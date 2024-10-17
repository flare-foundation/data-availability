from rest_framework import serializers


class AttestationTypeGetByRoundIdBytesRequest(serializers.Serializer):
    votingRoundId = serializers.IntegerField(
        help_text="Voting round when the request was made",
    )
    requestBytes = serializers.CharField(
        help_text="Request bytes that were send (emitted)",
    )
