from rest_framework import serializers

from configuration.config import config


class ListAttestationResultV0QuerySerializer(serializers.Serializer):
    voting_round_id = serializers.IntegerField(
        required=False,
        default=config.epoch.voting_epoch_factory.now_id,
        help_text="Voting round. Defaults to latest.",
    )
