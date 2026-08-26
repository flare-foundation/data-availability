"""Collecting a committed proposal, with a fake registry and a real origin.

The distinctions worth the most here are between a proposer that has NOT YET
published and one that published something wrong. The commitment scheme exists
so an honest proposer is never accused, and this is where that promise is either
kept or quietly broken.
"""

import http.server
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils.crypto import keccak

from dal.gate.signing import CSP_PROPOSAL, payload_hash
from dal.models import Artifact, ArtifactIndex, Expectation, ExpectationState
from dal.proposals import collect_proposal

CHAIN_ID = json.loads((Path(__file__).parent / "vectors.json").read_text())[0][
    "chainId"
]
PROPOSER_KEY = "0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318"
PROPOSER = Account.from_key(PROPOSER_KEY).address
WALLET = b"\x11" * 32
TXID = b"\x22" * 32
ENVELOPE = b"an abi-encoded ProposalEnvelope"


def package(envelope=ENVELOPE, key=PROPOSER_KEY, chain_id=CHAIN_ID) -> bytes:
    digest = payload_hash(CSP_PROPOSAL, chain_id, keccak(envelope))
    sig = Account.sign_message(encode_defunct(digest), private_key=key).signature
    return envelope + bytes(sig)


@dataclass
class FakeRegistry:
    url: str
    exists: bool = True
    allowed: bool = True

    def proposer(self, wallet_id, account_index, proposer):
        from dal.chain.registry import ProposerEntry

        return ProposerEntry(self.url, self.exists, 0, 0)

    def is_allowed_at(self, wallet_id, account_index, proposer, generation):
        return self.allowed


class _Origin(http.server.BaseHTTPRequestHandler):
    store: ClassVar[dict] = {}

    def do_GET(self):
        body = self.store.get(self.path.lstrip("/"))
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def origin():
    _Origin.store = {}
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Origin)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", _Origin.store
    server.shutdown()
    server.server_close()


def collect(url, package_hash, **kwargs):
    return collect_proposal(
        registry=kwargs.pop("registry", FakeRegistry(url)),
        chain_id=kwargs.pop("chain_id", CHAIN_ID),
        wallet_id=WALLET,
        account_index=0,
        proposer=kwargs.pop("proposer", PROPOSER),
        package_hash=package_hash,
        allow_private=True,
        **kwargs,
    )


@pytest.mark.django_db
class TestAdmission:
    def test_a_committed_package_is_fetched_gated_and_stored(self, origin):
        url, store = origin
        raw = package()
        h = keccak(raw)
        store[h.hex()] = raw

        outcome = collect(url, h)
        assert outcome.admitted
        assert bytes(Artifact.objects.get(key=h.hex()).raw) == raw
        assert Expectation.objects.get().state == ExpectationState.MET

    def test_the_txid_index_is_written(self, origin):
        # The relay client and the facilitator know a txid, never a package
        # hash, so without this the swap cannot happen.
        url, store = origin
        raw = package()
        h = keccak(raw)
        store[h.hex()] = raw

        collect(url, h, txid=TXID)
        assert ArtifactIndex.objects.get().index_key == TXID.hex()


@pytest.mark.django_db
class TestNotYetPublished:
    def test_a_404_is_not_an_accusation(self, origin):
        # THE promise of committing before publishing. A commitment can be mined
        # a moment before the package appears, and recording that as the
        # proposer's failure is exactly the mistake the scheme prevents.
        url, _ = origin
        outcome = collect(url, keccak(package()))

        assert not outcome.admitted
        assert "not published yet" in outcome.reason
        e = Expectation.objects.get()
        assert e.state == ExpectationState.OPEN
        assert e.attempts == 1

    def test_it_is_retried_and_then_admitted(self, origin):
        url, store = origin
        raw = package()
        h = keccak(raw)

        assert not collect(url, h).admitted
        store[h.hex()] = raw
        assert collect(url, h).admitted
        assert Expectation.objects.get().state == ExpectationState.MET


@pytest.mark.django_db
class TestRefusal:
    def test_bytes_that_do_not_match_the_commitment_are_refused(self, origin):
        url, store = origin
        committed = keccak(package())
        store[committed.hex()] = package(b"a different envelope entirely")

        outcome = collect(url, committed)
        assert not outcome.admitted
        assert "does not hash to the committed" in outcome.reason
        assert Expectation.objects.get().state == ExpectationState.REFUSED
        assert not Artifact.objects.exists()

    def test_a_package_signed_by_someone_else_is_refused(self, origin):
        url, store = origin
        raw = package(key="0x" + "11" * 32)
        h = keccak(raw)
        store[h.hex()] = raw

        outcome = collect(url, h)
        assert not outcome.admitted
        assert "proposer signature" in outcome.reason

    def test_a_proposer_with_no_registered_endpoint_is_refused(self):
        outcome = collect(
            "", keccak(package()), registry=FakeRegistry("", exists=False)
        )
        assert not outcome.admitted
        assert "no registered endpoint" in outcome.reason

    def test_an_endpoint_pointing_at_metadata_is_refused(self):
        outcome = collect(
            "x", keccak(package()), registry=FakeRegistry("http://169.254.169.254/")
        )
        assert not outcome.admitted
        assert "unusable endpoint" in outcome.reason


@pytest.mark.django_db
class TestGenerationBinding:
    def test_a_proposer_not_admitted_for_that_generation_is_refused(self, origin):
        # A contest has a defined window: judging at latest would let a registry
        # edit invalidate a proposal already voted on.
        url, store = origin
        raw = package()
        h = keccak(raw)
        store[h.hex()] = raw

        outcome = collect(
            url, h, generation=7, registry=FakeRegistry(url, allowed=False)
        )
        assert not outcome.admitted
        assert "generation 7" in outcome.reason

    def test_membership_is_not_consulted_when_no_generation_is_given(self, origin):
        url, store = origin
        raw = package()
        h = keccak(raw)
        store[h.hex()] = raw
        assert collect(url, h, registry=FakeRegistry(url, allowed=False)).admitted
