import logging
from typing import cast

from django.db import transaction

from configuration.types import ProtocolConfig
from fdc.models import AttestationResult
from fsp.models import ProtocolMessageRelayed
from processing.client.main import BaseClient, FdcClient
from processing.merkle_tree import MerkleTree
from processing.processing import Processor
from processing.utils import un_prefix_0x

logger = logging.getLogger(__name__)


class FdcProcessor(Processor):
    def _init_get_providers(self, config: ProtocolConfig):
        return [FdcClient.from_config(conf) for conf in config.providers]

    def process_single_provider(self, root: ProtocolMessageRelayed, client: BaseClient):
        client = cast(FdcClient, client)
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

    def process(self, root: ProtocolMessageRelayed):
        data = self.fetch_merkle_tree(root)
        if data is None:
            return None
        with transaction.atomic():
            ProtocolMessageRelayed.objects.bulk_create([root])
            AttestationResult.objects.bulk_create(data)
            logger.info(f"Processed {len(data)} FDC attestations for voting round {root.voting_round_id}")
