from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import decorators, response, serializers, status, viewsets

from processing.utils import un_prefix_0x

from ..models import AttestationResult
from ..serializers.v1.data import (
    AttestationResultRawV1Serializer,
    AttestationResultV1Serializer,
)
from ..serializers.v1.query import ListAttestationResultV1QuerySerializer
from ..serializers.v1.request import (
    AttestationResponseProofByRequestRoundV1RequestSerializer,
)


class AttestationResultV1ViewSet(viewsets.GenericViewSet):
    def get_queryset(self):
        return AttestationResult.objects.all()

    def _list(self, request, *args, **kwargs):
        _query_params = ListAttestationResultV1QuerySerializer(
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
        description=(
            "Returns full merkle tree with proof for each leaf for given round. "
            "Leafs are abi decoded."
        ),
        parameters=[ListAttestationResultV1QuerySerializer],
        responses=AttestationResultV1Serializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        self.serializer_class = AttestationResultV1Serializer
        return self._list(request, *args, **kwargs)

    @extend_schema(
        description=(
            "Returns full merkle tree with proof for each leaf for given round. "
            "Leafs are abi encoded."
        ),
        parameters=[ListAttestationResultV1QuerySerializer],
        responses=AttestationResultRawV1Serializer(many=True),
    )
    @decorators.action(detail=False, methods=["get"])
    def raw(self, request, *args, **kwargs):
        self.serializer_class = AttestationResultRawV1Serializer
        return self._list(request, *args, **kwargs)

    def _proof_by_request_round(self, request, *args, **kwargs):
        _body = AttestationResponseProofByRequestRoundV1RequestSerializer(
            data=self.request.data
        )
        _body.is_valid(raise_exception=True)
        body = _body.validated_data

        try:
            qs = self.get_queryset().filter(
                request_hex=un_prefix_0x(body["requestBytes"])
            )
            if "votingRoundId" in body:
                qs = qs.filter(
                    voting_round_id=body["votingRoundId"],
                )
            obj = qs.order_by("-voting_round_id").first()

        except AttestationResult.DoesNotExist:
            return response.Response(
                data={"error": "attestation request not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(obj)

        return response.Response(serializer.data)

    @extend_schema(
        description=(
            "Retrieves the attestation request proof for given request bytes and "
            "voting round. Leafs are abi decoded."
        ),
        request=AttestationResponseProofByRequestRoundV1RequestSerializer,
        responses={
            200: AttestationResultV1Serializer,
            400: inline_serializer(
                "AttestationTypeGetByRoundIdBytesErrorSerializer",
                fields={
                    "error": serializers.CharField(),
                },
            ),
        },
    )
    @decorators.action(
        detail=False, methods=["post"], url_path="proof-by-request-round"
    )
    def proof_by_request_round(self, request, *args, **kwargs):
        self.serializer_class = AttestationResultV1Serializer
        return self._proof_by_request_round(request, *args, **kwargs)

    @extend_schema(
        description=(
            "Retrieves the attestation request proof for given request bytes and "
            "voting round. Leafs are abi encoded."
        ),
        request=AttestationResponseProofByRequestRoundV1RequestSerializer,
        responses={
            200: AttestationResultRawV1Serializer,
            400: inline_serializer(
                "AttestationTypeGetByRoundIdBytesErrorSerializer",
                fields={
                    "error": serializers.CharField(),
                },
            ),
        },
    )
    @decorators.action(
        detail=False, methods=["post"], url_path="proof-by-request-round-raw"
    )
    def proof_by_request_round_raw(self, request, *args, **kwargs):
        self.serializer_class = AttestationResultRawV1Serializer
        return self._proof_by_request_round(request, *args, **kwargs)
