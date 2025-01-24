from rest_framework import serializers

from fsp.epoch import VotingEpoch


class ListAttestationResultV1QuerySerializer(serializers.Serializer):
    voting_round_id = serializers.IntegerField(
        required=False,
        default=VotingEpoch.now_id,
        help_text="Voting round. Defaults to latest.",
    )
