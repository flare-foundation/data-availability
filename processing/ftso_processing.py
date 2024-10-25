import logging
from typing import cast

from django.db import transaction

from fsp.models import ProtocolMessageRelayed
from ftso.models import FeedResult, RandomResult
from processing.client.main import BaseClient, FtsoClient
from processing.merkle_tree import MerkleTree
from processing.processing import Processor
from processing.utils import un_prefix_0x

logger = logging.getLogger(__name__)


class FtsoProcessor(Processor):
    providers: list[FtsoClient]

    def process_single_provider(self, root: ProtocolMessageRelayed, client: BaseClient):
        client = cast(FtsoClient, client)
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
        merkle_tree = MerkleTree([r.hash.hex() for r in rand] + [r.hash.hex() for r in res])

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

    def process(self, root: ProtocolMessageRelayed):
        data = self.fetch_merkle_tree(root)
        if data is None:
            return None
        rand, res = data
        with transaction.atomic():
            ProtocolMessageRelayed.objects.bulk_create([root])
            RandomResult.objects.bulk_create(rand)
            FeedResult.objects.bulk_create(res)
            logger.info("Processed round %s and saved FTSO data to DB", root.voting_round_id)
