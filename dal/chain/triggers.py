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
