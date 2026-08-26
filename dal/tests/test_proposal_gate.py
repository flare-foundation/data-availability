"""The proposal package gate, and the commitment that makes it meaningful.

A proposer signs its batch, hashes the SIGNED proposal, submits an FDC2 request
naming that hash, waits for it to be mined, and only then publishes. So by the
time anything is fetched, the chain already says both what the bytes must hash
to and who committed to them. These tests are about what happens when either
half is violated.
"""

import json
from pathlib import Path

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils.crypto import keccak

from dal.gate.g2 import gate_proposal_package
from dal.gate.result import Admitted, Refused
from dal.gate.signing import CSP_PROPOSAL, payload_hash

CHAIN_ID = json.loads((Path(__file__).parent / "vectors.json").read_text())[0][
    "chainId"
]

# The well-known go-ethereum test key, the same one the Go vector generator uses.
PROPOSER_KEY = "0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318"
PROPOSER = Account.from_key(PROPOSER_KEY).address
STRANGER = Account.from_key("0x" + "11" * 32).address

ENVELOPE = b"an abi-encoded ProposalEnvelope would go here"


def sign_envelope(envelope: bytes, key=PROPOSER_KEY, chain_id=CHAIN_ID) -> bytes:
    digest = payload_hash(CSP_PROPOSAL, chain_id, keccak(envelope))
    return Account.sign_message(encode_defunct(digest), private_key=key).signature


def package(envelope: bytes = ENVELOPE, **kwargs) -> bytes:
    return envelope + sign_envelope(envelope, **kwargs)


def gate(raw: bytes, *, package_hash=None, proposer=PROPOSER, chain_id=CHAIN_ID):
    return gate_proposal_package(
        raw,
        chain_id=chain_id,
        package_hash=package_hash if package_hash is not None else keccak(raw),
        proposer=proposer,
    )


class TestAdmission:
    def test_a_committed_package_is_admitted(self):
        raw = package()
        verdict = gate(raw)
        assert isinstance(verdict, Admitted)
        assert verdict.key == keccak(raw)
        assert verdict.raw is raw

    def test_the_key_is_the_committed_hash_itself(self):
        # DAL-17's resolution: the artifact IS the package, so its key is the
        # hash of exactly the bytes served. No header, no second encoding, and
        # nothing outside the hashed bytes.
        raw = package()
        verdict = gate(raw)
        assert isinstance(verdict, Admitted)
        assert keccak(verdict.raw) == verdict.key

    def test_the_envelope_is_not_decoded(self):
        # The DAL never parses the envelope: the verifier checks its
        # proposerAddress field against the registry, this gate checks
        # possession of the committing key. Keeping the ABI out of here means a
        # change to the envelope layout cannot stop artifacts being stored.
        raw = package(b"\xff\x00 not abi-encoded anything \xde\xad")
        assert isinstance(gate(raw), Admitted)


class TestTheCommitment:
    def test_bytes_that_do_not_hash_to_the_commitment_are_refused(self):
        # The whole point of committing before publishing: a proposer cannot
        # serve something other than what it committed to.
        raw = package()
        verdict = gate(raw, package_hash=keccak(b"a different package"))
        assert isinstance(verdict, Refused)
        assert "does not hash to the committed" in verdict.reason

    def test_one_flipped_byte_breaks_the_commitment(self):
        raw = bytearray(package())
        raw[0] ^= 0xFF
        original = keccak(bytes(package()))
        verdict = gate(bytes(raw), package_hash=original)
        assert isinstance(verdict, Refused)

    def test_a_truncated_package_is_refused(self):
        assert isinstance(gate(b"\x01" * 65), Refused)
        assert isinstance(gate(b""), Refused)

    def test_a_short_commitment_is_refused(self):
        verdict = gate(package(), package_hash=b"\xaa" * 31)
        assert isinstance(verdict, Refused)
        assert "not 32" in verdict.reason


class TestAttribution:
    def test_a_package_signed_by_someone_else_is_refused(self):
        # The proposer here comes from the request's SUBMITTER, on chain, so it
        # cannot be a wrong guess. A package whose signature recovers elsewhere
        # is somebody else's work served under this commitment.
        raw = package(key="0x" + "11" * 32)
        verdict = gate(raw, proposer=PROPOSER)
        assert isinstance(verdict, Refused)
        assert "proposer signature" in verdict.reason

    def test_the_same_package_is_refused_for_a_different_proposer(self):
        verdict = gate(package(), proposer=STRANGER)
        assert isinstance(verdict, Refused)

    def test_a_signature_from_another_chain_is_refused(self):
        # chainId is inside the signed payload, so a package committed on one
        # network cannot be replayed onto another.
        raw = ENVELOPE + sign_envelope(ENVELOPE, chain_id=CHAIN_ID + 1)
        verdict = gate(raw)
        assert isinstance(verdict, Refused)
        assert "proposer signature" in verdict.reason

    def test_a_valid_signature_over_the_wrong_envelope_is_refused(self):
        # Splice: A's signature, B's envelope, hashed honestly as a package.
        # G1 passes -- these really are the committed bytes -- and G2 is what
        # catches it.
        raw = b"a different envelope entirely" + sign_envelope(ENVELOPE)
        verdict = gate(raw)
        assert isinstance(verdict, Refused)
        assert "proposer signature" in verdict.reason

    @pytest.mark.parametrize("case", ["lower", "upper"], ids=str)
    def test_the_proposers_address_case_does_not_matter(self, case):
        addr = PROPOSER.lower() if case == "lower" else "0x" + PROPOSER[2:].upper()
        assert isinstance(gate(package(), proposer=addr), Admitted)
