from django.core.management.base import BaseCommand

from configuration.config import config
from processing.fdc_processing import FdcProcessor
from processing.main import DataProcessor, ProtocolProcessingConfig


class Command(BaseCommand):
    def handle(self, *args, **options):
        fdc_processor = FdcProcessor(config.fdc_provider)
        processor = DataProcessor(config.rpc_url, config.syncing_config, config.contracts.Relay)
        processor.run(
            ProtocolProcessingConfig(
                protocol_id=config.fdc_provider.protocol_id,
                processing_function=fdc_processor.process,
            )
        )
