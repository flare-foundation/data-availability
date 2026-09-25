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

**Two addressing schemes, both current.** An FDC2 `CspProposalCheck` request
names an account as `(walletRegistry, walletId, accountIndex)`; the TeePayments
diamond addresses it as `WalletAccount(sourceId, accountAddress)`. Neither is
wrong and neither is going away, so this module joins them with the diamond's
own `getCspAccount(walletRegistry, walletId, accountIndex)` rather than making
the DAL carry account configuration it would then have to keep in step with a
deployment.

The registry leads that triple because wallet ids of different registries may
collide: a wallet id alone stopped naming one account when custody moved onto
its own registries, so it is part of the key here and part of the cache key.

That join is also what this module got wrong until 2026-09-05: it called
`proposerUrl(bytes32,uint32,address)`, a pre-diamond signature that no facet
implements, so every collection attempt died on `FunctionNotFound(0x3be80a1b)`
before it could fetch anything. The failure was invisible in the obvious place —
the artifact was published and served correctly the whole time — and surfaced
only as a verifier 404.
"""

import logging
from collections import OrderedDict
from dataclasses import dataclass

from web3 import Web3

from dal.chain.abi import GET_CSP_ACCOUNT, IS_ALLOWED_PROPOSER, PROPOSER_URL

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

    # Bounded for the same reason Submitters' cache is: this is a long-running
    # collector, and one entry per account it ever sees is a slow leak.
    ACCOUNT_CACHE_LIMIT = 256

    def __init__(self, rpc_url: str, channel_address: str):
        self._w3 = Web3(Web3.HTTPProvider(rpc_url))
        self._address = Web3.to_checksum_address(channel_address)
        self._accounts: OrderedDict[tuple[str, bytes, int], tuple[bytes, str]] = (
            OrderedDict()
        )

    def _contract(self, abi):
        return self._w3.eth.contract(address=self._address, abi=[abi])

    def account(
        self, wallet_registry: str, wallet_id: bytes, account_index: int
    ) -> tuple[bytes, str]:
        """Resolve (walletRegistry, walletId, accountIndex) to the account struct.

        The join between two addressing schemes that both remain correct: an
        FDC2 request names an account positionally, the contract addresses it as
        (sourceId, accountAddress). Reading it from the chain is what keeps this
        service free of per-deployment account configuration.

        The registry is requester-supplied and so attacker-chosen. It is safe to
        resolve on: the answer is only ever an account struct, and whether that
        account may be spoken for is decided by the verifier against its own
        configured registry and by the contract when it finalizes. What is NOT
        safe is dropping it, which is what an older two-part key did.

        Cached because it cannot change for a given triple — a registration is
        immutable once made — and because it would otherwise be an extra RPC on
        every membership check, on the one component that must stay up.
        """
        key = (wallet_registry, wallet_id, account_index)
        hit = self._accounts.get(key)
        if hit is not None:
            self._accounts.move_to_end(key)
            return hit

        source_id, address = (
            self._contract(GET_CSP_ACCOUNT)
            .functions.getCspAccount(
                Web3.to_checksum_address(wallet_registry), wallet_id, account_index
            )
            .call()
        )
        self._accounts[key] = (source_id, address)
        while len(self._accounts) > self.ACCOUNT_CACHE_LIMIT:
            self._accounts.popitem(last=False)
        return source_id, address

    def proposer(
        self, wallet_id: bytes, account_index: int, proposer: str
    ) -> ProposerEntry:
        """Where a proposer serves.

        Endpoint registration is per PROPOSER, not per account — the account
        arguments are kept in the signature because callers have them and
        because the account is what the membership question needs, not because
        this read consults them.
        """
        url = (
            self._contract(PROPOSER_URL)
            .functions.getProposerUrl(Web3.to_checksum_address(proposer))
            .call()
        )
        return ProposerEntry(url=url, exists=bool(url))

    def is_allowed(
        self,
        wallet_registry: str,
        wallet_id: bytes,
        account_index: int,
        proposer: str,
    ) -> bool:
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
                self.account(wallet_registry, wallet_id, account_index),
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
