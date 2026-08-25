"""Eviction, driven by lifecycle first and by a clock only as a backstop.

The rule that inverts what both existing collectors assume: **an expectation
outlives the log that created it.** The c-chain indexer keeps roughly a week;
artifacts stay relevant for longer, and the expectation is the record while the
indexer is only how it was discovered. So nothing here is bounded by the
indexer's window, and nothing may be re-derived from chain data to decide
whether it can go.

Every rule is expressed against a condition the chain settles, plus one hard
max-age. The backstop is mandatory rather than defensive: without it, an
extension whose contract stalls -- never marking anything settled -- leaks
storage on every node forever, and the leak is invisible because each individual
record is legitimately still open.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from dal.models import Artifact, Expectation, ExpectationState

logger = logging.getLogger(__name__)

__all__ = ["SweepReport", "sweep"]

TERMINAL = (
    ExpectationState.MET,
    ExpectationState.UNMET,
    ExpectationState.REFUSED,
)


@dataclass
class SweepReport:
    expectations_dropped: int = 0
    artifacts_dropped: int = 0
    open_past_backstop: int = 0

    def __str__(self):
        return (
            f"expectations={self.expectations_dropped} "
            f"artifacts={self.artifacts_dropped} "
            f"open_past_backstop={self.open_past_backstop}"
        )


@transaction.atomic
def sweep(*, now: datetime | None = None, batch: int = 5_000) -> SweepReport:
    """Drop everything past its backstop, artifacts before the rows naming them.

    Order matters. An artifact is deleted first and its expectation second, so a
    sweep interrupted between the two leaves an expectation whose artifact is
    gone -- which the collector treats as work to redo. The opposite order would
    leave an artifact nothing points at, which nothing would ever notice.
    """
    now = now or timezone.now()
    report = SweepReport()

    expired = Expectation.objects.filter(expires_at__lte=now)[:batch]
    keys = list(expired.values_list("key", "state"))
    if not keys:
        return report

    # An OPEN expectation reaching its backstop is not routine: it means the
    # artifact never arrived and never will, and nothing terminal was ever
    # recorded for it. Worth counting separately, because a rising number is a
    # collector that has stopped collecting.
    report.open_past_backstop = sum(
        1 for _, state in keys if state == ExpectationState.OPEN
    )

    deletable = [key for key, _ in keys]
    report.artifacts_dropped, _ = (
        Artifact.objects.filter(key__in=deletable).delete()[0],
        None,
    )
    report.expectations_dropped, _ = (
        Expectation.objects.filter(key__in=deletable).delete()[0],
        None,
    )

    if report.open_past_backstop:
        logger.warning(
            "DAL retention: %d expectation(s) hit the backstop still OPEN",
            report.open_past_backstop,
        )
    logger.info("DAL retention: %s", report)
    return report


def terminal_count() -> int:
    """How many expectations have finished. A health signal, not a rule."""
    return Expectation.objects.filter(state__in=TERMINAL).count()
