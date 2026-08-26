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
"""

import logging
from dataclasses import dataclass

from web3 import Web3

from dal.chain.abi import IS_ALLOWED_PROPOSER_AT, PROPOSER_URL

logger = logging.getLogger(__name__)

__all__ = ["ProposerEntry", "Registry"]


@dataclass(frozen=True, slots=True)
class ProposerEntry:
    url: str
    exists: bool
    active_from: int
    active_until: int


class Registry:
    """A read-only view of one channel contract."""

    def __init__(self, rpc_url: str, channel_address: str):
        self._w3 = Web3(Web3.HTTPProvider(rpc_url))
        self._address = Web3.to_checksum_address(channel_address)

    def _contract(self, abi):
        return self._w3.eth.contract(address=self._address, abi=[abi])

    def proposer(
        self, wallet_id: bytes, account_index: int, proposer: str
    ) -> ProposerEntry:
        """Where a proposer serves, and the window it was admitted for."""
        url, exists, active_from, active_until = (
            self._contract(PROPOSER_URL)
            .functions.proposerUrl(
                wallet_id, account_index, Web3.to_checksum_address(proposer)
            )
            .call()
        )
        return ProposerEntry(url, exists, active_from, active_until)

    def is_allowed_at(
        self, wallet_id: bytes, account_index: int, proposer: str, generation: int
    ) -> bool:
        """Was this proposer admitted for THAT generation? Never for 'now'."""
        return (
            self._contract(IS_ALLOWED_PROPOSER_AT)
            .functions.isAllowedProposerAt(
                wallet_id,
                account_index,
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
