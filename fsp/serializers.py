from rest_framework import serializers


class VotingRoundSerializer(serializers.Serializer):
    voting_round_id = serializers.IntegerField()
    start_timestamp = serializers.IntegerField()


class VotingRoundStatusSerializer(serializers.Serializer):
    active = VotingRoundSerializer()
    latest_fdc = VotingRoundSerializer()
    latest_ftso = VotingRoundSerializer()
