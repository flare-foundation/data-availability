"""Drop artifacts and expectations past their backstop. One long-running process.

Deliberately separate from ``delete_history``, which prunes FTSO and FDC rounds
by voting round. This prunes by an artifact's own lifecycle, and the two must
not share a schedule: a round is finished when consensus moved on, while an
artifact is finished when the thing it describes settled.
"""

import logging
import time

from django.core.management.base import BaseCommand

from dal.retention import sweep

logger = logging.getLogger(__name__)

SLEEP_SECONDS = 600


class Command(BaseCommand):
    help = "Evict DAL artifacts and expectations past their max-age backstop."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once", action="store_true", help="run a single sweep and exit"
        )
        parser.add_argument("--sleep", type=int, default=SLEEP_SECONDS)

    def handle(self, *args, **options):
        while True:
            report = sweep()
            if report.open_past_backstop:
                # Not routine. An OPEN expectation reaching its backstop means
                # the artifact never arrived and nothing terminal was ever
                # recorded -- a rising count is a collector that has stopped
                # collecting, which otherwise looks exactly like a quiet chain.
                logger.warning(
                    "DAL retention: %d expectation(s) expired still OPEN",
                    report.open_past_backstop,
                )
            if options["once"]:
                return
            time.sleep(options["sleep"])
