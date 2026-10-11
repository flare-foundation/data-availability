"""The registry's calls, checked against the diamond's interface.

A call the diamond does not cut fails only at run time, as a
``FunctionNotFound`` revert, and every other test fakes the registry, so none of
them can see it. These pin each selector against the compiled interface, and
drive the real ``Registry`` through web3's own encoding against a chain that
answers only the calls the interface has.
"""

import pytest
from eth_abi.abi import decode as abi_decode
from eth_abi.abi import encode as abi_encode
from eth_utils.abi import function_abi_to_4byte_selector
from web3 import Web3
from web3.providers.base import BaseProvider

from dal.chain.abi import IS_ALLOWED_PROPOSER, PROPOSER_URL
from dal.chain.registry import Registry

CHANNEL = Web3.to_checksum_address("0x" + "0" * 36 + "c4a1")
PROPOSER = Web3.to_checksum_address("0x" + "0" * 36 + "5e11")
SOURCE_ID = b"BTC".ljust(32, b"\x00")
ACCOUNT_ADDRESS = "bcrt1qexampleaccount"

# From IIWalletPayments as compiled at flare-smart-contracts-v2 e4d6d26c — the
# interface the WalletPayments diamond cuts. Literals, because a selector computed
# from the DAL's own ABI agrees with whatever that ABI says.
SELECTORS = {
    "isAllowedProposer((bytes32,string),address)": "41cac86b",
    "getProposerUrl(address)": "6cb39f40",
}


@pytest.mark.parametrize(
    ("abi", "signature"),
    [
        (IS_ALLOWED_PROPOSER, "isAllowedProposer((bytes32,string),address)"),
        (PROPOSER_URL, "getProposerUrl(address)"),
    ],
)
def test_every_call_is_one_the_diamond_cuts(abi, signature):
    assert function_abi_to_4byte_selector(abi).hex() == SELECTORS[signature]


class FakeDiamond(BaseProvider):
    """Answers eth_call for the selectors above and nothing else.

    Anything else — a removed function, a changed argument list — gets the
    revert a diamond gives a selector it has no facet for.
    """

    def __init__(self, allowed: bool):
        super().__init__()
        self.allowed = allowed
        self.calls: list[tuple[str, bytes]] = []

    def make_request(self, method, params):
        if method == "eth_chainId":
            return {"jsonrpc": "2.0", "id": 1, "result": "0x1"}
        assert method == "eth_call", method
        data = bytes.fromhex(params[0]["data"].removeprefix("0x"))
        selector, args = data[:4].hex(), data[4:]
        self.calls.append((selector, args))

        if selector == SELECTORS["isAllowedProposer((bytes32,string),address)"]:
            result = abi_encode(["bool"], [self.allowed])
        else:
            return {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": 3, "message": f"FunctionNotFound(0x{selector})"},
            }
        return {"jsonrpc": "2.0", "id": 1, "result": "0x" + result.hex()}


def registry_on(chain: FakeDiamond) -> Registry:
    registry = Registry("http://127.0.0.1:1", CHANNEL)
    registry._w3 = Web3(chain)
    return registry


class TestIsAllowed:
    @pytest.mark.parametrize("allowed", [True, False])
    def test_the_answer_is_the_contracts(self, allowed):
        registry = registry_on(FakeDiamond(allowed))
        assert (
            registry.is_allowed(SOURCE_ID, ACCOUNT_ADDRESS, PROPOSER.lower()) is allowed
        )

    def test_it_asks_the_live_check_for_the_named_account(self):
        # The account struct exactly as the request names it, and the
        # proposer — no generation. The lists are read live, so there is none
        # to ask at. One call: nothing resolves the account first.
        chain = FakeDiamond(allowed=True)
        registry_on(chain).is_allowed(SOURCE_ID, ACCOUNT_ADDRESS, PROPOSER)

        assert len(chain.calls) == 1
        (selector, args) = chain.calls[0]
        assert selector == SELECTORS["isAllowedProposer((bytes32,string),address)"]
        account, proposer = abi_decode(["(bytes32,string)", "address"], args)
        assert account == (SOURCE_ID, ACCOUNT_ADDRESS)
        assert Web3.to_checksum_address(proposer) == PROPOSER
        # Exactly two arguments: the head is two words and the string's tail
        # follows, with no third head word where a generation would sit.
        assert len(args) == len(
            abi_encode(
                ["(bytes32,string)", "address"],
                [(SOURCE_ID, ACCOUNT_ADDRESS), PROPOSER],
            )
        )


def test_the_endpoint_is_read_by_proposer_alone():
    class UrlDiamond(FakeDiamond):
        def make_request(self, method, params):
            if method == "eth_call":
                data = bytes.fromhex(params[0]["data"].removeprefix("0x"))
                if data[:4].hex() == SELECTORS["getProposerUrl(address)"]:
                    self.calls.append((data[:4].hex(), data[4:]))
                    result = abi_encode(["string"], ["http://proposer.example"])
                    return {"jsonrpc": "2.0", "id": 1, "result": "0x" + result.hex()}
            return super().make_request(method, params)

    chain = UrlDiamond(allowed=True)
    entry = registry_on(chain).proposer(PROPOSER)
    assert entry.exists and entry.url == "http://proposer.example"
    (selector, args) = chain.calls[0]
    assert selector == SELECTORS["getProposerUrl(address)"]
    (proposer,) = abi_decode(["address"], args)
    assert Web3.to_checksum_address(proposer) == PROPOSER
