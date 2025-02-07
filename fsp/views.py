from drf_spectacular.utils import extend_schema
from rest_framework import decorators, response, viewsets

from configuration.config import config
from fsp.models import ProtocolMessageRelayed

from .serializers import VotingRoundSerializer, VotingRoundStatusSerializer


class FspViewSet(viewsets.GenericViewSet):
    @extend_schema(
        description="Retrieves the last voting round id and its starting timestamp",
        responses=VotingRoundSerializer,
    )
    @decorators.action(detail=False, methods=["get"], url_path="latest-voting-round")
    def latest_voting_round(self, request, *args, **kwargs):
        self.serializer_class = VotingRoundSerializer

        ve = config.epoch.voting_epoch_factory.now()

        data = {
            "voting_round_id": ve.id,
            "start_timestamp": ve.start_s,
        }
        serializer = self.get_serializer(data)

        return response.Response(serializer.data)

    @extend_schema(
        description="Retrieves the last voting round id and its starting timestamp for fdc and ftso",
        responses=VotingRoundStatusSerializer,
    )
    @decorators.action(detail=False, methods=["get"], url_path="status")
    def status(self, request, *args, **kwargs):
        self.serializer_class = VotingRoundStatusSerializer

        ve = config.epoch.voting_epoch_factory.now()

        data = {
            "active": {
                "voting_round_id": ve.id,
                "start_timestamp": ve.start_s,
            },
            "latest_ftso": {"voting_round_id": -1, "start_timestamp": -1},
            "latest_fdc": {"voting_round_id": -1, "start_timestamp": -1},
        }

        if config.ftso is not None:
            # NOTE: for this to work saving to DB must be atomic
            latest_ftso = (
                ProtocolMessageRelayed.objects.filter(
                    protocol_id=config.ftso.protocol_id
                )
                .order_by("-voting_round_id")
                .first()
            )
        else:
            latest_ftso = None

        if config.fdc is not None:
            latest_fdc = (
                ProtocolMessageRelayed.objects.filter(
                    protocol_id=config.fdc.protocol_id
                )
                .order_by("-voting_round_id")
                .first()
            )
        else:
            latest_fdc = None

        if latest_ftso is not None:
            vef = config.epoch.voting_epoch(latest_ftso.voting_round_id)
            data["latest_ftso"] = {
                "voting_round_id": vef.id,
                "start_timestamp": vef.start_s,
            }
        if latest_fdc is not None:
            vef = config.epoch.voting_epoch(latest_fdc.voting_round_id)
            data["latest_fdc"] = {
                "voting_round_id": vef.id,
                "start_timestamp": vef.start_s,
            }

        serializer = self.get_serializer(data)

        return response.Response(serializer.data)
