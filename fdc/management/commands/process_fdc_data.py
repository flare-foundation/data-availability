import logging

from django.core.management.base import BaseCommand

from configuration.config import config
from processing.fdc_processing import FdcProcessor
from processing.main import DataProcessor, ProtocolProcessingConfig

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def handle(self, *args, **options):
        if not config.fdc.providers:
            logger.warning("Providers are not set for fdc")
            return

        fdc_processor = FdcProcessor(config.fdc)
        for client in fdc_processor.providers:
            if not client.is_responsive():
                logger.error(f"Provider {client} is not responsive.")

        processor = DataProcessor(
            config.rpc_url, config.syncing_config, config.contracts.relay
        )
        processor.run(
            ProtocolProcessingConfig(
                protocol_id=config.fdc.protocol_id,
                processor=fdc_processor,
            )
        )
