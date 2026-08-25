"""The G2 gate, driven by a body signed with the Go-generated vectors.

Every negative case here is a way an origin can lie. The gate is the only place
that notices, so each one gets its own test rather than a shared "malformed"
case -- a refusal for the wrong reason is a passing test that proves nothing.
"""

import json
from pathlib import Path

import pytest

from dal.gate.g2 import gate_action_result
from dal.gate.result import Admitted, Refused
from dal.keys import action_result_key

VECTORS = {
    v["name"]: v
    for v in json.loads((Path(__file__).parent / "vectors.json").read_text())
}
TEE = VECTORS["tee_action_result"]
PROXY = VECTORS["proxy_action_result"]

# Both vectors were signed by one key, so the machine and its proxy share an
# address here. That is unrealistic and irrelevant: the gate looks each up
# separately, and a test below proves it does not accept one for the other.
SIGNER = TEE["signer"]
CHAIN_ID = TEE["chainId"]
INSTRUCTION = bytes.fromhex(TEE["actionId"].removeprefix("0x"))
TAG = TEE["submissionTag"]


def body(**overrides) -> bytes:
    payload = {
        "result": {
            "id": TEE["actionId"],
            "submissionTag": TAG,
            "status": TEE["status"],
            "data": TEE["data"],
        },
        "signature": TEE["signature"],
        "proxySignature": PROXY["signature"],
    }
    for key, value in overrides.items():
        if key in ("id", "submissionTag", "status", "data"):
            payload["result"][key] = value
        else:
            payload[key] = value
    return json.dumps(payload).encode()


def gate(raw: bytes, *, tee_id=SIGNER, proxy_id=SIGNER, tag=TAG):
    return gate_action_result(
        raw,
        chain_id=CHAIN_ID,
        instruction_id=INSTRUCTION,
        tee_id=tee_id,
        proxy_id=proxy_id,
        submission_tag=tag,
    )


def test_a_correctly_signed_result_is_admitted():
    verdict = gate(body())
    assert isinstance(verdict, Admitted)
    assert verdict.key == action_result_key(INSTRUCTION, SIGNER, TAG)


def test_the_admitted_bytes_are_the_fetched_bytes():
    # D8: the store keeps what the origin served. A JSON round-trip is not
    # byte-stable, so a gate that handed back its own re-encoding would store
    # bytes whose signatures no longer verify at the next hop.
    raw = (
        b'{"result":{"id":"%s","submissionTag":"%s","status":%d,"data":"%s"},"signature":"%s","proxySignature":"%s"}'
        % (
            TEE["actionId"].encode(),
            TAG.encode(),
            TEE["status"],
            TEE["data"].encode(),
            TEE["signature"].encode(),
            PROXY["signature"].encode(),
        )
    )
    verdict = gate(raw)
    assert isinstance(verdict, Admitted)
    assert verdict.raw is raw


def test_a_result_for_another_instruction_is_refused():
    other = "0x" + "11" * 32
    verdict = gate(body(id=other))
    assert isinstance(verdict, Refused)
    assert "names instruction" in verdict.reason


def test_a_result_under_another_tag_is_refused():
    # The proxy answers per tag. Accepting an `end` body for a `threshold`
    # expectation would let one signature satisfy two slots.
    verdict = gate(body(submissionTag="end"))
    assert isinstance(verdict, Refused)
    assert "tag" in verdict.reason


def test_a_flipped_status_is_refused():
    # Status is inside the signed hash, so a machine's refusal cannot be
    # relabelled as its success without breaking the signature.
    verdict = gate(body(status=TEE["status"] + 1))
    assert isinstance(verdict, Refused)
    assert "signature" in verdict.reason


def test_tampered_data_is_refused():
    verdict = gate(body(data="0xdeadbeef"))
    assert isinstance(verdict, Refused)
    assert "machine signature" in verdict.reason


def test_the_proxy_signature_is_not_accepted_as_the_machines():
    # The two prefixes differ, so swapping the two signatures must fail even
    # though one key produced both.
    verdict = gate(body(signature=PROXY["signature"], proxySignature=TEE["signature"]))
    assert isinstance(verdict, Refused)
    assert "machine signature" in verdict.reason


def test_an_unregistered_machine_is_refused():
    verdict = gate(body(), tee_id="0x" + "00" * 19 + "01")
    assert isinstance(verdict, Refused)
    assert "machine signature" in verdict.reason


def test_an_unregistered_proxy_is_refused():
    verdict = gate(body(), proxy_id="0x" + "00" * 19 + "01")
    assert isinstance(verdict, Refused)
    assert "proxy signature" in verdict.reason


def test_a_signature_from_another_chain_is_refused():
    verdict = gate_action_result(
        body(),
        chain_id=CHAIN_ID + 1,
        instruction_id=INSTRUCTION,
        tee_id=SIGNER,
        proxy_id=SIGNER,
        submission_tag=TAG,
    )
    assert isinstance(verdict, Refused)
    assert "machine signature" in verdict.reason


def test_a_missing_proxy_signature_is_refused_not_ignored():
    payload = json.loads(body())
    del payload["proxySignature"]
    verdict = gate(json.dumps(payload).encode())
    assert isinstance(verdict, Refused)
    assert "proxySignature" in verdict.reason


@pytest.mark.parametrize(
    "raw", [b"", b"not json", b"[]", b"null", b"\xff\xfe"], ids=repr
)
def test_a_body_that_is_not_an_object_is_refused(raw):
    assert isinstance(gate(raw), Refused)


def test_a_boolean_status_is_refused():
    # bool is an int in Python, so `True` would otherwise pass an isinstance
    # check and hash as 1.
    verdict = gate(body(status=True))
    assert isinstance(verdict, Refused)
    assert "not an integer" in verdict.reason


def test_a_body_with_no_result_is_refused():
    verdict = gate(json.dumps({"signature": TEE["signature"]}).encode())
    assert isinstance(verdict, Refused)
    assert "no result" in verdict.reason
