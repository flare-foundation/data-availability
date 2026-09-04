"""Reading the proposer registry from the channel contract.

State comes from the contracts directly over RPC, at latest — the DAL keeps no
chain index of its own. For one question that is not good enough, and the
exception is deliberate: **membership is asked at the generation a proposal
binds to**, because a contest has a defined window and judging it against later
state would let a registry edit invalidate a proposal already voted on. The
contract exposes `isAllowedProposerAt` for exactly that.

The endpoint, by contrast, is read at latest and that is fine: a wrong or moved
URL yields bytes that fail the hash and are refused, so it costs a fetch rather
than correctness.

**Two addressing schemes, both current.** An FDC2 `PMWUtxoProposalCheck` request
names an account as `(walletId, accountIndex)`; the TeePayments diamond
addresses it as `PMWMultisigAccount(sourceId, accountAddress)`. Neither is
wrong and neither is going away, so this module joins them with the diamond's
own `getUtxoAccount(walletId, accountIndex)` rather than making the DAL carry
account configuration it would then have to keep in step with a deployment.

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

from dal.chain.abi import GET_UTXO_ACCOUNT, IS_ALLOWED_PROPOSER_AT, PROPOSER_URL

logger = logging.getLogger(__name__)

__all__ = ["ProposerEntry", "Registry", "Submitters"]


@dataclass(frozen=True, slots=True)
class ProposerEntry:
    """Where a proposer serves.

    ``exists`` is derived rather than reported: the diamond's
    ``getProposerUrl`` returns the string alone, and an unregistered proposer
    is an empty one. The admission WINDOW is deliberately not here — it used to
    be, when the registry answered ``(url, exists, activeFrom, activeUntil)``,
    and nothing ever read the two bounds because the only question worth asking
    is ``isAllowedProposerAt`` at a specific generation. Two fields that were
    always ignored are worse than absent: they invite a caller to compare
    against ``now``, which is exactly the judgement this module exists to avoid.
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
        self._accounts: OrderedDict[tuple[bytes, int], tuple[bytes, str]] = (
            OrderedDict()
        )

    def _contract(self, abi):
        return self._w3.eth.contract(address=self._address, abi=[abi])

    def account(self, wallet_id: bytes, account_index: int) -> tuple[bytes, str]:
        """Resolve (walletId, accountIndex) to the diamond's account struct.

        The join between two addressing schemes that both remain correct: an
        FDC2 request names an account positionally, the contract addresses it as
        (sourceId, accountAddress). Reading it from the chain is what keeps this
        service free of per-deployment account configuration.

        Cached because it cannot change for a given pair — a registration is
        immutable once made — and because it would otherwise be an extra RPC on
        every membership check, on the one component that must stay up.
        """
        key = (wallet_id, account_index)
        hit = self._accounts.get(key)
        if hit is not None:
            self._accounts.move_to_end(key)
            return hit

        source_id, address = (
            self._contract(GET_UTXO_ACCOUNT)
            .functions.getUtxoAccount(wallet_id, account_index)
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

    def is_allowed_at(
        self, wallet_id: bytes, account_index: int, proposer: str, generation: int
    ) -> bool:
        """Was this proposer admitted for THAT generation? Never for 'now'."""
        return (
            self._contract(IS_ALLOWED_PROPOSER_AT)
            .functions.isAllowedProposerAt(
                self.account(wallet_id, account_index),
                Web3.to_checksum_address(proposer),
                generation,
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
