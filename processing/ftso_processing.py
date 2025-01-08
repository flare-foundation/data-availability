from typing import cast

from django.db import transaction
from py_flare_common.merkle import MerkleTree

from configuration.types import ProtocolConfig
from fsp.models import ProtocolMessageRelayed
from ftso.models import FeedResult, RandomResult
from processing.client.main import BaseClient, FtsoClient
from processing.processing import Processor
from processing.utils import un_prefix_0x


class FtsoProcessor(Processor):
    def _init_get_providers(self, config: ProtocolConfig):
        return [FtsoClient.from_config(conf) for conf in config.providers]

    def process_single_provider(self, root: ProtocolMessageRelayed, client: BaseClient):
        client = cast(FtsoClient, client)
        parsed_response = client.get_data(root.voting_round_id)
        provider_root = un_prefix_0x(parsed_response.merkleRoot.lower())

        if provider_root != root.merkle_root:
            raise ValueError(
                f"Root mismatch [chain:{root.merkle_root}] [provider:{provider_root}]"
            )

        rand = [RandomResult.from_decoded_dict(parsed_response.random)]
        res = [FeedResult.from_decoded_dict(leaf) for leaf in parsed_response.medians]
        merkle_tree = MerkleTree(
            [r.hash.hex() for r in rand] + [r.hash.hex() for r in res]
        )

        if (
            merkle_tree.root is None
            or un_prefix_0x(merkle_tree.root.lower()) != provider_root
        ):
            raise ValueError(
                f"Root mismatch [provider:{provider_root}] [calculated:{merkle_tree.root}]"
            )

        return rand, res

    def process(self, root: ProtocolMessageRelayed):
        data = self.fetch_merkle_tree(root)
        rand, res = data
        with transaction.atomic():
            ProtocolMessageRelayed.objects.bulk_create([root])
            RandomResult.objects.bulk_create(rand)
            FeedResult.objects.bulk_create(res)
