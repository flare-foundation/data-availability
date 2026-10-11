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

__all__ = ["ProposalOutcome", "collect_open_proposals", "collect_proposal"]

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
    source_id: bytes,
    sender_address: str,
    proposer: str,
    package_hash: bytes,
    txid: bytes | None = None,
    allow_private: bool = False,
    ttl: timedelta = DEFAULT_TTL,
) -> ProposalOutcome:
    """Fetch one committed package from its proposer, gate it, and store it.

    Only while the proposer is admitted for the account, asked on every attempt
    at latest — the contract reads the proposer lists live when it finalizes,
    so there is no earlier answer to prefer. A proposer that is not admitted
    leaves the expectation open, like a package not yet published: the owner
    can still list it before the proposal is finalized.
    """
    key = package_hash.hex()
    now = timezone.now()

    entry = registry.proposer(proposer)
    trigger_ref = _account_ref(source_id, sender_address)
    if not entry.exists or not entry.url:
        return _refuse(
            key,
            now,
            f"proposer {proposer} has no registered endpoint",
            ttl,
            trigger_ref,
            proposer,
        )

    expectation, _ = Expectation.objects.get_or_create(
        key=key,
        defaults={
            "message_class": MessageClass.PROPOSAL,
            "trigger_ref": trigger_ref,
            "origin": entry.url,
            # The account as well as the proposer, so an expectation opened
            # here rather than by the trigger can be retried by
            # collect_open_proposals, which reads nothing else.
            "params": {
                "proposer": proposer,
                "packageHash": f"0x{key}",
                "sourceId": f"0x{source_id.hex()}",
                "senderAddress": sender_address,
            },
            "first_seen_at": now,
            "expires_at": now + ttl,
        },
    )

    if not registry.is_allowed(source_id, sender_address, proposer):
        # NOT a refusal. A refusal is terminal and never retried, while this
        # answer can change: the lists are the owner's to edit at any time and
        # the contract judges the proposal by them as they stand when it is
        # finalized. Refusing here would withhold, for good, a package the
        # contract may yet accept. Nothing is fetched while it stands.
        expectation.attempts += 1
        expectation.last_attempt_at = now
        expectation.reason = f"proposer {proposer} is not admitted for the account"
        expectation.save(update_fields=["attempts", "last_attempt_at", "reason"])
        return ProposalOutcome(False, expectation.reason, key)

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


def _account_ref(source_id: bytes, sender_address: str) -> str:
    """The account as a trigger reference: ``0x<sourceId>/<senderAddress>``."""
    return f"0x{source_id.hex()}/{sender_address}"


def _refuse(key, now, reason, ttl, trigger_ref, proposer):
    expectation, _ = Expectation.objects.get_or_create(
        key=key,
        defaults={
            "message_class": MessageClass.PROPOSAL,
            "trigger_ref": trigger_ref,
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


def collect_open_proposals(
    *, registry, chain_id: int, allow_private: bool = False, limit: int = 100
) -> list[ProposalOutcome]:
    """Fetch every proposal that has been committed to and not yet collected.

    Driven by expectations rather than by a caller naming a hash: the requests
    are on chain, so the node already knows what it is owed and by whom. A
    proposal that is not published yet stays open and is retried next tick —
    which is the ordinary case, since a commitment is mined before the package
    is disclosed.
    """
    out = []
    open_proposals = Expectation.objects.filter(
        message_class=MessageClass.PROPOSAL, state=ExpectationState.OPEN
    ).order_by("last_attempt_at")[:limit]

    for expectation in open_proposals:
        params = expectation.params
        try:
            # No defaults. An expectation that does not name its account
            # cannot be asked about; a guessed account would get a confident
            # wrong answer from the chain instead of leaving the proposal open.
            source_id = bytes.fromhex(params["sourceId"].removeprefix("0x"))
            sender_address = params["senderAddress"]
            package_hash = bytes.fromhex(params["packageHash"].removeprefix("0x"))
        except KeyError, ValueError:
            logger.warning("DAL: proposal %s has unusable params", expectation.key)
            continue

        out.append(
            collect_proposal(
                registry=registry,
                chain_id=chain_id,
                source_id=source_id,
                sender_address=sender_address,
                proposer=params["proposer"],
                package_hash=package_hash,
                allow_private=allow_private,
            )
        )
    return out
