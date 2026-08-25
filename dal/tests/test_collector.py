"""The collection tick, against a real database.

The two distinctions worth the most here are the ones the explorer's poller
either learned the hard way or cannot make at all: a throttled call must not
consume the give-up budget, and a gate refusal must not look like an outage.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from dal.collector import Outcome, collect_once
from dal.fetch import FetchError
from dal.gate.result import Admitted, Refused
from dal.models import Artifact, ArtifactIndex, Expectation, ExpectationState

KEY = bytes.fromhex("aa" * 32)
INDEX = bytes.fromhex("cc" * 32)
ORIGIN = "http://93.184.216.34:8080"
BODY = b'{"result":{"ok":true}}'


def make_expectation(**kwargs):
    now = kwargs.pop("first_seen_at", timezone.now())
    return Expectation.objects.create(
        key=kwargs.pop("key", KEY.hex()),
        message_class="tee_action_result",
        trigger_ref="0x" + "11" * 32 + "#threshold",
        origin="machine-a",
        first_seen_at=now,
        expires_at=now + timedelta(days=14),
        **kwargs,
    )


def admitting(_expectation, raw):
    return Admitted(key=KEY, raw=raw)


def refusing(_expectation, _raw):
    return Refused("machine signature: recovers to somebody else")


def responder(status=200, body=BODY):
    def _fetch(_expectation, _resolved):
        return status, body

    return _fetch


def run(**kwargs):
    kwargs.setdefault("gate", admitting)
    kwargs.setdefault("origin_url", lambda _e: ORIGIN)
    kwargs.setdefault("fetcher", responder())
    return collect_once(**kwargs)


@pytest.mark.django_db
class TestSuccess:
    def test_an_admitted_artifact_is_stored_and_the_expectation_closes(self):
        make_expectation()
        report = run(index_keys=lambda _e: [INDEX])

        assert report.counts == {Outcome.FETCHED: 1}
        artifact = Artifact.objects.get(key=KEY.hex())
        assert bytes(artifact.raw) == BODY
        assert artifact.size_bytes == len(BODY)
        assert artifact.origin == ORIGIN
        assert Expectation.objects.get().state == ExpectationState.MET

    def test_the_secondary_index_is_written(self):
        make_expectation()
        run(index_keys=lambda _e: [INDEX])
        entry = ArtifactIndex.objects.get()
        assert entry.index_key == INDEX.hex()

    def test_a_met_expectation_is_not_fetched_again(self):
        make_expectation(state=ExpectationState.MET)

        def explode(_e, _r):
            raise AssertionError("a closed expectation must not be fetched")

        assert run(fetcher=explode).counts == {}


@pytest.mark.django_db
class TestNotYet:
    def test_a_404_leaves_the_expectation_open(self):
        make_expectation()
        report = run(fetcher=responder(status=404))

        assert report.counts == {Outcome.NOT_READY: 1}
        e = Expectation.objects.get()
        assert e.state == ExpectationState.OPEN
        assert e.attempts == 1
        assert e.last_attempt_at is not None

    def test_a_transport_failure_leaves_it_open_and_records_why(self):
        def failing(_e, _r):
            raise FetchError("connection refused")

        report = (make_expectation(), run(fetcher=failing))[1]
        assert report.counts == {Outcome.ERROR: 1}
        e = Expectation.objects.get()
        assert e.state == ExpectationState.OPEN
        assert "connection refused" in e.reason

    def test_a_500_is_an_error_not_a_refusal(self):
        # The origin failed to answer; it did not answer wrongly. Only the gate
        # can say the second thing.
        make_expectation()
        assert run(fetcher=responder(status=500)).counts == {Outcome.ERROR: 1}
        assert Expectation.objects.get().state == ExpectationState.OPEN


@pytest.mark.django_db
class TestThrottling:
    def test_a_429_does_not_consume_the_give_up_budget(self):
        # THE point of the outcome taxonomy. Being throttled is a statement
        # about our request rate, so it must not count as an attempt the origin
        # declined -- otherwise a busy proxy times out expectations that would
        # have succeeded.
        make_expectation()
        report = run(fetcher=responder(status=429))

        assert report.counts == {Outcome.RATE_LIMITED: 1}
        e = Expectation.objects.get()
        assert e.state == ExpectationState.OPEN
        assert e.attempts == 0
        assert e.last_attempt_at is None

    def test_one_429_backs_the_whole_host_off_for_the_tick(self):
        for i in range(3):
            make_expectation(key=f"{i:02x}" + "aa" * 31)
        calls = []

        def counting(_e, _r):
            calls.append(1)
            return 429, b""

        report = run(fetcher=counting)
        assert len(calls) == 1
        assert report.counts == {Outcome.RATE_LIMITED: 3}


@pytest.mark.django_db
class TestRefusal:
    def test_a_gate_refusal_is_terminal_and_keeps_its_reason(self):
        make_expectation()
        report = run(gate=refusing)

        assert report.counts == {Outcome.REFUSED: 1}
        e = Expectation.objects.get()
        assert e.state == ExpectationState.REFUSED
        assert "recovers to somebody else" in e.reason

    def test_a_refused_artifact_is_not_stored(self):
        # The whole purpose of the gate. Storing it "for reference" would put
        # bytes nobody vouched for behind an API that implies somebody did.
        make_expectation()
        run(gate=refusing)
        assert not Artifact.objects.exists()

    def test_a_refusal_is_not_retried(self):
        make_expectation()
        run(gate=refusing)
        assert run(gate=refusing).counts == {}

    def test_an_unusable_origin_url_is_refused_not_retried(self):
        # A URL pointing at cloud metadata will never become fetchable. Waiting
        # out a give-up window for it wastes half an hour saying so.
        make_expectation()
        report = run(origin_url=lambda _e: "http://169.254.169.254/")

        assert report.counts == {Outcome.REFUSED: 1}
        e = Expectation.objects.get()
        assert e.state == ExpectationState.REFUSED
        assert "unusable origin" in e.reason


@pytest.mark.django_db
class TestGivingUp:
    def test_an_old_expectation_is_closed_as_unmet(self):
        make_expectation(first_seen_at=timezone.now() - timedelta(hours=2))

        def explode(_e, _r):
            raise AssertionError("a give-up must not cost a request")

        report = run(fetcher=explode)
        assert report.counts == {Outcome.GAVE_UP: 1}
        e = Expectation.objects.get()
        assert e.state == ExpectationState.UNMET
        assert e.reason == "gave up waiting"

    def test_unmet_is_distinguishable_from_refused(self):
        # D7: "asked and never answered" is a different fact from "answered
        # with something wrong", and only one of them accuses anybody.
        make_expectation(
            key="01" + "aa" * 31, first_seen_at=timezone.now() - timedelta(hours=2)
        )
        make_expectation(key="02" + "aa" * 31)
        run(gate=refusing)

        assert Expectation.objects.filter(state=ExpectationState.UNMET).count() == 1
        assert Expectation.objects.filter(state=ExpectationState.REFUSED).count() == 1
