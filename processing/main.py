import logging
import time
from collections import deque

from attr import frozen
from django.db.models.aggregates import Max
from sentry_sdk import capture_exception
from web3 import Web3

from configuration.contract_types import Contract
from configuration.types import SyncingConfig
from fsp.models import ProtocolMessageRelayed
from processing.processing import Processor
from processing.utils import un_prefix_0x

logger = logging.getLogger(__name__)


@frozen
class ProtocolProcessingConfig:
    protocol_id: int
    processor: Processor


class DataProcessor:
    RELAY_EVENT_NAME = "ProtocolMessageRelayed"

    def __init__(self, rpc_url: str, sync_config: SyncingConfig, relay: Contract):
        assert relay is not None and relay.address is not None

        self.relay_contract = relay
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        self.default_start_height = sync_config.start_height
        self.max_processing_block_batch = sync_config.max_processing_block_batch
        self.processing_sleep_cycle = sync_config.processing_sleep_cycle

    def run(self, protocol_config: ProtocolProcessingConfig):
        ADDRESSES = [self.relay_contract.address]  # Relay Address

        RELAY_EVENT = self.relay_contract.events[self.RELAY_EVENT_NAME]
        EVENT_SIGNATURE = {un_prefix_0x(RELAY_EVENT.signature).lower()}

        db_processed_height = ProtocolMessageRelayed.objects.filter(
            protocol_id=protocol_config.protocol_id,
        ).aggregate(m=Max("block"))["m"]

        start = db_processed_height or (self.default_start_height - 1)

        logger.info(
            f"Processing started for protocol [id:{protocol_config.protocol_id}]."
        )
        providers_string = ", ".join(
            [f"{p.logging_name} - {p.url}" for p in protocol_config.processor.providers]
        )
        logger.info(f"Using providers {providers_string}.")
        logger.info(f"Starting processing from block {start}.")

        processing_queue: deque[tuple[ProtocolMessageRelayed, int, float]] = deque()

        while True:
            height = self.w3.eth.get_block_number()

            if height == start:
                time.sleep(self.processing_sleep_cycle)
                continue

            while start < height:
                index_range = min(self.max_processing_block_batch, height - start)
                logger.debug(f"Processing blocks [{start}-{start + index_range}]")

                events = self.w3.eth.get_logs(
                    {
                        "fromBlock": start,
                        # to block is including in this function
                        "toBlock": start + index_range - 1,
                        "address": ADDRESSES,
                    }
                )

                start += index_range

                for event in events:
                    signature = un_prefix_0x(event["topics"][0].hex()).lower()
                    if signature not in EVENT_SIGNATURE:
                        continue

                    ev = ProtocolMessageRelayed.process_event(
                        event, RELAY_EVENT, self.w3
                    )
                    if ev is None or ev.protocol_id != protocol_config.protocol_id:
                        continue

                    try:
                        logger.debug(f"Processing event {ev}")
                        protocol_config.processor.process(ev)
                        logger.info(f"Processed event {ev}")

                    except Exception:
                        logger.warning(
                            f"Failed to process and added to retry queue: {ev}"
                        )
                        processing_queue.append((ev, 1, time.time()))

            # Retry to process failed events
            while processing_queue:
                ev, i, t = processing_queue.popleft()

                if time.time() - t <= 20:
                    # the first event has the smallest t in the processing_queue
                    processing_queue.appendleft((ev, i, t))
                    break

                try:
                    logger.debug(f"Processing event {ev}")
                    protocol_config.processor.process(ev)
                    logger.info(f"Processed event with retry [retry:{i}] {ev}")

                except Exception as e:
                    if i < 5:
                        processing_queue.append((ev, i + 1, time.time()))
                    else:
                        capture_exception(e)
                        logger.error(
                            f"Failed: [vr:{ev.voting_round_id}] "
                            f"[retry:{i}] [event:{ev}]"
                        )
