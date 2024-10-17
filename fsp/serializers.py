from rest_framework import serializers


class SingleVotingRoundDetailSerializer(serializers.Serializer):
    voting_round_id = serializers.IntegerField()
    start_timestamp = serializers.IntegerField()


class VotingRoundStatusSerializer(serializers.Serializer):
    active = SingleVotingRoundDetailSerializer()
    latest_fdc = SingleVotingRoundDetailSerializer()
    latest_ftso = SingleVotingRoundDetailSerializer()
