from drf_spectacular.utils import extend_schema
from rest_framework import response, viewsets, decorators

from fdc.models import AttestationResult

from .serializers.data import AttestationResultSerializer
from .serializers.query import ListAttestationResultQuerySerializer
from .serializers.request import AttestationTypeGetByRoundIdBytesRequest


class AttestationResultViewSet(viewsets.GenericViewSet):
    def get_queryset(self):
        return AttestationResult.objects.all()

    @extend_schema(
        parameters=[ListAttestationResultQuerySerializer],
        responses=AttestationResultSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        self.serializer_class = AttestationResultSerializer

        _query_params = ListAttestationResultQuerySerializer(self.request.query_params)
        _query_params.is_valid(raise_exception=True)
        query_params = _query_params.validated_data

        queryset = self.get_queryset().filter(voting_round_id=query_params["voting_round_id"])

        serializer = self.get_serializer(queryset, many=True)

        return response.Response(serializer.data)

    @extend_schema(
        request=AttestationTypeGetByRoundIdBytesRequest,
        responses=AttestationResultSerializer,
    )
    @decorators.action(detail=False, methods=["post"])
    def get_by_round_id_bytes(self, request, *args, **kwargs):
        self.serializer_class = AttestationResultSerializer

        _body = AttestationTypeGetByRoundIdBytesRequest(self.request.body)
        _body.is_valid(raise_exception=True)
        body = _body.validated_data

        obj = self.get_queryset().get(
            voting_round_id=body["votingRoundId"],
            request_hex=body["requestBytes"],
        )

        serializer = self.get_serializer(obj)

        return response.Response(serializer.data)
