import logging
from typing import Sequence

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
        assert (
            root.protocol_id == self.protocol_id
        ), f"{self.protocol_id=} should match {root.protocol_id=}"

        errors = []

        for client in self.providers:
            try:
                data = self.process_single_provider(root, client)
            except Exception as e:
                logger.warning(
                    f"Error while fetching [P:{client.logging_name}]"
                    f"[VR:{root.voting_round_id}] - {e}"
                )
                errors.append(e)
                continue
            return data
        raise ValueError(
            f"Error while fetching [VR:{root.voting_round_id}] from all providers",
            errors,
        )

    def process_single_provider(self, root: ProtocolMessageRelayed, client: BaseClient):
        raise NotImplementedError("Subclasses must implement this method")

    def process(self, root: ProtocolMessageRelayed):
        raise NotImplementedError("Subclasses must implement this method")
