import copy
import json
from typing import Any, Callable

from django.contrib.postgres.fields import ArrayField
from django.db import models
from eth_utils.crypto import keccak
from web3._utils.contracts import decode_transaction_data
from web3._utils.normalizers import abi_bytes_to_hex

from processing.client.types import FdcAttestationResponse
from processing.utils import prefix_0x, un_prefix_0x

EMPTY_METHOD_IDENTIFIER = "00000000"


def dict_transform(
    data: dict[str, Any], transformators: dict[type, Callable[[Any], Any]]
) -> dict[str, Any]:
    """
    This function performs a deepcopy of input dict, then recursively traverses it and
    performs the transformations as defined in transformators input parameter

    Args:
        data: dictionary that will be transformed
        transformators: mapper of transformators eg {int: lambda x: str(x)} would
            transform all integers to string by applying the str(...) function

    Returns:
        new_data: transformed data
    """

    new_data = copy.deepcopy(data)
    ref_stack: list[dict[str, Any] | list[Any]] = [new_data]
    while ref_stack:
        d = ref_stack.pop()

        if isinstance(d, list):
            for i in range(len(d)):
                if isinstance(d[i], dict) or isinstance(d[i], list):
                    ref_stack.append(d[i])
                if type(d[i]) in transformators:
                    d[i] = transformators[type(d[i])](d[i])

        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, dict) or isinstance(v, list):
                    ref_stack.append(v)
                if type(v) in transformators:
                    d[k] = transformators[type(v)](d[k])

    return new_data


def dict_transform_typescript(data: dict[str, Any]) -> dict[str, Any]:
    # NOTE:(matej) this is needed since javascript number type
    # is a float and will not work correctly with large integers
    return dict_transform(data, {int: lambda x: str(x)})


class AttestationResult(models.Model):
    voting_round_id = models.PositiveBigIntegerField()
    request_hex = models.CharField()
    response_hex = models.CharField()
    abi = models.CharField()  # JSON
    proof = ArrayField(models.CharField())

    def __str__(self):
        return f"Round {self.voting_round_id} - {self.request_hex[:8]}...{self.request_hex[-8:]}"

    @property
    def hash(self):
        return keccak(hexstr=self.response_hex)

    @property
    def response(self):
        abi = json.loads(self.abi)
        a = {"inputs": [abi], "type": "function"}
        c = decode_transaction_data(
            a, EMPTY_METHOD_IDENTIFIER + self.response_hex, [abi_bytes_to_hex]
        )  # type: ignore

        return c["data"]

    @property
    def response_ts(self):
        return dict_transform_typescript(self.response)

    def attestation_type(self) -> str:
        return prefix_0x(un_prefix_0x(self.request_hex)[:64])

    @classmethod
    def from_decoded_dict(cls, attestation_response: FdcAttestationResponse):
        return cls(
            voting_round_id=attestation_response.roundId,
            request_hex=attestation_response.request,
            response_hex=attestation_response.response,
            abi=attestation_response.abi,
            proof=attestation_response.proof,
        )
