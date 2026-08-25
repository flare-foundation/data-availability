"""Discover triggers, then collect what they imply. One long-running process.

Shaped like ``process_ftso_data`` and ``process_fdc_data``: a management command
that loops until killed, deployed as its own container. Discovery and collection
share a tick rather than running as two processes, because an expectation is
useless until something fetches it and a fetch is wasted before its expectation
exists.
"""

import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from dal.chain import indexer as indexer_module
from dal.chain.indexer import HistoryGap
from dal.chain.triggers import discover_tee_instructions
from dal.collector import collect_once
from dal.gate.g2 import gate_action_result
from dal.keys import instruction_index_key

logger = logging.getLogger(__name__)

SLEEP_SECONDS = 20


class Command(BaseCommand):
    help = "Collect DAL artifacts: discover triggers, fetch, gate, store."

    def add_arguments(self, parser):
        parser.add_argument(
            "--contract",
            required=True,
            help="address emitting TeeInstructionsSent",
        )
        parser.add_argument(
            "--from-block",
            type=int,
            default=0,
            help="where to start when no expectation has been written yet",
        )
        parser.add_argument(
            "--once", action="store_true", help="run a single tick and exit"
        )
        parser.add_argument("--sleep", type=int, default=SLEEP_SECONDS)

    def handle(self, *args, **options):
        reader = indexer_module.from_settings()
        chain_id = _chain_id()
        cursor = options["from_block"]

        while True:
            try:
                report = discover_tee_instructions(
                    reader,
                    contract_address=options["contract"],
                    from_block=cursor,
                )
                # Advance only through what the indexer has WRITTEN. Moving the
                # cursor to the chain tip would skip every block it had not
                # reached, and nothing revisits a skipped range.
                cursor = max(cursor, report.through_block + 1)
            except HistoryGap as exc:
                # The range asked for has been dropped, or the indexer has not
                # published its state yet. Never treated as "nothing happened":
                # that is the one reading which silently stops collecting.
                logger.error("DAL discovery cannot proceed: %s", exc)

            collect_once(
                gate=_gate(chain_id),
                origin_url=lambda expectation: expectation.origin,
                index_keys=_index_keys,
                allow_private=settings.DAL_ALLOW_PRIVATE_ORIGINS,
            )

            if options["once"]:
                return
            time.sleep(options["sleep"])


def _gate(chain_id: int):
    def gate(expectation, raw):
        params = expectation.params
        return gate_action_result(
            raw,
            chain_id=chain_id,
            instruction_id=bytes.fromhex(params["instructionId"].removeprefix("0x")),
            tee_id=params["teeId"],
            proxy_id=params["proxyId"],
            submission_tag=params["submissionTag"],
        )

    return gate


def _index_keys(expectation):
    """Every artifact of one instruction is reachable by the instruction alone."""
    instruction = bytes.fromhex(expectation.params["instructionId"].removeprefix("0x"))
    return [instruction_index_key(instruction)]


def _chain_id() -> int:
    """The chain the signatures are bound to.

    Read through the same configuration everything else uses, so a DAL pointed
    at one network cannot admit artifacts signed for another -- chainId is
    inside the signed payload, and this is the value it is checked against.
    """
    from web3 import Web3

    from configuration.config import config

    return Web3(Web3.HTTPProvider(config.rpc_url)).eth.chain_id
