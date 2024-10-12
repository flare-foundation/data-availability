from rest_framework import serializers


class FeedResultAvailableFeedsQuerySerializer(serializers.Serializer):
    voting_round_id = serializers.IntegerField(
        required=False,
        help_text="Voting round. Defaults to latest.",
    )


class FeedResultFeedWithProofQuerySerializer(serializers.Serializer):
    voting_round_id = serializers.IntegerField(
        required=False,
        help_text="Voting round. Defaults to latest.",
    )


class FeedResultFeedsWithProofsQuerySerializer(serializers.Serializer):
    voting_round_id = serializers.IntegerField(
        required=False,
        help_text="Voting round. Defaults to latest.",
    )
