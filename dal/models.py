"""What the DAL stores: expectations, and the bytes that met them.

Two tables and one index table, and the first of them is the one that carries
the design.

An **expectation** is a record that something *should* exist. It is written the
first time its trigger is seen on chain and is never re-derived afterwards,
which is what lets the c-chain indexer keep only about a week of history while
artifacts remain relevant for longer: the indexer is how expectations are
discovered, not where they live.

An **artifact** is the bytes, stored exactly as the origin served them. Every
decoded view elsewhere in this service -- attestation results, feed results --
is a projection over an artifact, never a substitute for one, because a hash or
a signature is over the origin's bytes and a re-encoding is not byte-stable.
"""

from django.db import models

__all__ = ["Artifact", "ArtifactIndex", "Expectation"]


class MessageClass(models.TextChoices):
    """Values are stable and never reused: they appear in stored keys."""

    FTSO_ROUND = "ftso_round", "FTSO round payload"
    FDC_ROUND = "fdc_round", "FDC round payload"
    TEE_ACTION_RESULT = "tee_action_result", "TEE action result"
    PROPOSAL = "proposal", "Proposal package"


class ExpectationState(models.TextChoices):
    OPEN = "open", "Open"
    MET = "met", "Met"
    UNMET = "unmet", "Unmet"
    REFUSED = "refused", "Refused"


class Expectation(models.Model):
    """Something that should exist, and what became of it.

    ``UNMET`` and ``REFUSED`` are both terminal and they are not the same thing.
    Unmet means the origin never answered -- an outage, a censoring proxy, or a
    result that was never produced. Refused means the origin answered with
    something that failed its gate, which is a bug or an attack and should page
    somebody. Both existing collectors record these identically, which is how a
    persistent forgery comes to look like a flaky network.
    """

    key = models.CharField(max_length=64, unique=True)
    message_class = models.CharField(max_length=32, choices=MessageClass)
    # What on chain created this expectation, rendered for the class: an
    # instruction id, or a "protocol/round" pair. Not a foreign key -- the log
    # it came from is dropped long before this row is.
    trigger_ref = models.CharField(max_length=128, db_index=True)
    # Where the artifact should come from. An address for a TEE machine, a
    # configured name for a data-provider client. Recorded even for a G1
    # artifact, where several origins may each be correct and return different
    # bytes, so a disagreement between them is investigable rather than lost.
    origin = models.CharField(max_length=128)
    state = models.CharField(
        max_length=16, choices=ExpectationState, default=ExpectationState.OPEN
    )
    # Starts the give-up window. A pair that is throttled must not advance it:
    # being rate limited is a statement about our request rate, not about the
    # origin's willingness to answer.
    first_seen_at = models.DateTimeField()
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    # Why it ended, for UNMET and REFUSED. Empty while open.
    reason = models.TextField(blank=True, default="")
    # The hard backstop, independent of any on-chain condition. Without one, an
    # extension whose contract stalls leaks storage on every node forever.
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [  # noqa: RUF012
            # The collector's hot query: what is still open and due a retry.
            models.Index(fields=["state", "last_attempt_at"]),
        ]
        verbose_name = "Expectation"
        verbose_name_plural = "Expectations"

    def __str__(self):
        return f"{self.message_class} {self.key[:12]}... ({self.state})"


class Artifact(models.Model):
    """Bytes that passed their gate, stored verbatim.

    ``key`` is 32 bytes as hex whichever kind of key it is -- the hash of the
    content where a commitment exists, the hash of the coordinate tuple where
    one does not -- so the byte-serving API has one shape for every message
    class and never grows a per-type route.
    """

    key = models.CharField(max_length=64, unique=True)
    message_class = models.CharField(max_length=32, choices=MessageClass)
    # Exactly what the origin served. Never a re-encoding: for a G1 artifact the
    # hash is over these bytes and for a G2 artifact the signature is, so a node
    # that re-serialised would serve something failing the gate at the next hop.
    raw = models.BinaryField()
    origin = models.CharField(max_length=128)
    gated_at = models.DateTimeField()
    # Denormalised from the bytes so retention and serving never have to parse.
    size_bytes = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Artifact"
        verbose_name_plural = "Artifacts"

    def __str__(self):
        return f"{self.message_class} {self.key[:12]}... ({self.size_bytes} B)"


class ArtifactIndex(models.Model):
    """A secondary, SET-valued name for artifacts.

    A primary lookup answers "do you have key X" and returns one artifact or
    nothing. A node that missed a trigger has a different question -- "what do
    you hold for this instruction" -- which a primary key cannot express, and
    which is exactly what a peer joining late needs to ask.
    """

    index_key = models.CharField(max_length=64, db_index=True)
    artifact = models.ForeignKey(
        Artifact, on_delete=models.CASCADE, related_name="index_entries"
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["index_key", "artifact"], name="dal_index_entry_unique"
            )
        ]
        verbose_name = "Artifact index entry"
        verbose_name_plural = "Artifact index entries"

    def __str__(self):
        return f"{self.index_key[:12]}... -> {self.artifact_id}"
