from django.core.management.base import BaseCommand

from configuration.config import config
from processing.ftso_processing import FtsoProcessor
from processing.main import DataProcessor, ProtocolProcessingConfig


class Command(BaseCommand):
    def handle(self, *args, **options):
        ftso_processor = FtsoProcessor(config.ftso_provider)
        processor = DataProcessor(config.rpc_url, config.syncing_config, config.contracts.Relay)
        processor.run(
            ProtocolProcessingConfig(
                protocol_id=config.ftso_provider.protocol_id,
                processing_function=ftso_processor.process,
            )
        )
