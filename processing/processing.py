import logging
from typing import Sequence

from sentry_sdk import capture_message

from configuration.types import ProtocolConfig
from fsp.models import ProtocolMessageRelayed
from processing.client.main import BaseClient

logger = logging.getLogger(__name__)


class Processor:
    def __init__(self, config: ProtocolConfig):
        self.protocol_id = config.protocol_id
        self.providers = self._init_get_providers(config)

    def _init_get_providers(self, config: ProtocolConfig) -> Sequence[BaseClient]:
        return [BaseClient.from_config(conf) for conf in config.providers]

    def fetch_merkle_tree(self, root: ProtocolMessageRelayed):
        if root.protocol_id != self.protocol_id:
            logger.error(
                f"Protocol ID mismatch: \nExpected : {self.protocol_id} \nReceived : {root.protocol_id}"
            )
            return None

        for client in self.providers:
            try:
                data = self.process_single_provider(root, client)
                if data is None:
                    continue
                return data
            except Exception as e:
                logger.error(f"Error fetching data from provider {client}: {e}")
                continue
        # TODO: sentry check it can process logger.error
        capture_message(
            f"Unable to fetch data from any provider for voting round {root.voting_round_id}"
        )
        logger.error(
            f"Unable to fetch data from any provider for voting round {root.voting_round_id}"
        )
        return None

    def process_single_provider(self, root: ProtocolMessageRelayed, client: BaseClient):
        raise NotImplementedError("Subclasses must implement this method")

    def process(self, root: ProtocolMessageRelayed):
        raise NotImplementedError("Subclasses must implement this method")
