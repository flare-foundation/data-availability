"""Collecting a committed proposal, with a fake registry and a real origin.

The distinctions worth the most here are between a proposer that has NOT YET
published and one that published something wrong. The commitment scheme exists
so an honest proposer is never accused, and this is where that promise is either
kept or quietly broken.
"""

import http.server
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils.crypto import keccak

from dal.gate.signing import CSP_PROPOSAL, payload_hash
from dal.models import Artifact, ArtifactIndex, Expectation, ExpectationState
from dal.proposals import collect_open_proposals, collect_proposal

CHAIN_ID = json.loads((Path(__file__).parent / "vectors.json").read_text())[0][
    "chainId"
]
PROPOSER_KEY = "0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318"
PROPOSER = Account.from_key(PROPOSER_KEY).address
WALLET = b"\x11" * 32
REGISTRY = "0x" + "0" * 36 + "7e61"
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
    asked: list = field(default_factory=list)

    def proposer(self, wallet_id, account_index, proposer):
        from dal.chain.registry import ProposerEntry

        return ProposerEntry(url=self.url, exists=self.exists)

    def is_allowed(self, wallet_registry, wallet_id, account_index, proposer):
        # Asserted rather than ignored: the registry is half of what identifies
        # the account, and a caller that dropped it would otherwise pass here
        # and resolve to the wrong account on a real chain.
        assert wallet_registry == REGISTRY
        self.asked.append((wallet_registry, wallet_id, account_index, proposer))
        return self.allowed


class _Origin(http.server.BaseHTTPRequestHandler):
    store: ClassVar[dict] = {}
    requests: ClassVar[list] = []

    def do_GET(self):
        self.requests.append(self.path)
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
    _Origin.requests = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Origin)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", _Origin.store
    server.shutdown()
    server.server_close()


def collect(url, package_hash, **kwargs):
    return collect_proposal(
        registry=kwargs.pop("registry", FakeRegistry(url)),
        chain_id=kwargs.pop("chain_id", CHAIN_ID),
        wallet_registry=kwargs.pop("wallet_registry", REGISTRY),
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
class TestProposerAdmission:
    """Who may propose is the contract's live check, asked on every attempt.

    ``finalizeProposal`` reads the proposer lists as they stand when it runs,
    so an answer is true only of the block it was read at. These tests hold the
    DAL to the consequence: a proposer that is not admitted is waited for, not
    refused, and its package is fetched once the owner admits it.
    """

    def test_a_proposer_not_admitted_is_not_fetched(self, origin):
        url, store = origin
        raw = package()
        h = keccak(raw)
        store[h.hex()] = raw

        outcome = collect(url, h, registry=FakeRegistry(url, allowed=False))
        assert not outcome.admitted
        assert "not admitted" in outcome.reason
        assert _Origin.requests == []
        assert not Artifact.objects.exists()

    def test_not_admitted_is_not_a_refusal(self, origin):
        # A refusal is terminal and never retried; this answer can change the
        # next block. Recording it as REFUSED would withhold for good a package
        # the contract may still accept.
        url, store = origin
        raw = package()
        h = keccak(raw)
        store[h.hex()] = raw

        collect(url, h, registry=FakeRegistry(url, allowed=False))
        e = Expectation.objects.get()
        assert e.state == ExpectationState.OPEN
        assert e.attempts == 1
        assert "not admitted" in e.reason

    def test_a_proposer_admitted_later_is_collected(self, origin):
        url, store = origin
        raw = package()
        h = keccak(raw)
        store[h.hex()] = raw
        registry = FakeRegistry(url, allowed=False)

        assert not collect(url, h, registry=registry).admitted
        registry.allowed = True  # the owner lists the proposer
        assert collect(url, h, registry=registry).admitted
        e = Expectation.objects.get()
        assert e.state == ExpectationState.MET
        assert e.reason == ""

    def test_membership_is_asked_for_the_account_and_the_proposer(self, origin):
        # No generation: the contract has none to ask at. The fake's signature
        # is the live call's, so a caller still passing one fails here.
        url, store = origin
        raw = package()
        h = keccak(raw)
        store[h.hex()] = raw
        registry = FakeRegistry(url)

        assert collect(url, h, registry=registry).admitted
        assert registry.asked == [(REGISTRY, WALLET, 0, PROPOSER)]

    def test_the_collector_retries_until_the_proposer_is_admitted(self, origin):
        # The automatic path: an expectation opened while the proposer was not
        # admitted is picked up again on the next tick, with the account it
        # recorded, and collected once the answer changes.
        url, store = origin
        raw = package()
        h = keccak(raw)
        store[h.hex()] = raw
        registry = FakeRegistry(url, allowed=False)
        collect(url, h, registry=registry)

        tick = collect_open_proposals(
            registry=registry, chain_id=CHAIN_ID, allow_private=True
        )
        assert [o.admitted for o in tick] == [False]
        assert Expectation.objects.get().attempts == 2

        registry.allowed = True
        tick = collect_open_proposals(
            registry=registry, chain_id=CHAIN_ID, allow_private=True
        )
        assert [o.admitted for o in tick] == [True]
        assert Expectation.objects.get().state == ExpectationState.MET
        assert registry.asked[-1] == (REGISTRY, WALLET, 0, PROPOSER)
