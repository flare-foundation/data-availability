from typing import cast

from django.db import transaction
from py_flare_common.merkle import MerkleTree

from configuration.types import ProtocolConfig
from fdc.models import AttestationResult
from fsp.models import ProtocolMessageRelayed
from processing.client.main import BaseClient, FdcClient
from processing.processing import Processor
from processing.utils import un_prefix_0x


class FdcProcessor(Processor):
    def _init_get_providers(self, config: ProtocolConfig):
        return [FdcClient.from_config(conf) for conf in config.providers]

    def process_single_provider(self, root: ProtocolMessageRelayed, client: BaseClient):
        client = cast(FdcClient, client)
        parsed_response = client.get_data(root.voting_round_id)

        # Construct full merkle tree
        leafs = [
            AttestationResult.from_decoded_dict(leaf)
            for leaf in parsed_response.Attestations
        ]
        merkle_tree = MerkleTree([leaf.hash.hex() for leaf in leafs])

        if (
            merkle_tree.root is None
            or un_prefix_0x(merkle_tree.root.lower()) != root.merkle_root
        ):
            raise ValueError(
                f"Root mismatch [chain:{root.merkle_root}] [calculated:{merkle_tree.root}]"
            )

        return leafs

    def process(self, root: ProtocolMessageRelayed):
        data = self.fetch_merkle_tree(root)
        with transaction.atomic():
            ProtocolMessageRelayed.objects.bulk_create([root])
            AttestationResult.objects.bulk_create(data)
