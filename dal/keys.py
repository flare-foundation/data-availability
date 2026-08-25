"""How every artifact in the store is named.

Two kinds of key, and the difference decides what prefetch can ask for.

A **content key** is the hash of the bytes. It is self-checking -- a node cannot
file an artifact under a key it does not hash to -- but it cannot be known
before the content exists.

A **coordinate key** is the hash of the tuple that names the slot. It is
computable from the trigger alone, which is what lets a node that has seen
``TeeInstructionsSent`` ask a peer for exactly the artifacts it is missing.

Every key is 32 bytes whichever kind it is, so the byte-serving API has one
shape for every message class and never grows a per-type route.

Coordinate keys are domain-separated by message class for the same reason
signatures are (see gate/signing.py): without it, two classes whose coordinates
happen to encode alike would share a keyspace, and a collision there is an
artifact silently overwriting another rather than an error anyone sees.
"""

from typing import Final

from eth_utils.crypto import keccak

__all__ = [
    "MessageClass",
    "action_result_key",
    "instruction_index_key",
    "proposal_key",
    "round_payload_key",
]

_KEY_DOMAIN: Final = b"FLARE_DAL_KEY_V1"


class MessageClass:
    """The message classes the store holds. Values are stable and never reused."""

    FTSO_ROUND = "ftso_round"
    FDC_ROUND = "fdc_round"
    TEE_ACTION_RESULT = "tee_action_result"
    PROPOSAL = "proposal"


def _coordinate(message_class: str, *parts: bytes) -> bytes:
    return keccak(_KEY_DOMAIN + keccak(message_class.encode("ascii")) + b"".join(parts))


def _u64(value: int) -> bytes:
    if not 0 <= value < 2**64:
        raise ValueError(f"{value} does not fit in 8 bytes")
    return value.to_bytes(8, "big")


def round_payload_key(protocol_id: int, voting_round_id: int) -> bytes:
    """Primary key of one protocol's whole round payload.

    The round, not the leaf: a single attestation result cannot be gated on its
    own, because rebuilding the Merkle root needs every leaf. Per-leaf rows are
    projections over this artifact, not artifacts of their own.
    """
    if not 0 <= protocol_id <= 0xFF:
        raise ValueError(f"protocol id {protocol_id} does not fit in a byte")
    message_class = (
        MessageClass.FTSO_ROUND if protocol_id == 100 else MessageClass.FDC_ROUND
    )
    return _coordinate(message_class, bytes([protocol_id]), _u64(voting_round_id))


def action_result_key(instruction_id: bytes, tee_id: str, submission_tag: str) -> bytes:
    """Primary key of one machine's answer to one instruction under one tag.

    The tag is part of the key because ``threshold`` and ``end`` are different
    artifacts of the same instruction, carrying different payloads and signed
    separately.
    """
    if len(instruction_id) != 32:
        raise ValueError(f"instruction id must be 32 bytes, got {len(instruction_id)}")
    return _coordinate(
        MessageClass.TEE_ACTION_RESULT,
        instruction_id,
        _address(tee_id),
        keccak(submission_tag.encode("utf-8")),
    )


def instruction_index_key(instruction_id: bytes) -> bytes:
    """Secondary index: every artifact belonging to one instruction.

    Set-valued on purpose. A node that missed a trigger asks "what do you hold
    for this instruction", which is a question a primary key cannot express.
    """
    if len(instruction_id) != 32:
        raise ValueError(f"instruction id must be 32 bytes, got {len(instruction_id)}")
    return _coordinate(MessageClass.TEE_ACTION_RESULT, instruction_id)


def proposal_key(proposal_hash: bytes) -> bytes:
    """Primary key of a proposal package -- a CONTENT key, passed through.

    ``proposalHash`` is already domain-separated and chain-bound by the
    CSP_PROPOSAL payload the proposer signs, so hashing it again would only
    break the identity every existing consumer already binds to.
    """
    if len(proposal_hash) != 32:
        raise ValueError(f"proposal hash must be 32 bytes, got {len(proposal_hash)}")
    return proposal_hash


def _address(value: str) -> bytes:
    raw = bytes.fromhex(value.removeprefix("0x"))
    if len(raw) != 20:
        raise ValueError(f"{value!r} is not a 20-byte address")
    return raw
