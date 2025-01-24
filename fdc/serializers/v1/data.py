from rest_framework import serializers

from processing.utils import prefix_0x

from ...models import AttestationResult


class AttestationResultV1Serializer(serializers.ModelSerializer):
    response = serializers.DictField()

    class Meta:
        model = AttestationResult
        fields = ("response", "proof")


class AttestationResultRawV1Serializer(serializers.ModelSerializer):
    response_hex = serializers.SerializerMethodField()

    def get_response_hex(self, obj) -> str:
        return prefix_0x(obj.response_hex)

    class Meta:
        model = AttestationResult
        fields = ("response_hex", "attestation_type", "proof")
