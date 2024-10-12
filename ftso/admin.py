# Register your models here.

from django.contrib import admin

from ftso.models import FeedResult


@admin.register(FeedResult)
class FeedResultAdmin(admin.ModelAdmin):
    list_display = ("feed_id", "voting_round_id", "value", "turnout_bips", "decimals")
    list_filter = ("feed_id", "voting_round_id", "value", "turnout_bips", "decimals")
    search_fields = ("feed_id", "voting_round_id", "value", "turnout_bips", "decimals")
    ordering = ("voting_round_id", "feed_id", "value", "turnout_bips", "decimals")
    # list_per_page = 25
