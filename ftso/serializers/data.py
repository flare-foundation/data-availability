from rest_framework import serializers

from ftso.models import FeedResult
from processing.utils import prefix_0x


class Prefix0xField(serializers.CharField):
    def to_representation(self, value):
        if value is None:
            return None

        return prefix_0x(value)


class FeedValueNameSerializer(serializers.ModelSerializer):
    feed_id = Prefix0xField()
    feed_name = serializers.CharField(source="representation")

    class Meta:
        model = FeedResult
        fields = ("feed_id", "feed_name")


class FeedValueStructSerializer(serializers.ModelSerializer):
    """
    Serializer that returns the feed in a json format that matches ABI definition
    """

    votingRoundId = serializers.IntegerField(source="voting_round_id")
    id = Prefix0xField(source="feed_id")
    value = serializers.IntegerField()
    turnoutBIPS = serializers.IntegerField(source="turnout_bips")
    decimals = serializers.IntegerField()

    class Meta:
        model = FeedResult
        fields = ("votingRoundId", "id", "value", "turnoutBIPS", "decimals")


class MerkleProofValueSerializer(serializers.Serializer):
    data = FeedValueStructSerializer()
    proof = serializers.ListField(child=serializers.CharField())
