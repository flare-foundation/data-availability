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

from dal.gate.result import Admitted, Refused, Verdict
from dal.gate.signing import (
    PROXY_ACTION_RESULT,
    TEE_ACTION_RESULT,
    SignatureError,
    action_result_hash,
    payload_hash,
    verify,
)
from dal.keys import action_result_key

__all__ = ["gate_action_result"]


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
