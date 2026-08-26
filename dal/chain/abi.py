"""Event definitions the DAL decodes.

Held as literals rather than vendored artifacts because the DAL needs a handful
of *events*, not whole contract interfaces, and a vendored artifact would drift
against a contract this service never calls. Addresses still come from
``FlareContractRegistry`` — a registry answers with an address, never an
interface, so something has to carry the shape.

The signature strings below are canonical: they are what ``topic0`` is the
keccak of, so a typo produces a filter that matches nothing, which is
indistinguishable from a contract that never emitted. Every one of them is
covered by a test that recomputes the topic from the ABI.
"""

from typing import Any, Final

from eth_utils.abi import event_abi_to_log_topic

__all__ = [
    "IS_ALLOWED_PROPOSER_AT",
    "PROPOSER_URL",
    "TEE_INSTRUCTIONS_SENT",
    "topic0",
]

# TeeInstructionsSent(uint256 indexed extensionId, bytes32 indexed instructionId,
#   uint32 indexed rewardEpochId, (address teeId, address teeProxyId, string url)[] teeMachines,
#   bytes32 opType, bytes32 opCommand, bytes message, address[] cosigners,
#   uint64 cosignersThreshold, address claimBackAddress, uint256 fee)
#
# The machine tuples are the reason this event is enough on its own: it names
# every origin AND both identities the gate recovers against, as they stood when
# the instruction was sent. No registry lookup, and no question of reading state
# at the wrong block.
TEE_INSTRUCTIONS_SENT: Final[dict[str, Any]] = {
    "name": "TeeInstructionsSent",
    "type": "event",
    "anonymous": False,
    "inputs": [
        {"name": "extensionId", "type": "uint256", "indexed": True},
        {"name": "instructionId", "type": "bytes32", "indexed": True},
        {"name": "rewardEpochId", "type": "uint32", "indexed": True},
        {
            "name": "teeMachines",
            "type": "tuple[]",
            "indexed": False,
            "components": [
                {"name": "teeId", "type": "address"},
                {"name": "teeProxyId", "type": "address"},
                {"name": "url", "type": "string"},
            ],
        },
        {"name": "opType", "type": "bytes32", "indexed": False},
        {"name": "opCommand", "type": "bytes32", "indexed": False},
        {"name": "message", "type": "bytes", "indexed": False},
        {"name": "cosigners", "type": "address[]", "indexed": False},
        {"name": "cosignersThreshold", "type": "uint64", "indexed": False},
        {"name": "claimBackAddress", "type": "address", "indexed": False},
        {"name": "fee", "type": "uint256", "indexed": False},
    ],
}


def topic0(event_abi: dict[str, Any]) -> str:
    """The log topic for an event, bare and lowercase, as the indexer stores it."""
    return event_abi_to_log_topic(event_abi).hex()


# UtxoInstructionChannel.proposerUrl(bytes32,uint32,address)
#   -> (string url, bool exists, uint64 activeFrom, uint64 activeUntil)
#
# The registry is what makes the pull model possible: without an endpoint on
# chain, proposal packages would be the one artifact that had to be pushed.
# Answers for DEACTIVATED proposers too, deliberately — a node resolving a
# proposer named in an older attestation request needs the endpoint it served
# from, and whether it is still admitted is a separate question.
PROPOSER_URL: Final[dict[str, Any]] = {
    "name": "proposerUrl",
    "type": "function",
    "stateMutability": "view",
    "inputs": [
        {"name": "walletId", "type": "bytes32"},
        {"name": "accountIndex", "type": "uint32"},
        {"name": "proposer", "type": "address"},
    ],
    "outputs": [
        {"name": "url", "type": "string"},
        {"name": "exists", "type": "bool"},
        {"name": "activeFrom", "type": "uint64"},
        {"name": "activeUntil", "type": "uint64"},
    ],
}

# UtxoInstructionChannel.isAllowedProposerAt(bytes32,uint32,address,uint64)
#
# Membership is asked AT A GENERATION, never at latest: a proposal names the
# generation it binds to, and judging it against state at some later moment
# would let a registry edit invalidate a proposal already voted on.
IS_ALLOWED_PROPOSER_AT: Final[dict[str, Any]] = {
    "name": "isAllowedProposerAt",
    "type": "function",
    "stateMutability": "view",
    "inputs": [
        {"name": "walletId", "type": "bytes32"},
        {"name": "accountIndex", "type": "uint32"},
        {"name": "proposer", "type": "address"},
        {"name": "generation", "type": "uint64"},
    ],
    "outputs": [{"name": "", "type": "bool"}],
}
