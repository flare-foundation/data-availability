from drf_spectacular.utils import extend_schema
from rest_framework import decorators, response, viewsets

from configuration.config import config
from fsp.models import ProtocolMessageRelayed

from .epoch import VotingEpoch
from .serializers import SingleVotingRoundDetailSerializer, VotingRoundStatusSerializer


class FspViewSet(viewsets.GenericViewSet):
    @extend_schema(responses=SingleVotingRoundDetailSerializer)
    @decorators.action(detail=False, methods=["get"], url_path="latest-voting-round")
    def latest_voting_round(self, request, *args, **kwargs):
        self.serializer_class = SingleVotingRoundDetailSerializer

        ve = VotingEpoch.now()

        data = {
            "voting_round_id": ve.n,
            "start_timestamp": ve.start_s,
        }
        serializer = self.get_serializer(data)

        return response.Response(serializer.data)

    @extend_schema(responses=VotingRoundStatusSerializer)
    @decorators.action(detail=False, methods=["get"], url_path="status")
    def status(self, request, *args, **kwargs):
        self.serializer_class = VotingRoundStatusSerializer

        ve = VotingEpoch.now()

        data = {
            "active": {
                "voting_round_id": ve.n,
                "timestamp": ve.start_s,
            },
            "latest_ftso": {"voting_round_id": -1, "timestamp": -1},
            "latest_fdc": {"voting_round_id": -1, "timestamp": -1},
        }

        # NOTE: for this to work saving to DB must be atomic
        latest_ftso = (
            ProtocolMessageRelayed.objects.get_queryset()
            .filter("protocol_id" == config.ftso_provider.protocol_id)
            .order_by("-voting_round_id")
            .first()
        )
        latest_fdc = (
            ProtocolMessageRelayed.objects.get_queryset()
            .filter("protocol_id" == config.fdc_provider.protocol_id)
            .order_by("-voting_round_id")
            .first()
        )
        if latest_ftso is not None:
            vef = VotingEpoch(latest_ftso.voting_round_id)
            data["latest_ftso"] = {"voting_round_id": vef.n, "timestamp": vef.start_s}
        if latest_fdc is not None:
            vef = VotingEpoch(latest_fdc.voting_round_id)
            data["latest_fdc"] = {"voting_round_id": vef.n, "timestamp": vef.start_s}

        serializer = self.get_serializer(data)

        return response.Response(serializer.data)
