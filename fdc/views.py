from rest_framework import viewsets

from fdc.models import AttestationResult


class AttestationResultViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = "voting_round_id"

    def get_queryset(self):
        return AttestationResult.objects.all()

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
