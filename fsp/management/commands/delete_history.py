import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from configuration.config import config
from fdc.models import AttestationResult
from fsp.models import ProtocolMessageRelayed
from ftso.models import FeedResult, RandomResult


class Command(BaseCommand):
    def handle(self, *args, **options):
        history_rounds: int | None = settings.HISTORY_KEEP_ROUNDS
        if history_rounds is None:
            return

        while True:
            time.sleep(600)

            voting_epoch_now = config.epoch.voting_epoch_factory.now_id()
            voting_round = config.epoch.voting_epoch(
                voting_epoch_now - history_rounds
            ).id

            with transaction.atomic():
                AttestationResult.objects.filter(
                    voting_round_id__lt=voting_round
                ).delete()
                FeedResult.objects.filter(voting_round_id__lt=voting_round).delete()
                RandomResult.objects.filter(voting_round_id__lt=voting_round).delete()
                ProtocolMessageRelayed.objects.filter(
                    voting_round_id__lt=voting_round
                ).delete()
