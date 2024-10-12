import re

from web3 import Web3


def prefix_0x(to_prefix: str) -> str:
    if len(to_prefix) >= 2:
        if to_prefix[:2] == "0x":
            return to_prefix
    return f"0x{to_prefix}"


def is_debug_file(filename: str) -> bool:
    pattern = re.compile(r"^(.*\.dbg\.json$).*$")
    found = pattern.match(filename)
    return found is not None


def is_method_id(maybe_method_id: str) -> bool:
    pattern = re.compile(r"^((0x)?[a-fA-F0-9]{8})$")
    found = pattern.match(maybe_method_id)
    return found is not None


def to_method_id(method_signature: str) -> str:
    return Web3.keccak(text=method_signature).hex()[2:10]


def extract_method_id_from_input(input: str) -> str:
    unprefixed = un_prefix_0x(input)
    if len(unprefixed) >= 8:
        return unprefixed[:8]
    return ""


def un_prefix_0x(to_unprefixed: str) -> str:
    if len(to_unprefixed) >= 2:
        if to_unprefixed[:2] == "0x":
            return to_unprefixed[2:]
    return to_unprefixed


def event_signature(event_abi: dict) -> str:
    params = ",".join([a["type"] for a in event_abi["inputs"]])
    return un_prefix_0x(Web3.keccak(text=event_abi["name"] + "(" + params + ")").hex())
