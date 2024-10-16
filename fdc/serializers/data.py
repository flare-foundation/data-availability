from rest_framework import serializers

from ..models import AttestationResult


class AttestationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttestationResult
        # TODO:(matej) do we need all
        fields = "__all__"
