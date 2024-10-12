import logging

from django.db import transaction
from sentry_sdk import capture_message

from configuration.types import ProtocolProvider
from fsp.models import ProtocolMessageRelayed
from ftso.models import FeedResult, RandomResult
from processing.client.main import FtsoClient
from processing.merkle_tree import MerkleTree
from processing.utils import un_prefix_0x

logger = logging.getLogger(__name__)


def process_single_provider(root: ProtocolMessageRelayed, client: FtsoClient):
    parsed_response = client.get_data(root.voting_round_id)

    provider_root = un_prefix_0x(parsed_response.merkleRoot.lower())

    if provider_root != root.merkle_root:
        logging.error(
            "Merkle roots mismatch (provider and chain) (round: %s) %s: \nProvider : %s \nFinalized: %s",
            root.voting_round_id,
            client,
            provider_root,
            root.merkle_root,
        )
        return None

    rand = [RandomResult.from_decoded_dict(parsed_response.random)]

    res = [FeedResult.from_decoded_dict(leaf) for leaf in parsed_response.medians]

    tree_leafs = [r.hash.hex() for r in rand] + [r.hash.hex() for r in res]

    merkle_tree = MerkleTree(tree_leafs)

    if merkle_tree.root and un_prefix_0x(merkle_tree.root.lower()) != provider_root:
        logging.error(
            "Merkle roots mismatch (provider and calculated) (round: %s) %s: \nCalculated   : %s \nFrom provider: %s",
            root.voting_round_id,
            client,
            merkle_tree.root,
            provider_root,
        )
        return None

    return rand, res


class FtsoProcessor:
    def __init__(self, config: ProtocolProvider):
        self.protocol_id = config.protocol_id
        self.providers = [FtsoClient.from_config(conf) for conf in config.client_configs]

    def fetch_ftso_merkle_tree(self, root: ProtocolMessageRelayed):
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
                print(client.logging_name)
                data = process_single_provider(root, client)
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

    def process(self, root: ProtocolMessageRelayed):
        data = self.fetch_ftso_merkle_tree(root)
        if data is None:
            return
        rand, res = data
        with transaction.atomic():
            ProtocolMessageRelayed.objects.bulk_create([root])
            RandomResult.objects.bulk_create(rand)
            FeedResult.objects.bulk_create(res)
            logger.info("Processed round %s and saved FTSO data to DB", root.voting_round_id)
