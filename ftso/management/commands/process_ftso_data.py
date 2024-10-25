import logging

from django.core.management.base import BaseCommand

from configuration.config import config
from processing.ftso_processing import FtsoProcessor
from processing.main import DataProcessor, ProtocolProcessingConfig

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def handle(self, *args, **options):
        if not config.ftso.providers:
            logger.warning("Providers are not set for ftso.")
            return

        ftso_processor = FtsoProcessor(config.ftso)
        processor = DataProcessor(config.rpc_url, config.syncing_config, config.contracts.Relay)
        processor.run(
            ProtocolProcessingConfig(
                protocol_id=config.ftso.protocol_id,
                processor=ftso_processor,
            )
        )
