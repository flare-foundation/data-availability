from drf_spectacular.utils import extend_schema
from rest_framework import decorators, response, viewsets

from fdc.models import AttestationResult

from .serializers.data import AttestationMinimalProofSerializer
from .serializers.query import ListAttestationResultQuerySerializer
from .serializers.request import AttestationTypeGetByRoundIdBytesRequest


class AttestationResultViewSet(viewsets.GenericViewSet):
    def get_queryset(self):
        return AttestationResult.objects.all()

    @extend_schema(
        parameters=[ListAttestationResultQuerySerializer],
        responses=AttestationMinimalProofSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        self.serializer_class = AttestationMinimalProofSerializer

        _query_params = ListAttestationResultQuerySerializer(data=self.request.query_params)
        _query_params.is_valid(raise_exception=True)
        query_params = _query_params.validated_data

        queryset = self.get_queryset().filter(voting_round_id=query_params["voting_round_id"])

        serializer = self.get_serializer(queryset, many=True)

        return response.Response(serializer.data)

    @extend_schema(
        request=AttestationTypeGetByRoundIdBytesRequest,
        responses=AttestationMinimalProofSerializer,
    )
    @decorators.action(detail=False, methods=["post"])
    def get_proof_round_id_bytes(self, request, *args, **kwargs):
        self.serializer_class = AttestationMinimalProofSerializer

        _body = AttestationTypeGetByRoundIdBytesRequest(data=self.request.data)
        _body.is_valid(raise_exception=True)
        body = _body.validated_data

        obj = self.get_queryset().get(
            voting_round_id=body["votingRoundId"],
            request_hex=body["requestBytes"],
        )

        serializer = self.get_serializer(obj)

        return response.Response(serializer.data)
