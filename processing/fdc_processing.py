import logging

from django.db import transaction
from sentry_sdk import capture_message

from configuration.types import ProtocolProvider
from fdc.models import AttestationResult
from fsp.models import ProtocolMessageRelayed
from processing.client.main import FdcClient
from processing.merkle_tree import MerkleTree
from processing.utils import un_prefix_0x

logger = logging.getLogger(__name__)


def process_single_fdc_provider(root: ProtocolMessageRelayed, client: FdcClient):
    parsed_response = client.get_data(root.voting_round_id)

    # Construct full merkle tree
    leafs = [AttestationResult.from_decoded_dict(leaf) for leaf in parsed_response.Attestations]
    merkle_tree = MerkleTree([leaf.hash.hex() for leaf in leafs])

    if merkle_tree.root and un_prefix_0x(merkle_tree.root.lower()) != root.merkle_root:
        logging.error(
            "Merkle roots mismatch (FDC) (chain and calculated) (round: %s) %s: \nChain      : %s \nCalculated : %s",
            root.voting_round_id,
            client,
            root.merkle_root,
            merkle_tree.root,
        )
        return None

    return leafs


class FdcProcessor:
    def __init__(self, config: ProtocolProvider):
        self.protocol_id = config.protocol_id
        self.providers = [FdcClient.from_config(conf) for conf in config.client_configs]

    def fetch_fdc_merkle_tree(self, root: ProtocolMessageRelayed):
        if root.protocol_id != self.protocol_id:
            logging.error(
                "Protocol ID mismatch %s: \nExpected: %s \nReceived: %s",
                self,
                self.protocol_id,
                root.protocol_id,
            )
            return None

        for provider in self.providers:
            try:
                data = process_single_fdc_provider(root, provider)
                if data is None:
                    continue
                return data
            except Exception as e:
                logging.error(
                    "Error processing provider %s: %s",
                    provider,
                    e,
                )
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
        data = self.fetch_fdc_merkle_tree(root)
        if data is None:
            return None
        with transaction.atomic():
            ProtocolMessageRelayed.objects.bulk_create([root])
            AttestationResult.objects.bulk_create(data)
            logger.info(f"Processed {len(data)} FDC attestations for voting round {root.voting_round_id}")
