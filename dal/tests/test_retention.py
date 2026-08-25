"""Retention, against a real database."""

from datetime import timedelta

import pytest
from django.utils import timezone

from dal.models import Artifact, ArtifactIndex, Expectation, ExpectationState
from dal.retention import sweep

KEY_A = "aa" * 32
KEY_B = "bb" * 32


def make_pair(key, *, expired: bool, state=ExpectationState.MET, with_artifact=True):
    now = timezone.now()
    expires = now - timedelta(minutes=1) if expired else now + timedelta(days=7)
    Expectation.objects.create(
        key=key,
        message_class="tee_action_result",
        trigger_ref="0x" + "11" * 32 + "#threshold",
        origin="machine-a",
        state=state,
        first_seen_at=now - timedelta(hours=1),
        expires_at=expires,
    )
    if with_artifact:
        artifact = Artifact.objects.create(
            key=key,
            message_class="tee_action_result",
            raw=b"bytes",
            origin="http://93.184.216.34/",
            gated_at=now,
            size_bytes=5,
        )
        ArtifactIndex.objects.create(index_key="cc" * 32, artifact=artifact)


@pytest.mark.django_db
class TestSweep:
    def test_nothing_expired_is_a_no_op(self):
        make_pair(KEY_A, expired=False)
        report = sweep()
        assert (report.expectations_dropped, report.artifacts_dropped) == (0, 0)
        assert Artifact.objects.count() == 1

    def test_an_expired_pair_goes_together(self):
        make_pair(KEY_A, expired=True)
        report = sweep()
        assert report.expectations_dropped == 1
        assert not Artifact.objects.exists()
        assert not Expectation.objects.exists()

    def test_index_entries_go_with_their_artifact(self):
        # An index entry pointing at a deleted artifact would answer a peer with
        # a promise the node cannot keep.
        make_pair(KEY_A, expired=True)
        sweep()
        assert not ArtifactIndex.objects.exists()

    def test_only_the_expired_are_touched(self):
        make_pair(KEY_A, expired=True)
        make_pair(KEY_B, expired=False)
        sweep()
        assert [a.key for a in Artifact.objects.all()] == [KEY_B]

    def test_an_open_expectation_at_its_backstop_is_counted_separately(self):
        # Not routine: the artifact never arrived and nothing terminal was
        # recorded. A rising count here is a collector that has stopped
        # collecting, which otherwise looks exactly like a quiet chain.
        make_pair(KEY_A, expired=True, state=ExpectationState.OPEN, with_artifact=False)
        report = sweep()
        assert report.open_past_backstop == 1

    def test_a_terminal_expectation_at_its_backstop_is_not_alarming(self):
        make_pair(KEY_A, expired=True, state=ExpectationState.MET)
        assert sweep().open_past_backstop == 0

    def test_retention_never_consults_the_indexer_window(self):
        # An expectation older than the c-chain indexer's history is dropped on
        # its OWN backstop, not because the log that created it is gone. This is
        # the rule that lets a week of logs support a fortnight of artifacts.
        now = timezone.now()
        Expectation.objects.create(
            key=KEY_A,
            message_class="tee_action_result",
            trigger_ref="0x" + "11" * 32 + "#threshold",
            origin="machine-a",
            state=ExpectationState.MET,
            first_seen_at=now - timedelta(days=30),
            expires_at=now + timedelta(days=1),
        )
        assert sweep().expectations_dropped == 0
        assert Expectation.objects.count() == 1
