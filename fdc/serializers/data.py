from rest_framework import serializers

from ..models import AttestationResult

# class AttestationResultSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = AttestationResult
#         # TODO:(matej) do we need all
#         fields = "__all__"


class AttestationMinimalProofSerializer(serializers.ModelSerializer):
    response = serializers.ReadOnlyField()

    class Meta:
        model = AttestationResult

        fields = (
            "response",
            "proof",
        )
        read_only_fields = ("response",)
