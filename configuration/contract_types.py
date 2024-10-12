import json
from typing import Self

from attrs import field, frozen
from django.conf import settings
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.types import ABI, ABIEvent, ABIFunction

from processing.utils import un_prefix_0x


def abi_from_file_location(file_location):
    return json.load(open(file_location))["abi"]


def event_signature(event_abi: ABIEvent) -> str:
    params = ",".join([a["type"] for a in event_abi["inputs"]])  # type: ignore
    return un_prefix_0x(Web3.keccak(text=event_abi["name"] + "(" + params + ")").hex())  # type: ignore


def function_signature(function_name: str) -> str:
    return Web3.keccak(text=function_name).hex()[2:10]


@frozen
class Event:
    name: str
    abi: ABIEvent
    contract: "Contract"
    signature: str = field(init=False)

    def __str__(self) -> str:
        return f"Event: {self.name}, signature: {self.signature}"

    def __repr__(self) -> str:
        return f"Event: {self.name}, signature: {self.signature}"

    def __attrs_post_init__(self):
        object.__setattr__(self, "signature", event_signature(self.abi))


@frozen
class Function:
    name: str
    abi: ABIFunction
    contract: "Contract"
    signature: str = field(init=False)

    def to_full_name(self):
        assert "inputs" in self.abi
        inputs = [i["type"] for i in self.abi["inputs"]]  # type: ignore
        return f"{self.name}({','.join(inputs)})"

    def __str__(self) -> str:
        return f"Function: {self.to_full_name()}, signature: {self.signature}"

    def __repr__(self) -> str:
        return f"Function: {self.to_full_name()}, signature: {self.signature}"

    def __attrs_post_init__(self):
        object.__setattr__(self, "signature", function_signature(self.to_full_name()))


@frozen
class Contract:
    name: str
    address: ChecksumAddress
    abi: ABI = field(converter=abi_from_file_location)
    events: dict[str, Event] = field(init=False)
    functions: dict[str, Function] = field(init=False)

    def __str__(self) -> str:
        return f"Contract: {self.name}, addr.: {self.address}, events: {self.events}, functions: {self.functions}"

    def __repr__(self) -> str:
        return f"Contract: {self.name}, addr.: {self.address}, events: {self.events}, functions: {self.functions}"

    def __attrs_post_init__(self):
        events = {}
        functions = {}
        for entry in self.abi:
            assert "type" in entry
            if entry["type"] == "event":
                assert "name" in entry
                events[entry["name"]] = Event(entry["name"], entry, self)
            elif entry["type"] == "function":
                assert "name" in entry
                functions[entry["name"]] = Function(entry["name"], entry, self)
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "functions", functions)


@frozen
class Contracts:
    Relay: Contract

    @classmethod
    def default(cls) -> Self:
        attr_names = [a.name for a in cls.__attrs_attrs__]  # type: ignore
        with open(f"configuration/chain/{settings.CONFIG_MODULE}/contracts.json") as f:
            contracts = {c["name"]: c["address"] for c in json.load(f)}

            kwargs = {}

            for name in attr_names:
                kwargs[name] = None
                if name in contracts:
                    kwargs[name] = Contract(
                        name,
                        contracts[name],
                        f"configuration/chain/{settings.CONFIG_MODULE}/artifacts/{name}.json",
                    )

            return cls(**kwargs)
