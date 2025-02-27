from rest_framework import serializers

from ..models import AttestationResult


class AttestationMinimalProofSerializer(serializers.ModelSerializer):
    response = serializers.DictField()

    class Meta:
        model = AttestationResult
        fields = ("response", "proof")
