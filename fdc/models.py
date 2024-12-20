import json

from django.contrib.postgres.fields import ArrayField
from django.db import models
from eth_utils.crypto import keccak
from web3._utils.contracts import decode_transaction_data
from web3._utils.normalizers import abi_bytes_to_hex

from processing.client.types import FdcAttestationResponse

EMPTY_METHOD_IDENTIFIER = "00000000"


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

        data = c["data"]

        ref_stack: list[dict] = [data]
        while ref_stack:
            d = ref_stack.pop()

            for k, v in d.items():
                if isinstance(v, dict):
                    ref_stack.append(v)
                if isinstance(v, list):
                    for i in range(len(v)):
                        if type(v[i]) is int:
                            d[k][i] = str(d[k][i])
                if type(v) is int:
                    d[k] = str(d[k])

        return data

    @classmethod
    def from_decoded_dict(cls, attestation_response: FdcAttestationResponse):
        return cls(
            voting_round_id=attestation_response.roundId,
            request_hex=attestation_response.request,
            response_hex=attestation_response.response,
            abi=attestation_response.abi,
            proof=attestation_response.proof,
        )
