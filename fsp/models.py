import logging

from django.db import models
from sentry_sdk import capture_exception
from web3 import Web3
from web3._utils.events import (
    get_event_data,
)
from web3.types import EventData, LogReceipt

from configuration.contract_types import Event
from processing.utils import un_prefix_0x

logger = logging.getLogger(__name__)


def event_data_extract_args(event_data: EventData, *args: str):
    errors: list[KeyError] = []
    for key in filter(lambda x: x not in event_data["args"], args):
        errors.append(KeyError(f"missing key {key}"))

    if errors:
        raise KeyError(errors)

    return [event_data["args"][a] for a in args]


class ProtocolMessageRelayed(models.Model):
    EVENT_NAME = "ProtocolMessageRelayed"

    block = models.IntegerField()
    protocol_id = models.PositiveSmallIntegerField()
    voting_round_id = models.PositiveIntegerField()
    is_secure_random = models.BooleanField()
    merkle_root = models.CharField(max_length=64)  # 32 bytes

    class Meta:
        unique_together = ("protocol_id", "voting_round_id")

    def __str__(self):
        return f"{self.protocol_id} - {self.voting_round_id} - {self.merkle_root}"

    @classmethod
    def from_decoded_dict(cls, event_data: EventData):
        (
            _protocol_id,
            _voting_round_id,
            _is_secure_random,
            _merkle_root,
        ) = event_data_extract_args(event_data, "protocolId", "votingRoundId", "isSecureRandom", "merkleRoot")
        protocol_id = int(_protocol_id)
        voting_round_id = int(_voting_round_id)
        is_secure_random = bool(_is_secure_random)
        merkle_root = un_prefix_0x(_merkle_root.hex().lower())

        return cls(
            block=event_data["blockNumber"],
            protocol_id=protocol_id,
            voting_round_id=voting_round_id,
            is_secure_random=is_secure_random,
            merkle_root=merkle_root,
        )

    @classmethod
    def process_event(cls, log_receipt: LogReceipt, event: Event, w3: Web3) -> "ProtocolMessageRelayed":
        try:
            ev = get_event_data(w3.codec, event.abi, log_receipt)
            return cls.from_decoded_dict(ev)
        except Exception as e:
            capture_exception(e)
            logger.error(f"Failed to process event {cls.EVENT_NAME}")
            raise e
