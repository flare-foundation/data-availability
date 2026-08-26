"""G2: admit an artifact because a registered identity signed it.

The gate does no I/O. It is handed the bytes as fetched and the identities the
chain says should have signed them, and it answers. Reading the registry is the
caller's job, which keeps every rule here testable without a node.

Ported from the Go implementation in fcc-facilitator-bot, which performs
exactly these checks before it will assemble a transaction out of a machine's
answer.
"""

import json
from typing import Any

from eth_utils.crypto import keccak

from dal.gate.result import Admitted, Refused, Verdict
from dal.gate.signing import (
    CSP_PROPOSAL,
    PROXY_ACTION_RESULT,
    TEE_ACTION_RESULT,
    TEE_VOTE_HASH,
    SignatureError,
    action_result_hash,
    payload_hash,
    verify,
)
from dal.keys import action_result_key

__all__ = ["gate_action_result", "gate_proposal_package", "gate_vote"]


def _unhex(value: Any, field: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError(f"{field} is not a string")
    try:
        return bytes.fromhex(value.removeprefix("0x"))
    except ValueError as exc:
        raise ValueError(f"{field} is not hex: {exc}") from exc


def gate_action_result(
    raw: bytes,
    *,
    chain_id: int,
    instruction_id: bytes,
    tee_id: str,
    proxy_id: str,
    submission_tag: str,
) -> Verdict:
    """Gate one machine's answer to one instruction.

    ``raw`` is the response body exactly as the proxy served it, and it is what
    an Admitted verdict carries back for storage. The gate parses a copy to
    check it and never re-serializes: a JSON round-trip is not byte-stable, and
    a store that kept the re-encoded form would serve bytes whose signatures no
    longer verify.

    The identity checks come first and cheapest -- an answer about a different
    instruction or under a different tag is refused before any elliptic-curve
    work happens.
    """
    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return Refused(f"body is not JSON: {exc}")
    if not isinstance(body, dict):
        return Refused("body is not a JSON object")

    result = body.get("result")
    if not isinstance(result, dict):
        return Refused("body carries no result object")

    try:
        got_id = _unhex(result.get("id"), "result.id")
        data = _unhex(result.get("data", "0x"), "result.data")
        signature = _unhex(body.get("signature"), "signature")
        proxy_signature = _unhex(body.get("proxySignature"), "proxySignature")
    except ValueError as exc:
        return Refused(str(exc))

    if got_id != instruction_id:
        return Refused(
            f"result names instruction {got_id.hex()}, expected {instruction_id.hex()}"
        )

    got_tag = result.get("submissionTag")
    if got_tag != submission_tag:
        return Refused(f"result carries tag {got_tag!r}, expected {submission_tag!r}")

    status = result.get("status")
    if not isinstance(status, int) or isinstance(status, bool):
        return Refused("result status is not an integer")
    if not 0 <= status <= 0xFF:
        return Refused(f"result status {status} does not fit in a byte")

    try:
        data_hash = action_result_hash(data, got_id, submission_tag, status)
    except ValueError as exc:
        return Refused(str(exc))

    for prefix, sig, signer, label in (
        (TEE_ACTION_RESULT, signature, tee_id, "machine"),
        (PROXY_ACTION_RESULT, proxy_signature, proxy_id, "proxy"),
    ):
        try:
            verify(payload_hash(prefix, chain_id, data_hash), sig, signer)
        except SignatureError as exc:
            return Refused(f"{label} signature: {exc}")

    return Admitted(
        key=action_result_key(instruction_id, tee_id, submission_tag), raw=raw
    )


def gate_vote(data: bytes, *, chain_id: int, tee_id: str) -> Refused | None:
    """Gate the RewardingData carried by an `end` result. ``None`` means admitted.

    The vote is signed under a DIFFERENT preimage from the result that carries
    it: the dataHash is ``VoteSequence.voteHash`` itself, not the hash of the
    action result. So an `end` result carries two independent signatures over
    two different things, and checking one says nothing about the other.

    Not a Verdict, because a vote is not an artifact of its own -- it lives
    inside an action result and inherits that result's key. This is the
    second half of gating one `end` body.
    """
    try:
        payload = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return Refused(f"rewarding data is not JSON: {exc}")
    if not isinstance(payload, dict):
        return Refused("rewarding data is not a JSON object")

    sequence = payload.get("voteSequence")
    if not isinstance(sequence, dict):
        return Refused("rewarding data carries no voteSequence")

    try:
        vote_hash = _unhex(sequence.get("voteHash"), "voteHash")
        signature = _unhex(payload.get("signature"), "signature")
    except ValueError as exc:
        return Refused(str(exc))

    if len(vote_hash) != 32:
        return Refused(f"voteHash is {len(vote_hash)} bytes, not 32")

    claimed = sequence.get("teeId")
    if isinstance(claimed, str) and claimed.lower() != tee_id.lower():
        # The vote names its own machine. A body claiming to be another
        # machine's vote is refused before the signature is even considered.
        return Refused(f"vote names machine {claimed}, expected {tee_id}")

    try:
        verify(payload_hash(TEE_VOTE_HASH, chain_id, vote_hash), signature, tee_id)
    except SignatureError as exc:
        return Refused(f"vote signature: {exc}")
    return None


# A proposer signature is [R || S || V], fixed width, so a package needs no
# length prefix and no encoding decision: the last 65 bytes are the signature
# and everything before them is the envelope.
PROPOSER_SIG_BYTES = 65


def gate_proposal_package(
    raw: bytes, *, chain_id: int, package_hash: bytes, proposer: str
) -> Verdict:
    """Gate a proposal package: ``envelope ‖ proposerSig``.

    Two checks over one artifact, and they establish different things.

    **G1** — ``keccak(raw) == packageHash``. The FDC2 request committed to this
    hash before the package existed publicly (§5.7), so a match says these are
    the bytes that were committed to, and nothing else can be served under this
    key.

    **G2** — the signature recovers, under ``CSP_PROPOSAL`` over the envelope's
    own hash, to the proposer that submitted the committing request. The
    submitter is an on-chain fact, so ``proposer`` is derived rather than
    asserted and a wrong attribution is not expressible.

    The envelope is deliberately NOT decoded here. Its `proposerAddress` field
    is checked by the verifier against the account's registry; this gate checks
    possession of the key that committed. Two independent checks over one
    artifact are worth more than one check performed twice, and keeping the DAL
    free of the envelope's ABI means a change to that layout does not stop
    artifacts being stored.
    """
    if len(package_hash) != 32:
        return Refused(f"package hash is {len(package_hash)} bytes, not 32")
    if len(raw) <= PROPOSER_SIG_BYTES:
        return Refused(
            f"package is {len(raw)} bytes, too short to hold an envelope and a signature"
        )

    # G1 first: it is a hash comparison against a value the chain already
    # committed to, so it is both cheaper than recovery and stronger.
    if keccak(raw) != package_hash:
        return Refused("package does not hash to the committed packageHash")

    envelope = raw[:-PROPOSER_SIG_BYTES]
    signature = raw[-PROPOSER_SIG_BYTES:]

    try:
        verify(
            payload_hash(CSP_PROPOSAL, chain_id, keccak(envelope)), signature, proposer
        )
    except SignatureError as exc:
        return Refused(f"proposer signature: {exc}")

    return Admitted(key=package_hash, raw=raw)
