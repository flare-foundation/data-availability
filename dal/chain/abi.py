"""Event definitions the DAL decodes.

Held as literals rather than vendored artifacts because the DAL needs a handful
of *events*, not whole contract interfaces, and a vendored artifact would drift
against a contract this service never calls. Addresses still come from
``FlareContractRegistry`` — a registry answers with an address, never an
interface, so something has to carry the shape.

The signature strings below are canonical: they are what ``topic0`` is the
keccak of, so a typo produces a filter that matches nothing, which is
indistinguishable from a contract that never emitted. Every one of them is
covered by a test that recomputes the topic from the ABI. The functions are
pinned the same way, by selector against the compiled interface, because a
call the diamond does not cut fails only at run time, as ``FunctionNotFound``.
"""

from typing import Any, Final

from eth_utils.abi import event_abi_to_log_topic

__all__ = [
    "CSP_PROPOSAL_CHECK",
    "FDC2_ATTESTATION_REQUEST",
    "GET_CSP_ACCOUNT",
    "IS_ALLOWED_PROPOSER",
    "PROPOSAL_REQUEST_BODY",
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


# CspProposalsFacet.getProposerUrl(address) -> string url
#
# The registry is what makes the pull model possible: without an endpoint on
# chain, proposal packages would be the one artifact that had to be pushed.
# Keyed by the proposer alone and written by the proposer itself, so it answers
# whether or not that proposer is admitted for any account — a node resolving a
# proposer named in an older attestation request needs the endpoint it served
# from, and admission is a separate question (isAllowedProposer, below).
PROPOSER_URL: Final[dict[str, Any]] = {
    "name": "getProposerUrl",
    "type": "function",
    "stateMutability": "view",
    "inputs": [{"name": "proposer", "type": "address"}],
    "outputs": [{"name": "url", "type": "string"}],
}

# CspInstructionsFacet.getCspAccount(address,bytes32,uint32) -> WalletAccount
#
# The diamond addresses an account by (sourceId, accountAddress); an FDC2
# CspProposalCheck request names it as (walletRegistry, walletId, accountIndex).
# This is the join, and reading it from the chain is what keeps the DAL free of
# per-deployment account configuration: the triple is already in the request,
# and the contract turns it into the struct its own reads expect.
#
# The REGISTRY is the third of those, and it is not decoration: wallet ids of
# different registries may collide, so (walletId, accountIndex) alone no longer
# names one account. It is also requester-supplied and therefore attacker-chosen
# — naming a registry you control is how you would try to be resolved to an
# account you own. Nothing here decides anything on it; the verifier answers
# only about its configured registry and the contract checks again.
GET_CSP_ACCOUNT: Final[dict[str, Any]] = {
    "name": "getCspAccount",
    "type": "function",
    "stateMutability": "view",
    "inputs": [
        {"name": "walletRegistry", "type": "address"},
        {"name": "walletId", "type": "bytes32"},
        {"name": "accountIndex", "type": "uint32"},
    ],
    "outputs": [
        {
            "name": "",
            "type": "tuple",
            "components": [
                {"name": "sourceId", "type": "bytes32"},
                {"name": "accountAddress", "type": "string"},
            ],
        }
    ],
}

# CspProposalsFacet.isAllowedProposer((bytes32,string),address) -> bool
#
# The check finalizeProposal makes, asked the way it makes it: the account's
# proposer list if it has one, otherwise its project's, and a project with no
# list admits every proposer. The lists are read live, so there is no
# generation to ask at — a list change applies to every proposal finalized
# after it, a contest under way included.
IS_ALLOWED_PROPOSER: Final[dict[str, Any]] = {
    "name": "isAllowedProposer",
    "type": "function",
    "stateMutability": "view",
    "inputs": [
        {
            "name": "account",
            "type": "tuple",
            "components": [
                {"name": "sourceId", "type": "bytes32"},
                {"name": "accountAddress", "type": "string"},
            ],
        },
        {"name": "proposer", "type": "address"},
    ],
    "outputs": [{"name": "", "type": "bool"}],
}


# The FDC2 attestation request, as the hub encodes it into the instruction's
# `message`: abi.encode(Fdc2AttestationRequest).
#
# This is what makes a proposal's trigger free. The hub turns a request into a
# TeeInstructionsSent instruction — the very event already indexed for machine
# results — so recognising a proposal expectation is decoding a message the node
# is reading anyway, not watching a second source.
FDC2_ATTESTATION_REQUEST: Final[dict[str, Any]] = {
    "name": "request",
    "type": "tuple",
    "components": [
        {
            "name": "header",
            "type": "tuple",
            "components": [
                {"name": "attestationType", "type": "bytes32"},
                {"name": "sourceId", "type": "bytes32"},
                {"name": "thresholdBIPS", "type": "uint16"},
                {"name": "proofOwner", "type": "address"},
            ],
        },
        {"name": "requestBody", "type": "bytes"},
    ],
}

# The request body of CspProposalCheck. `packageHash` is the commitment the
# proposer made before publishing anything.
#
# `walletRegistry` LEADS, and it was not there before the control plane was
# split from the execution plane: an account is identified by the triple
# (walletRegistry, walletId, accountIndex), because wallet ids of different
# registries may collide. Decoding without it silently shifts every later field
# by one word, and the decode then fails rather than lying — which is the only
# reason this was cheap to find.
PROPOSAL_REQUEST_BODY: Final[list[str]] = [
    "address",  # walletRegistry
    "bytes32",  # walletId
    "uint32",  # accountIndex
    "uint64",  # sequencePosition
    "uint32",  # attempt
    "uint64",  # eligibleGeneration
    "bytes32",  # packageHash
]


def attestation_type(name: str) -> bytes:
    """An attestation type is its name, right-padded to 32 bytes."""
    raw = name.encode("ascii")
    if len(raw) > 32:
        raise ValueError(f"attestation type {name!r} is longer than 32 bytes")
    return raw.ljust(32, b"\x00")


CSP_PROPOSAL_CHECK: Final = attestation_type("CspProposalCheck")
