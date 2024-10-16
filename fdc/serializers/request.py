from rest_framework import serializers


class AttestationTypeGetByRoundIdBytesRequest(serializers.Serializer):
    votingRoundId = serializers.IntegerField(
        help_text="todo",
    )
    requestBytes = serializers.CharField(
        help_text="todo",
    )
