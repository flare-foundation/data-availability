from rest_framework import serializers


class ListAttestationResultV1QuerySerializer(serializers.Serializer):
    voting_round_id = serializers.IntegerField(
        help_text="Voting round.",
    )
