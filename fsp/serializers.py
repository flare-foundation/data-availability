from rest_framework import serializers


class LatestVotingRoundSerializer(serializers.Serializer):
    voting_round_id = serializers.IntegerField()
    timestamp = serializers.IntegerField()
