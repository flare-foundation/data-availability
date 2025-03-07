from rest_framework import serializers

from configuration.config import config


class ListAttestationResultV1QuerySerializer(serializers.Serializer):
    voting_round_id = serializers.IntegerField(
        help_text="Voting round.",
    )
