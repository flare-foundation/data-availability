import logging

from sentry_sdk import capture_message

from configuration.types import ProtocolConfig
from fsp.models import ProtocolMessageRelayed
from processing.client.main import BaseClient


class Processor:
    def __init__(self, config: ProtocolConfig):
        self.protocol_id = config.protocol_id
        self.providers = [BaseClient.from_config(conf) for conf in config.providers]

    def fetch_merkle_tree(self, root: ProtocolMessageRelayed):
        if root.protocol_id != self.protocol_id:
            logging.error(
                "Protocol ID mismatch %s: \nExpected: %s \nReceived: %s",
                self,
                self.protocol_id,
                root.protocol_id,
            )
            return None

        for client in self.providers:
            try:
                data = self.process_single_provider(root, client)
                if data is None:
                    continue
                return data
            except Exception as e:
                logging.error("Error fetching data from provider %s: %s", client, e)
                continue
        # TODO: sentry check it can process logging.error
        capture_message(
            f"Unable to fetch data from any provider for voting round {root.voting_round_id}",
        )
        logging.error(
            "Unable to fetch data from any provider for voting round %s",
            root.voting_round_id,
        )
        return None

    def process_single_provider(self, root: ProtocolMessageRelayed, client: BaseClient):
        raise NotImplementedError("Subclasses must implement this method")

    def process(self, root: ProtocolMessageRelayed):
        raise NotImplementedError("Subclasses must implement this method")
