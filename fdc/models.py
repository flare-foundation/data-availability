from django.contrib.postgres.fields import ArrayField
from django.db import models
from eth_utils.crypto import keccak

from processing.client.types import FdcAttestationResponse


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

    @classmethod
    def from_decoded_dict(cls, dict: FdcAttestationResponse):
        return cls(
            voting_round_id=dict.roundId,
            request_hex=dict.request,
            response_hex=dict.response,
            abi=dict.abi,
            proof=dict.proof,
        )
