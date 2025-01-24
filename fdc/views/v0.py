from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import decorators, response, serializers, status, viewsets

from processing.utils import un_prefix_0x

from ..models import AttestationResult
from ..serializers.v0.data import AttestationResultV0Serializer
from ..serializers.v0.query import ListAttestationResultV0QuerySerializer
from ..serializers.v0.request import (
    AttestationTypeGetByRoundBytesV0RequestSerializer,
    AttestationTypeGetByRoundIdBytesv0RequestSerializer,
)


class AttestationResultV0ViewSet(viewsets.GenericViewSet):
    def get_queryset(self):
        return AttestationResult.objects.all()

    @extend_schema(
        deprecated=True,
        description="Retrieves the attestation minimal proofs based on voting round id",
        parameters=[ListAttestationResultV0QuerySerializer],
        responses=AttestationResultV0Serializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        self.serializer_class = AttestationResultV0Serializer

        _query_params = ListAttestationResultV0QuerySerializer(
            data=self.request.query_params
        )
        _query_params.is_valid(raise_exception=True)
        query_params = _query_params.validated_data

        queryset = self.get_queryset().filter(
            voting_round_id=query_params["voting_round_id"]
        )

        serializer = self.get_serializer(queryset, many=True)

        return response.Response(serializer.data)

    @extend_schema(
        deprecated=True,
        description="Retrieves the attestation minimal proof based on request bytes and voting round id",
        request=AttestationTypeGetByRoundIdBytesv0RequestSerializer,
        responses={
            200: AttestationResultV0Serializer,
            400: inline_serializer(
                "AttestationTypeGetByRoundIdBytesErrorSerializer",
                fields={
                    "error": serializers.CharField(),
                },
            ),
        },
    )
    @decorators.action(
        detail=False, methods=["post"], url_path="get-proof-round-id-bytes"
    )
    def get_proof_round_id_bytes(self, request, *args, **kwargs):
        self.serializer_class = AttestationResultV0Serializer

        _body = AttestationTypeGetByRoundIdBytesv0RequestSerializer(
            data=self.request.data
        )
        _body.is_valid(raise_exception=True)
        body = _body.validated_data

        try:
            obj = self.get_queryset().get(
                voting_round_id=body["votingRoundId"],
                request_hex=un_prefix_0x(body["requestBytes"]),
            )
        except AttestationResult.DoesNotExist:
            return response.Response(
                data={"error": "attestation request not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(obj)

        return response.Response(serializer.data)

    @extend_schema(
        deprecated=True,
        description="Retrieves the last attestation minimal proof based on request bytes",
        request=AttestationTypeGetByRoundBytesV0RequestSerializer,
        responses={
            200: AttestationResultV0Serializer,
            400: inline_serializer(
                "AttestationTypeGetByRoundBytesErrorSerializer",
                fields={
                    "error": serializers.CharField(),
                },
            ),
        },
    )
    @decorators.action(detail=False, methods=["post"], url_path="get-proof-round-bytes")
    def get_proof_round_bytes(self, request, *args, **kwargs):
        self.serializer_class = AttestationResultV0Serializer

        _body = AttestationTypeGetByRoundBytesV0RequestSerializer(
            data=self.request.data
        )
        _body.is_valid(raise_exception=True)
        body = _body.validated_data

        try:
            obj = (
                self.get_queryset()
                .filter(
                    request_hex=body["requestBytes"],
                )
                .order_by("-voting_round_id")
                .first()
            )
        except AttestationResult.DoesNotExist:
            return response.Response(
                data={"error": "attestation request not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(obj)

        return response.Response(serializer.data)
