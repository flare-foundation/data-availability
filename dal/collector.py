"""The collection tick: what is open, fetch it, gate it, record what happened.

Driven by **open expectations** rather than by rescanning chain data every tick.
The query names what is missing instead of re-deriving it, which is also what
lets an expectation outlive the log that created it.

The outcome taxonomy is ported from the explorer's poller and extended by one
case. Two of these distinctions are load-bearing and were evidently learned the
hard way:

* **Throttling does not consume the give-up budget.** A 429 is a statement about
  our request rate, not about the origin's willingness to answer. Conflating
  them abandons pairs that would have succeeded.
* **Refusal is not failure.** The explorer has no REFUSED state because it has
  no gate. An origin that answers with something inadmissible is a bug or an
  attack; an origin that does not answer is an outage. Recording them alike is
  how a persistent forgery comes to look like a flaky network.
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final, Protocol

from django.db import transaction
from django.utils import timezone

from dal.fetch import FetchError, Resolved, UnsafeURL, fetch, resolve
from dal.gate.result import Admitted, Refused, Verdict
from dal.models import Artifact, ArtifactIndex, Expectation, ExpectationState

logger = logging.getLogger(__name__)

__all__ = ["Outcome", "TickReport", "collect_once"]

GIVE_UP_AFTER: Final = timedelta(minutes=30)


class Outcome(StrEnum):
    FETCHED = "fetched"
    NOT_READY = "not_ready"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    GAVE_UP = "gave_up"
    REFUSED = "refused"


@dataclass
class TickReport:
    """What one pass over the open expectations did. Logged, and worth alarming on."""

    counts: dict[str, int] = field(default_factory=dict)

    def record(self, outcome: Outcome) -> None:
        self.counts[outcome] = self.counts.get(outcome, 0) + 1

    def __str__(self):
        if not self.counts:
            return "nothing open"
        return " ".join(f"{k}={v}" for k, v in sorted(self.counts.items()))


class Gate(Protocol):
    """Decides whether fetched bytes may enter the store."""

    def __call__(self, expectation: Expectation, raw: bytes) -> Verdict: ...


class Fetcher(Protocol):
    """Fetches one expectation's artifact. Separated so the tick is testable."""

    def __call__(
        self, expectation: Expectation, resolved: Resolved
    ) -> tuple[int, bytes]: ...


def _default_fetcher(expectation: Expectation, resolved: Resolved):
    return fetch(resolved, _path_for(expectation))


def _path_for(expectation: Expectation) -> str:
    # Only the TEE class is wired for now; the others arrive with their own
    # collectors. Raising here rather than defaulting keeps a new message class
    # from silently fetching the wrong URL.
    if expectation.message_class == "tee_action_result":
        instruction, _, tag = expectation.trigger_ref.partition("#")
        return f"/action/result/{instruction}?submissionTag={tag}"
    raise NotImplementedError(
        f"no fetch path for message class {expectation.message_class!r}"
    )


def collect_once(
    *,
    gate: Gate,
    origin_url: Callable[[Expectation], str],
    index_keys: Callable[[Expectation], Iterable[bytes]] = lambda _: (),
    fetcher: Fetcher = _default_fetcher,
    allow_private: bool = False,
    give_up_after: timedelta = GIVE_UP_AFTER,
    now: datetime | None = None,
    limit: int = 500,
) -> TickReport:
    """Run one pass over the open expectations.

    ``origin_url`` resolves an expectation to its origin's endpoint -- a chain
    read, which is why it is injected rather than performed here.
    """
    now = now or timezone.now()
    report = TickReport()
    give_up_before = now - give_up_after

    resolved_cache: dict[str, Resolved | None] = {}
    throttled: set[str] = set()

    due = Expectation.objects.filter(state=ExpectationState.OPEN).order_by(
        "last_attempt_at"
    )[:limit]

    for expectation in due:
        outcome = _collect_one(
            expectation,
            gate=gate,
            origin_url=origin_url,
            index_keys=index_keys,
            fetcher=fetcher,
            allow_private=allow_private,
            now=now,
            give_up_before=give_up_before,
            resolved_cache=resolved_cache,
            throttled=throttled,
        )
        report.record(outcome)

    logger.info("DAL collection: %s", report)
    return report


def _collect_one(
    expectation: Expectation,
    *,
    gate: Gate,
    origin_url: Callable[[Expectation], str],
    index_keys: Callable[[Expectation], Iterable[bytes]],
    fetcher: Fetcher,
    allow_private: bool,
    now: datetime,
    give_up_before: datetime,
    resolved_cache: dict[str, Resolved | None],
    throttled: set[str],
) -> Outcome:
    # The give-up check comes first: an expectation past its window must not
    # cost another request, however cheap.
    if expectation.first_seen_at <= give_up_before:
        return _close(expectation, ExpectationState.UNMET, "gave up waiting", now)

    url = origin_url(expectation)

    if url in throttled:
        # Already 429'd by this host in this tick. The per-IP limit means
        # another call would be throttled too, so back off without touching the
        # attempt count -- a throttled call is not an attempt the origin saw.
        return Outcome.RATE_LIMITED

    if url not in resolved_cache:
        try:
            resolved_cache[url] = resolve(url, allow_private=allow_private)
        except UnsafeURL as exc:
            # Not retryable and not the origin's outage: the URL itself is
            # inadmissible, so the expectation ends refused rather than waiting
            # out a give-up window it can never survive.
            logger.warning("DAL: refusing origin %s: %s", url, exc)
            resolved_cache[url] = None
    resolved = resolved_cache[url]
    if resolved is None:
        return _close(
            expectation, ExpectationState.REFUSED, f"unusable origin {url}", now
        )

    try:
        status, body = fetcher(expectation, resolved)
    except FetchError as exc:
        return _attempted(expectation, now, Outcome.ERROR, str(exc))

    if status == 404:
        # The proxy has no result yet. Expected, and the common case early in an
        # instruction's life.
        return _attempted(expectation, now, Outcome.NOT_READY, "")

    if status == 429:
        throttled.add(url)
        return Outcome.RATE_LIMITED

    if status != 200:
        return _attempted(expectation, now, Outcome.ERROR, f"origin answered {status}")

    verdict = gate(expectation, body)
    if isinstance(verdict, Refused):
        logger.warning(
            "DAL: REFUSED %s from %s: %s", expectation.key, url, verdict.reason
        )
        return _close(expectation, ExpectationState.REFUSED, verdict.reason, now)

    _store(expectation, verdict, url, index_keys(expectation), now)
    return Outcome.FETCHED


@transaction.atomic
def _store(
    expectation: Expectation,
    admitted: Admitted,
    origin: str,
    index_keys: Iterable[bytes],
    now: datetime,
) -> None:
    """Write the bytes and close the expectation, together or not at all.

    Atomic because the two halves are one fact. An artifact stored under an
    expectation still marked open would be re-fetched and re-gated forever; an
    expectation closed without its artifact is a node claiming to hold something
    it does not.
    """
    artifact, _ = Artifact.objects.update_or_create(
        key=admitted.key.hex(),
        defaults={
            "message_class": expectation.message_class,
            "raw": admitted.raw,
            "origin": origin,
            "gated_at": now,
            "size_bytes": len(admitted.raw),
        },
    )
    for index_key in index_keys:
        ArtifactIndex.objects.get_or_create(
            index_key=index_key.hex(), artifact=artifact
        )

    expectation.state = ExpectationState.MET
    expectation.attempts += 1
    expectation.last_attempt_at = now
    expectation.reason = ""
    expectation.save(update_fields=["state", "attempts", "last_attempt_at", "reason"])


def _attempted(
    expectation: Expectation, now: datetime, outcome: Outcome, reason: str
) -> Outcome:
    expectation.attempts += 1
    expectation.last_attempt_at = now
    if reason:
        expectation.reason = reason
    expectation.save(update_fields=["attempts", "last_attempt_at", "reason"])
    return outcome


def _close(
    expectation: Expectation, state: ExpectationState, reason: str, now: datetime
) -> Outcome:
    expectation.state = state
    expectation.reason = reason
    expectation.last_attempt_at = now
    expectation.save(update_fields=["state", "reason", "last_attempt_at"])
    return Outcome.REFUSED if state == ExpectationState.REFUSED else Outcome.GAVE_UP
