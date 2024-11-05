import logging

from drf_spectacular.utils import extend_schema
from py_flare_common.merkle import MerkleTree
from rest_framework import decorators, response, status, viewsets

from ftso.models import FeedResult, RandomResult
from ftso.serializers.data import (
    FeedValueNameSerializer,
    MerkleProofValueSerializer,
)
from ftso.serializers.query import (
    FeedResultAvailableFeedsQuerySerializer,
    FeedResultFeedsWithProofsQuerySerializer,
)
from ftso.serializers.request import (
    FeedResultFeedsWithProofsRequestSerializer,
)
from processing.utils import un_prefix_0x

logger = logging.getLogger(__name__)


class FeedResultViewSet(viewsets.GenericViewSet):
    def get_queryset(self):
        return FeedResult.objects.all()

    @extend_schema(
        parameters=[FeedResultAvailableFeedsQuerySerializer],
        responses={200: FeedValueNameSerializer(many=True)},
    )
    @decorators.action(detail=False, methods=["get"], url_path="anchor-feed-names")
    def anchor_feed_names(self, request, *args, **kwargs):
        self.serializer_class = FeedValueNameSerializer

        _query_params = FeedResultAvailableFeedsQuerySerializer(data=request.query_params)
        _query_params.is_valid(raise_exception=True)
        query_params = _query_params.validated_data

        voting_round_id = get_requested_round_id(query_params.get("voting_round_id", None))
        if voting_round_id is None:
            return response.Response(None, status=status.HTTP_404_NOT_FOUND)

        logger.debug(f"Querying for available feeds for round: {voting_round_id}")

        queryset = self.get_queryset().filter(voting_round_id=voting_round_id)
        serializer = self.get_serializer(queryset, many=True)

        return response.Response(serializer.data)

    @extend_schema(
        parameters=[FeedResultFeedsWithProofsQuerySerializer],
        request=FeedResultFeedsWithProofsRequestSerializer,
        responses={200: MerkleProofValueSerializer(many=True)},
    )
    @decorators.action(detail=False, methods=["post"], url_path="anchor-feeds-with-proof")
    def anchor_feeds_with_proof(self, request, *args, **kwargs):
        self.serializer_class = MerkleProofValueSerializer

        # TODO:(matej) validate both at the same time
        _query_params = FeedResultFeedsWithProofsQuerySerializer(data=request.query_params)
        _query_params.is_valid(raise_exception=True)
        query_params = _query_params.validated_data

        _body = FeedResultFeedsWithProofsRequestSerializer(data=request.data)
        _body.is_valid(raise_exception=True)
        body = _body.validated_data

        voting_round_id = get_requested_round_id(query_params.get("voting_round_id"))
        if voting_round_id is None:
            return response.Response(None, status=status.HTTP_404_NOT_FOUND)

        feed_ids = list(map(un_prefix_0x, body["feed_ids"]))

        queryset = self.get_queryset().filter(voting_round_id=voting_round_id).filter(feed_id__in=feed_ids).all()
        if queryset is None:
            return response.Response(None, status=status.HTTP_404_NOT_FOUND)

        tree = get_merkle_tree_for_round(voting_round_id)
        data = [
            {
                "body": el,
                "proof": tree.get_proof(el.hash.hex()),
            }
            for el in queryset
        ]

        serializer = self.get_serializer(data, many=True)
        return response.Response(serializer.data)


# Utils
# TODO:(luka) Also handle too early rounds
def get_requested_round_id(query_voting_round_id: int | None) -> int | None:
    latest_round = FeedResult.objects.latest("voting_round_id")
    if query_voting_round_id is None:
        if latest_round is None:
            # TODO:(luka) we have no data, error/none
            return None
        return latest_round.voting_round_id
    query_voting_round_id = int(query_voting_round_id)
    if query_voting_round_id > latest_round.voting_round_id:
        # Querying for a round that does not exist (ie is not indexed yet)
        # TODO:(luka) We can handle this differently
        logger.debug("Querying for a round that does not yet exist")
        query_voting_round_id = latest_round.voting_round_id
    return query_voting_round_id


# TODO:(luka) WIP
def get_merkle_tree_for_round(voting_round_id: int) -> MerkleTree:
    queryset = FeedResult.objects.filter(voting_round_id=voting_round_id)
    random = RandomResult.objects.filter(voting_round_id=voting_round_id).first()
    if random is None:
        raise ValueError("No random result for this round")
    a = [v.hash.hex() for v in queryset]
    b = random.hash.hex()
    return MerkleTree([b, *a])
