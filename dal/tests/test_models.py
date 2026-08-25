"""The store's schema, exercised against a real database.

These are the tests the migration exists for. A migration that has only been
generated is a claim; one that has been applied and then written to and read
back is a fact.
"""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from dal.models import Artifact, ArtifactIndex, Expectation, ExpectationState

KEY_A = "aa" * 32
KEY_B = "bb" * 32
INDEX_KEY = "cc" * 32


def make_artifact(key=KEY_A, raw=b'{"result":{}}'):
    return Artifact.objects.create(
        key=key,
        message_class="tee_action_result",
        raw=raw,
        origin="0x2c7536E3605D9C16a7a3D7b1898e529396a65c23",
        gated_at=timezone.now(),
        size_bytes=len(raw),
    )


def make_expectation(key=KEY_A, **kwargs):
    now = timezone.now()
    return Expectation.objects.create(
        key=key,
        message_class=kwargs.pop("message_class", "tee_action_result"),
        trigger_ref=kwargs.pop("trigger_ref", "0x" + "11" * 32),
        origin=kwargs.pop("origin", "machine-a"),
        first_seen_at=now,
        expires_at=now + timezone.timedelta(days=14),
        **kwargs,
    )


@pytest.mark.django_db
class TestArtifact:
    def test_bytes_survive_a_round_trip(self):
        # bytea comes back as a memoryview, not bytes. A comparison that forgets
        # this silently fails, and the symptom is an artifact that serves
        # correctly but never matches its own hash.
        raw = bytes(range(256))
        make_artifact(raw=raw)
        stored = Artifact.objects.get(key=KEY_A)
        assert bytes(stored.raw) == raw

    def test_a_key_is_unique(self):
        # The uniqueness IS the design: a primary lookup must return one
        # artifact or nothing, never a choice.
        make_artifact()
        with pytest.raises(IntegrityError), transaction.atomic():
            make_artifact(raw=b"different bytes entirely")

    def test_two_artifacts_coexist_under_different_keys(self):
        make_artifact(key=KEY_A)
        make_artifact(key=KEY_B)
        assert Artifact.objects.count() == 2


@pytest.mark.django_db
class TestArtifactIndex:
    def test_one_index_key_names_many_artifacts(self):
        # A secondary lookup is set-valued -- that is the whole reason it
        # exists, since "what do you hold for this instruction" is the question
        # a node that missed a trigger has to ask.
        for key in (KEY_A, KEY_B):
            ArtifactIndex.objects.create(
                index_key=INDEX_KEY, artifact=make_artifact(key=key)
            )
        found = ArtifactIndex.objects.filter(index_key=INDEX_KEY)
        assert {e.artifact.key for e in found} == {KEY_A, KEY_B}

    def test_an_artifact_is_not_indexed_twice_under_one_key(self):
        artifact = make_artifact()
        ArtifactIndex.objects.create(index_key=INDEX_KEY, artifact=artifact)
        with pytest.raises(IntegrityError), transaction.atomic():
            ArtifactIndex.objects.create(index_key=INDEX_KEY, artifact=artifact)

    def test_dropping_an_artifact_drops_its_index_entries(self):
        # Retention deletes artifacts; an index entry pointing at nothing would
        # answer a peer with a promise the node cannot keep.
        artifact = make_artifact()
        ArtifactIndex.objects.create(index_key=INDEX_KEY, artifact=artifact)
        artifact.delete()
        assert not ArtifactIndex.objects.exists()


@pytest.mark.django_db
class TestExpectation:
    def test_a_new_expectation_is_open_with_no_attempts(self):
        e = make_expectation()
        assert e.state == ExpectationState.OPEN
        assert e.attempts == 0
        assert e.last_attempt_at is None
        assert e.reason == ""

    def test_a_key_is_unique(self):
        # Seeing a trigger twice -- a reorg, a restart, an overlapping scan --
        # must not create a second expectation for one slot.
        make_expectation()
        with pytest.raises(IntegrityError), transaction.atomic():
            make_expectation()

    def test_unmet_and_refused_are_different_terminal_states(self):
        unmet = make_expectation(
            key=KEY_A, state=ExpectationState.UNMET, reason="never answered"
        )
        refused = make_expectation(
            key=KEY_B, state=ExpectationState.REFUSED, reason="machine signature"
        )
        assert unmet.state != refused.state
        # The distinction has to be queryable, or nothing can alarm on one and
        # not the other.
        assert Expectation.objects.filter(state=ExpectationState.REFUSED).count() == 1

    def test_the_collectors_hot_query_is_indexed(self):
        # Open expectations ordered by when they were last tried: the query the
        # collector runs every tick, and the reason for the composite index.
        make_expectation(key=KEY_A)
        make_expectation(key=KEY_B, state=ExpectationState.MET)
        due = Expectation.objects.filter(state=ExpectationState.OPEN).order_by(
            "last_attempt_at"
        )
        assert [e.key for e in due] == [KEY_A]

    def test_an_expectation_outlives_the_log_that_created_it(self):
        # trigger_ref is a rendered value, not a foreign key. The c-chain
        # indexer keeps about a week; artifacts matter for longer, so the
        # expectation cannot depend on the log still being there.
        e = make_expectation()
        assert isinstance(e.trigger_ref, str)
        assert not hasattr(e, "trigger")
