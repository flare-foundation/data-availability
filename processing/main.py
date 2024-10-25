import logging
import queue
import time

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
        relay = relay
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

        latest_processed_height = db_processed_height or self.default_start_height

        while True:
            height = self.w3.eth.get_block_number()
            logger.info(f"Latest processed/current Height: {latest_processed_height} | {height}")

            processing_qeue = queue.Queue()
            while latest_processed_height < height:
                from_block_exc = latest_processed_height
                to_block_inc = min(latest_processed_height + self.max_processing_block_batch, height)
                events = self.w3.eth.get_logs(
                    {
                        "fromBlock": from_block_exc + 1,
                        "toBlock": to_block_inc,
                        "address": ADDRESSES,
                    }
                )
                latest_processed_height = to_block_inc

                print(f"Processing from {from_block_exc} to {to_block_inc}, found {len(events)} events")
                for event in events:
                    signature = un_prefix_0x(event["topics"][0].hex()).lower()
                    if signature not in EVENT_SIGNATURE:
                        continue
                    logger.debug("Processing event")
                    ev = ProtocolMessageRelayed.process_event(event, RELAY_EVENT, self.w3, {})
                    if ev is None:
                        continue
                    if ev.protocol_id != protocol_config.protocol_id:
                        continue
                    try:
                        logger.debug(f"Processing round {ev}")
                        protocol_config.processor.process(ev)
                    except Exception as e:
                        processing_qeue.put(ev)
                        capture_exception(e)
                        logger.error(f"Round processing failed for round {ev}")
                        # raise e

            # Retry to process failed events one more time
            while not processing_qeue.empty():
                ev = processing_qeue.get()
                try:
                    logger.debug(f"Processing round {ev}")
                    protocol_config.processor.process(ev)
                except Exception as e:
                    capture_exception(e)
                    logger.error(f"Round processing failed for round {ev}")

            time.sleep(self.processing_sleep_cycle)
