"""Turning triggers into expectations.

This is the half of the chain read layer that decides **what should exist**. It
runs once per tick, reads a bounded range of logs, and writes an expectation for
every artifact the trigger implies -- one per (instruction, machine, tag).

Two rules hold the whole design together here:

* **An expectation is written the first time its trigger is seen and never
  re-derived.** The c-chain indexer keeps roughly a week; artifacts stay
  relevant longer. Re-deriving would quietly stop creating expectations the day
  the window passed them, and nothing would look wrong.
* **Progress is only recorded up to what the indexer has actually written.**
  A cursor advanced to the chain tip would skip every block the indexer had not
  reached yet, which is a gap nothing ever revisits.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone
from web3 import Web3
from web3._utils.events import get_event_data

from dal.chain.abi import TEE_INSTRUCTIONS_SENT, topic0
from dal.chain.indexer import IndexerReader, LogRow
from dal.keys import MessageClass, action_result_key
from dal.models import Expectation

logger = logging.getLogger(__name__)

__all__ = ["SUBMISSION_TAGS", "DiscoveryReport", "discover_tee_instructions"]

# Both answers a machine produces for one instruction. They are separate
# artifacts under separate keys: different payloads, signed separately.
SUBMISSION_TAGS = ("threshold", "end")

# How long an artifact stays worth holding once its trigger was seen. The hard
# backstop of §8.2, deliberately independent of the indexer's window.
DEFAULT_TTL = timedelta(days=14)


@dataclass
class DiscoveryReport:
    logs_read: int = 0
    expectations_created: int = 0
    through_block: int = 0
    indexer_lag: int = 0

    def __str__(self):
        return (
            f"logs={self.logs_read} created={self.expectations_created} "
            f"through={self.through_block} lag={self.indexer_lag}"
        )


def discover_tee_instructions(
    reader: IndexerReader,
    *,
    contract_address: str,
    from_block: int,
    to_block: int | None = None,
    ttl: timedelta = DEFAULT_TTL,
    limit: int = 1000,
) -> DiscoveryReport:
    """Read TeeInstructionsSent logs and write the expectations they imply."""
    rows, window = reader.logs(
        address=contract_address,
        topic0=topic0(TEE_INSTRUCTIONS_SENT),
        from_block=from_block,
        to_block=to_block,
        limit=limit,
    )

    report = DiscoveryReport(
        logs_read=len(rows),
        # Through what the indexer WROTE, never the chain tip: a cursor moved to
        # the tip skips whatever the indexer had not reached, and nothing goes
        # back for it.
        through_block=window.last_indexed
        if to_block is None
        else min(to_block, window.last_indexed),
        indexer_lag=window.lag,
    )

    now = timezone.now()
    for row in rows:
        report.expectations_created += _expectations_for(row, now=now, ttl=ttl)

    logger.info("DAL discovery: %s", report)
    return report


def _expectations_for(row: LogRow, *, now, ttl: timedelta) -> int:
    try:
        event = _decode(row)
    except Exception as exc:
        # One malformed log must not stall discovery for every later block. It
        # is logged loudly because it means an ABI that no longer matches what
        # the contract emits.
        logger.warning(
            "DAL: could not decode a TeeInstructionsSent at block %d log %d: %s",
            row.block_number,
            row.log_index,
            exc,
        )
        return 0

    args = event["args"]
    instruction_id = args["instructionId"]
    created = 0

    for machine in args["teeMachines"]:
        for tag in SUBMISSION_TAGS:
            key = action_result_key(instruction_id, machine["teeId"], tag)
            _, made = Expectation.objects.get_or_create(
                key=key.hex(),
                defaults={
                    "message_class": MessageClass.TEE_ACTION_RESULT,
                    "trigger_ref": f"0x{instruction_id.hex()}#{tag}",
                    "origin": machine["url"],
                    # Both identities the gate recovers against, as the event
                    # named them. This is why no registry read is needed, and
                    # why reading state at the latest block cannot be wrong
                    # for this class.
                    "params": {
                        "teeId": machine["teeId"],
                        "proxyId": machine["teeProxyId"],
                        "submissionTag": tag,
                        "instructionId": f"0x{instruction_id.hex()}",
                        "blockNumber": row.block_number,
                    },
                    "first_seen_at": now,
                    "expires_at": now + ttl,
                },
            )
            created += int(made)

    return created


def _decode(row: LogRow) -> dict:
    """Decode one indexer row with web3's event decoder.

    The indexer stores hex bare and lowercase; web3 wants ``0x``-prefixed
    values and bytes, so the row is put back into the shape a log receipt has.
    """
    return get_event_data(
        Web3().codec,
        TEE_INSTRUCTIONS_SENT,
        {
            "address": Web3.to_checksum_address("0x" + row.address),
            "topics": [
                bytes.fromhex(t)
                for t in (row.topic0, row.topic1, row.topic2, row.topic3)
                if t
            ],
            "data": "0x" + row.data,
            "blockNumber": row.block_number,
            "blockHash": b"\x00" * 32,
            "transactionHash": bytes.fromhex(row.transaction_hash),
            "transactionIndex": 0,
            "logIndex": row.log_index,
        },
    )


# The op type and command an attestation request is dispatched under. Both are
# names right-padded to 32 bytes — `op.Type.Hash()` is a UTF-8 pad, not a
# keccak, despite the name.
#
# The VALUES are the trap: the identifiers are "F_FDC2" and "PROVE", not "FDC2"
# and "Prove". Getting them wrong produces a filter that matches nothing, which
# reads exactly like a chain on which no proposal was ever requested — and cost
# a run to notice, because discovery kept reporting logs it had read and
# expectations it had not created.
OP_FDC2 = b"F_FDC2".ljust(32, b"\x00")
OP_PROVE = b"PROVE".ljust(32, b"\x00")


def discover_proposal_requests(
    reader: IndexerReader,
    *,
    contract_address: str,
    from_block: int,
    submitter_of,
    to_block: int | None = None,
    ttl: timedelta = timedelta(hours=6),
    limit: int = 1000,
) -> DiscoveryReport:
    """Create proposal expectations from the requests proposers committed.

    **The trigger is free.** A proposer's FDC2 attestation request becomes a
    `TeeInstructionsSent` instruction, which is the event already indexed for
    machine results — so a proposal expectation is a message decoded from a
    stream the node is reading anyway, not a second source to watch.

    ``submitter_of(transaction_hash)`` answers who actually sent the
    transaction. That is deliberately NOT taken from the event: the instruction
    carries a ``claimBackAddress`` chosen by whoever called the hub, so it is a
    hint and cannot establish authorship. The transaction's sender can, and it
    is the whole basis of provenance under commit-then-publish.
    """
    rows, window = reader.logs(
        address=contract_address,
        topic0=topic0(TEE_INSTRUCTIONS_SENT),
        from_block=from_block,
        to_block=to_block,
        limit=limit,
    )

    report = DiscoveryReport(
        logs_read=len(rows),
        through_block=window.last_indexed
        if to_block is None
        else min(to_block, window.last_indexed),
        indexer_lag=window.lag,
    )

    now = timezone.now()
    for row in rows:
        try:
            event = _decode(row)
        except Exception as exc:
            logger.warning(
                "DAL: undecodable instruction at block %d: %s", row.block_number, exc
            )
            continue

        args = event["args"]
        if args["opType"] != OP_FDC2 or args["opCommand"] != OP_PROVE:
            continue  # not an attestation request

        parsed = _proposal_request(args["message"])
        if parsed is None:
            continue  # some other attestation type

        proposer = submitter_of(row.transaction_hash)
        if not proposer:
            logger.warning(
                "DAL: no sender for the request in tx %s; provenance cannot be established",
                row.transaction_hash,
            )
            continue

        report.expectations_created += _proposal_expectation(
            parsed, proposer=proposer, block=row.block_number, now=now, ttl=ttl
        )

    logger.info("DAL proposal discovery: %s", report)
    return report


def _proposal_request(message: bytes) -> dict | None:
    """Decode an instruction message into a proposal request, or None."""
    from eth_abi.abi import decode as abi_decode

    from dal.chain.abi import (
        FDC2_ATTESTATION_REQUEST,
        PMW_UTXO_PROPOSAL_CHECK,
        PROPOSAL_REQUEST_BODY,
    )

    try:
        # ((attestationType, sourceId, thresholdBIPS, proofOwner), requestBody)
        (request,) = abi_decode(["((bytes32,bytes32,uint16,address),bytes)"], message)
        header, body = request
        if header[0] != PMW_UTXO_PROPOSAL_CHECK:
            return None
        wallet_id, account_index, sequence, attempt, generation, package_hash = (
            abi_decode(PROPOSAL_REQUEST_BODY, body)
        )
    except Exception:
        return None

    _ = FDC2_ATTESTATION_REQUEST  # documented shape; decoded positionally above
    return {
        "wallet_id": wallet_id,
        "account_index": account_index,
        "sequence_position": sequence,
        "attempt": attempt,
        "generation": generation,
        "package_hash": package_hash,
    }


def _proposal_expectation(parsed, *, proposer, block, now, ttl) -> int:
    """Write the expectation, keyed by the commitment itself.

    ``get_or_create`` is what makes a reissue a RETRY rather than a rival: an
    identical request submitted again finds the first expectation and leaves its
    provenance alone. The first commitment keeps it, which is the rule.
    """
    key = parsed["package_hash"].hex()
    _, created = Expectation.objects.get_or_create(
        key=key,
        defaults={
            "message_class": MessageClass.PROPOSAL,
            "trigger_ref": f"0x{parsed['wallet_id'].hex()}/{parsed['account_index']}"
            f"#{parsed['sequence_position']}.{parsed['attempt']}",
            "origin": "",  # resolved from the registry when it is fetched
            "params": {
                "proposer": proposer,
                "packageHash": f"0x{key}",
                "walletId": f"0x{parsed['wallet_id'].hex()}",
                "accountIndex": parsed["account_index"],
                "generation": parsed["generation"],
                "blockNumber": block,
            },
            "first_seen_at": now,
            "expires_at": now + ttl,
        },
    )
    return int(created)
