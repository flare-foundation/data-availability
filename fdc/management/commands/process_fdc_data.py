import logging

from django.core.management.base import BaseCommand

from configuration.config import config
from processing.fdc_processing import FdcProcessor
from processing.main import DataProcessor, ProtocolProcessingConfig

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def handle(self, *args, **options):
        if not config.fdc.providers:
            logger.warning("Providers are not set for fdc.")
            return

        fdc_processor = FdcProcessor(config.fdc)
        processor = DataProcessor(config.rpc_url, config.syncing_config, config.contracts.Relay)

        processor.run(
            ProtocolProcessingConfig(
                protocol_id=config.fdc.protocol_id,
                processing_function=fdc_processor.process,
            )
        )
