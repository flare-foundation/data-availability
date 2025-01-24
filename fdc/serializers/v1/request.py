from rest_framework import serializers


class AttestationResponseProofByRequestRoundV1RequestSerializer(serializers.Serializer):
    votingRoundId = serializers.IntegerField(
        help_text="Specific voting round from which the proof should be fetched. If not provided latest matching proof will be fetched instead.",
        required=False,
    )
    requestBytes = serializers.CharField(
        help_text="Hex encoded attestation request.",
    )
