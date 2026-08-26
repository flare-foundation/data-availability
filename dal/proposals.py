"""Collecting a proposal package, on demand.

Unlike every other class, a proposal is fetched because somebody asked for it by
hash. The proposer committed to `packageHash` on chain before publishing
anything, so by the time this runs the chain already says both what the bytes
must hash to and — through the submitter of that commitment — whose endpoint to
fetch them from.

Nobody NAMES a proposer in a request here. The caller passes the address the
commitment came from, which is an on-chain fact, so a wrong attribution is not
expressible and an honest 404 can never be recorded against a proposer that
simply never had the hash.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from dal.fetch import FetchError, UnsafeURL, fetch, resolve
from dal.gate.g2 import gate_proposal_package
from dal.gate.result import Refused
from dal.keys import MessageClass
from dal.models import Artifact, ArtifactIndex, Expectation, ExpectationState

logger = logging.getLogger(__name__)

__all__ = ["ProposalOutcome", "collect_proposal"]

# Short by default. A losing proposal becomes unfinalizable the moment the
# eligibility generation bumps, and most proposals in a contest lose.
DEFAULT_TTL = timedelta(hours=6)


@dataclass
class ProposalOutcome:
    admitted: bool
    reason: str = ""
    key: str = ""

    def __str__(self):
        return f"admitted={self.admitted} {self.reason}".strip()


@transaction.atomic
def collect_proposal(
    *,
    registry,
    chain_id: int,
    wallet_id: bytes,
    account_index: int,
    proposer: str,
    package_hash: bytes,
    txid: bytes | None = None,
    generation: int | None = None,
    allow_private: bool = False,
    ttl: timedelta = DEFAULT_TTL,
) -> ProposalOutcome:
    """Fetch one committed package from its proposer, gate it, and store it.

    ``generation`` is optional and, when given, is checked against the registry
    AT THAT GENERATION rather than at latest — a proposal is judged under the
    rules that were in force when its contest opened.
    """
    key = package_hash.hex()
    now = timezone.now()

    entry = registry.proposer(wallet_id, account_index, proposer)
    if not entry.exists or not entry.url:
        return _refuse(
            key,
            now,
            f"proposer {proposer} has no registered endpoint",
            ttl,
            wallet_id,
            account_index,
            proposer,
        )

    if generation is not None and not registry.is_allowed_at(
        wallet_id, account_index, proposer, generation
    ):
        return _refuse(
            key,
            now,
            f"proposer {proposer} was not admitted for generation {generation}",
            ttl,
            wallet_id,
            account_index,
            proposer,
        )

    expectation, _ = Expectation.objects.get_or_create(
        key=key,
        defaults={
            "message_class": MessageClass.PROPOSAL,
            "trigger_ref": f"0x{wallet_id.hex()}/{account_index}",
            "origin": entry.url,
            "params": {
                "proposer": proposer,
                "packageHash": f"0x{key}",
                "generation": generation,
            },
            "first_seen_at": now,
            "expires_at": now + ttl,
        },
    )

    try:
        resolved = resolve(entry.url, allow_private=allow_private)
    except UnsafeURL as exc:
        return _close(
            expectation, ExpectationState.REFUSED, f"unusable endpoint: {exc}"
        )

    try:
        status, body = fetch(resolved, f"/{key}")
    except FetchError as exc:
        expectation.attempts += 1
        expectation.last_attempt_at = now
        expectation.reason = str(exc)
        expectation.save(update_fields=["attempts", "last_attempt_at", "reason"])
        return ProposalOutcome(False, str(exc), key)

    if status == 404:
        # The proposer does not have this hash. NOT a refusal: a commitment can
        # be mined a moment before the package is published, and recording an
        # accusation for that would be the exact mistake the commitment scheme
        # exists to prevent.
        expectation.attempts += 1
        expectation.last_attempt_at = now
        expectation.save(update_fields=["attempts", "last_attempt_at"])
        return ProposalOutcome(False, "not published yet", key)

    if status != 200:
        expectation.attempts += 1
        expectation.last_attempt_at = now
        expectation.reason = f"endpoint answered {status}"
        expectation.save(update_fields=["attempts", "last_attempt_at", "reason"])
        return ProposalOutcome(False, expectation.reason, key)

    verdict = gate_proposal_package(
        body, chain_id=chain_id, package_hash=package_hash, proposer=proposer
    )
    if isinstance(verdict, Refused):
        logger.warning(
            "DAL: REFUSED proposal %s from %s: %s", key, proposer, verdict.reason
        )
        return _close(expectation, ExpectationState.REFUSED, verdict.reason)

    artifact, _ = Artifact.objects.update_or_create(
        key=key,
        defaults={
            "message_class": MessageClass.PROPOSAL,
            "raw": verdict.raw,
            "origin": entry.url,
            "gated_at": now,
            "size_bytes": len(verdict.raw),
        },
    )
    if txid is not None:
        # The secondary index every non-verifier consumer uses: the relay client
        # and the facilitator know a txid, never a package hash.
        ArtifactIndex.objects.get_or_create(index_key=txid.hex(), artifact=artifact)

    expectation.state = ExpectationState.MET
    expectation.attempts += 1
    expectation.last_attempt_at = now
    expectation.reason = ""
    expectation.save(update_fields=["state", "attempts", "last_attempt_at", "reason"])
    return ProposalOutcome(True, "", key)


def _refuse(key, now, reason, ttl, wallet_id, account_index, proposer):
    expectation, _ = Expectation.objects.get_or_create(
        key=key,
        defaults={
            "message_class": MessageClass.PROPOSAL,
            "trigger_ref": f"0x{wallet_id.hex()}/{account_index}",
            "origin": "",
            "params": {"proposer": proposer},
            "first_seen_at": now,
            "expires_at": now + ttl,
        },
    )
    return _close(expectation, ExpectationState.REFUSED, reason)


def _close(expectation, state, reason) -> ProposalOutcome:
    expectation.state = state
    expectation.reason = reason
    expectation.last_attempt_at = timezone.now()
    expectation.save(update_fields=["state", "reason", "last_attempt_at"])
    logger.warning("DAL: proposal %s refused: %s", expectation.key, reason)
    return ProposalOutcome(False, reason, expectation.key)
