from rest_framework import serializers

from ...models import AttestationResult


class AttestationResultV1Serializer(serializers.ModelSerializer):
    response = serializers.DictField()

    class Meta:
        model = AttestationResult
        fields = ("response", "proof")


class AttestationResultRawV1Serializer(serializers.ModelSerializer):
    class Meta:
        model = AttestationResult
        fields = ("response_hex", "attestation_type")
