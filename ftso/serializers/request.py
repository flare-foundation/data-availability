from rest_framework import serializers


class FeedResultFeedWithProofRequestSerializer(serializers.Serializer):
    feed_id = serializers.CharField(
        required=True,
        help_text="Feed id with 0x prefix included",
    )


class FeedResultFeedsWithProofsRequestSerializer(serializers.Serializer):
    feed_ids = serializers.ListField(
        required=True,
        help_text="List of feed ids with 0x prefixes included",
        child=serializers.CharField(),
    )
