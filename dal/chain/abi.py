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

__all__ = ["TEE_INSTRUCTIONS_SENT", "topic0"]

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
