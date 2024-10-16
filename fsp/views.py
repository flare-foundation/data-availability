from drf_spectacular.utils import extend_schema
from rest_framework import decorators, response, viewsets

from .epoch import VotingEpoch
from .serializers import LatestVotingRoundSerializer


class FspViewSet(viewsets.GenericViewSet):
    @extend_schema(responses=LatestVotingRoundSerializer)
    @decorators.action(detail=False, methods=["get"], url_path="latest-voting-round")
    def latest_voting_round(self, request, *args, **kwargs):
        self.serializer_class = LatestVotingRoundSerializer

        ve = VotingEpoch.now()

        data = {
            "voting_round_id": ve.n,
            "timestamp": ve.start_s,
        }
        serializer = self.get_serializer(data)

        return response.Response(serializer.data)
