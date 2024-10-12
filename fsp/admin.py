from django.contrib import admin

from fsp.models import ProtocolMessageRelayed

# Register your models here.


@admin.register(ProtocolMessageRelayed)
class ProtocolMessageRelayedAdmin(admin.ModelAdmin):
    list_display = ("voting_round_id", "protocol_id", "merkle_root", "is_secure_random")
    list_filter = ("voting_round_id", "merkle_root", "protocol_id")
    search_fields = ("voting_round_id", "protocol_id")
    ordering = ("voting_round_id", "merkle_root")
