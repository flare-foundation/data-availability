"""Reading the proposer registry from the channel contract.

State comes from the contracts directly over RPC, at latest — the DAL keeps no
chain index of its own, and for both questions asked here latest is the right
block rather than an approximation of one:

* **Membership** is `isAllowedProposer`, which is what `finalizeProposal`
  checks, and the contract reads the proposer lists live: a list change applies
  to every proposal finalized after it, a contest under way included. There is
  no earlier state a proposal is judged against, so an answer holds for the
  block it was read at and no longer — which is why a "no" here leaves a
  proposal waiting rather than refused.
* **The endpoint** is read at latest too, and that is fine: a wrong or moved URL
  yields bytes that fail the hash and are refused, so it costs a fetch rather
  than correctness.

**The account is named the way the diamond reads it.** An FDC2
`CspProposalCheck` request carries `senderAddress`, and with the header's
`sourceId` that is the `WalletAccount(sourceId, accountAddress)` struct
`isAllowedProposer` takes — so membership is one call, with no account
resolution in front of it and no per-deployment account configuration here.
"""

import logging
from collections import OrderedDict
from dataclasses import dataclass

from web3 import Web3

from dal.chain.abi import IS_ALLOWED_PROPOSER, PROPOSER_URL

logger = logging.getLogger(__name__)

__all__ = ["ProposerEntry", "Registry", "Submitters"]


@dataclass(frozen=True, slots=True)
class ProposerEntry:
    """Where a proposer serves.

    ``exists`` is derived rather than reported: the diamond's
    ``getProposerUrl`` returns the string alone, and an unregistered proposer
    is an empty one. Admission is deliberately not here. The directory is keyed
    by proposer alone and gates nothing; whether a proposer may propose is a
    per-account question the contract answers from the proposer lists, and
    ``Registry.is_allowed`` asks it. An endpoint that exists is not permission.
    """

    url: str
    exists: bool


class Registry:
    """A read-only view of one channel contract."""

    def __init__(self, rpc_url: str, channel_address: str):
        self._w3 = Web3(Web3.HTTPProvider(rpc_url))
        self._address = Web3.to_checksum_address(channel_address)

    def _contract(self, abi):
        return self._w3.eth.contract(address=self._address, abi=[abi])

    def proposer(self, proposer: str) -> ProposerEntry:
        """Where a proposer serves.

        Endpoint registration is per PROPOSER, not per account: one proposer
        publishes one endpoint for every account it proposes for.
        """
        url = (
            self._contract(PROPOSER_URL)
            .functions.getProposerUrl(Web3.to_checksum_address(proposer))
            .call()
        )
        return ProposerEntry(url=url, exists=bool(url))

    def is_allowed(self, source_id: bytes, sender_address: str, proposer: str) -> bool:
        """May this proposer propose for the account, as the lists stand now?

        The contract's own check: the account's list if it has one, otherwise
        its project's, and a project with no list admits every proposer — as
        does a custodian wallet's account, which has no project, until its
        owner sets an account list. ``finalizeProposal`` reads the same lists
        live, so ``False`` is a statement about this block and not a verdict on
        the proposal: the owner can list the proposer before it is finalized.
        """
        return (
            self._contract(IS_ALLOWED_PROPOSER)
            .functions.isAllowedProposer(
                (source_id, sender_address),
                Web3.to_checksum_address(proposer),
            )
            .call()
        )


def from_settings() -> Registry:
    from django.conf import settings

    if not settings.DAL_RPC_URL or not settings.DAL_CHANNEL_ADDRESS:
        raise RuntimeError(
            "DAL_RPC_URL and DAL_CHANNEL_ADDRESS must be set to resolve proposers"
        )
    return Registry(settings.DAL_RPC_URL, settings.DAL_CHANNEL_ADDRESS)


class Submitters:
    """Who actually sent a transaction.

    Provenance under commit-then-publish rests on this and on nothing else. The
    instruction carries a ``claimBackAddress``, but that is chosen by whoever
    called the hub and can name anybody — so it is a hint about where a refund
    goes, never evidence of authorship. The transaction's sender is the one
    value the caller cannot lie about.
    """

    # Bounded. The collector is a long-running process and every commitment it
    # sees adds an entry, so an unbounded map is a slow leak in the one
    # component that must stay up. Senders are cheap to re-read and a miss costs
    # one RPC call.
    CACHE_LIMIT = 4096

    def __init__(self, rpc_url: str):
        self._w3 = Web3(Web3.HTTPProvider(rpc_url))
        self._cache: OrderedDict[str, str] = OrderedDict()

    def __call__(self, transaction_hash: str) -> str | None:
        key = transaction_hash.removeprefix("0x").lower()
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        try:
            tx = self._w3.eth.get_transaction("0x" + key)
        except Exception as exc:
            logger.warning("DAL: could not read transaction %s: %s", key, exc)
            return None
        sender = tx["from"]
        self._cache[key] = sender
        while len(self._cache) > self.CACHE_LIMIT:
            self._cache.popitem(last=False)
        return sender
