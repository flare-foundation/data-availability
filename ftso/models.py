from typing import ClassVar

from django.db import models
from eth_abi.abi import encode
from web3 import Web3

from configuration.config import config
from processing.client.types import FtsoRandomResponse, FtsoVotingResponse
from processing.utils import un_prefix_0x


class FeedResult(models.Model):
    voting_round_id = models.PositiveBigIntegerField()
    feed_id = models.CharField(max_length=42)

    value = models.BigIntegerField()
    turnout_bips = models.PositiveBigIntegerField()
    decimals = models.IntegerField()

    # TODO: get this from contract versioning
    STRUCT_ABI: ClassVar = {
        "components": [
            {"internalType": "uint32", "name": "votingRoundId", "type": "uint32"},
            {"internalType": "bytes21", "name": "id", "type": "bytes21"},
            {"internalType": "int32", "name": "value", "type": "int32"},
            {"internalType": "uint16", "name": "turnoutBIPS", "type": "uint16"},
            {"internalType": "int8", "name": "decimals", "type": "int8"},
        ],
        "internalType": "struct IFtsoFeedPublisher.Feed",
        "name": "_feed",
        "type": "tuple",
    }

    def __str__(self):
        return f"{self.voting_round_id} - {self.representation} - {self.feed_id} - {self.value}"

    @property
    def representation(self) -> str:
        return bytes.fromhex(self.feed_id[2:]).decode().rstrip("\x00").strip()

    @property
    def type(self) -> int:
        return int(self.feed_id[:2], 16)

    @property
    def timestamp(self):
        return config.epoch.voting_epoch(self.voting_round_id).next.start_s

    @property
    def hash(self):
        name_mapper = {
            "votingRoundId": self.voting_round_id,
            "id": bytes.fromhex(self.feed_id),
            "value": self.value,
            "turnoutBIPS": self.turnout_bips,
            "decimals": self.decimals,
        }
        return base_hash(self.STRUCT_ABI, name_mapper)

    @classmethod
    def from_decoded_dict(cls, response: FtsoVotingResponse):
        return cls(
            voting_round_id=response.votingRoundId,
            feed_id=un_prefix_0x(response.id.lower()),
            value=response.value,
            turnout_bips=response.turnoutBIPS,
            decimals=response.decimals,
        )


def base_hash(abi, value_mapper) -> bytes:
    TYPES = []
    VALUES = []
    for k in abi["components"]:
        TYPES.append(k["type"])
        VALUES.append(value_mapper[k["name"]])

    return Web3.solidity_keccak(["bytes"], [encode(TYPES, VALUES)])


class RandomResult(models.Model):
    voting_round_id = models.PositiveBigIntegerField()

    value = models.CharField(max_length=64)  # 32 bytes
    is_secure = models.BooleanField()

    STRUCT_ABI: ClassVar = {
        "components": [
            {"internalType": "uint32", "name": "votingRoundId", "type": "uint32"},
            {"internalType": "uint256", "name": "value", "type": "uint256"},
            {"internalType": "bool", "name": "isSecure", "type": "bool"},
        ],
        "internalType": "struct IFtsoFeedPublisher.Random",
        "name": "_random",
        "type": "tuple",
    }

    def __str__(self) -> str:
        return f"Random for {self.voting_round_id}: {self.value}"

    @property
    def hash(self):
        name_mapper = {
            "votingRoundId": self.voting_round_id,
            "value": int(self.value, 16),
            "isSecure": self.is_secure,
        }
        return base_hash(self.STRUCT_ABI, name_mapper)

    @classmethod
    def from_decoded_dict(cls, response: FtsoRandomResponse):
        return cls(
            voting_round_id=response.votingRoundId,
            value=un_prefix_0x(response.value.lower()),
            is_secure=response.isSecure,
        )
