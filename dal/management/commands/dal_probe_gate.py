"""Ask the gate about a body, and print what it would decide.

Diagnostic rather than test-only. When a store refuses an artifact the operator
question is always the same — *what was wrong with it* — and the answer lives in
a verdict that is otherwise only ever written to a log line and a database
column. This runs the real gate, with the real expectation's parameters, over
bytes given on the command line.
"""

import sys

from django.core.management.base import BaseCommand, CommandError

from dal.gate.g2 import gate_action_result
from dal.gate.result import Refused
from dal.models import Expectation


class Command(BaseCommand):
    help = "Run the gate over a body and report the verdict."

    def add_arguments(self, parser):
        parser.add_argument("--key", required=True, help="the expectation's key")
        parser.add_argument("--body", help="the body; omit to read stdin")
        parser.add_argument("--chain-id", type=int)

    def handle(self, *args, **options):
        try:
            expectation = Expectation.objects.get(key=options["key"].removeprefix("0x"))
        except Expectation.DoesNotExist as exc:
            raise CommandError(f"no expectation with key {options['key']}") from exc

        raw = (
            options["body"].encode()
            if options["body"] is not None
            else sys.stdin.buffer.read()
        )
        params = expectation.params
        chain_id = options["chain_id"]
        if chain_id is None:
            from django.conf import settings

            chain_id = settings.DAL_CHAIN_ID
        if chain_id is None:
            raise CommandError("set --chain-id or DAL_CHAIN_ID")

        verdict = gate_action_result(
            raw,
            chain_id=chain_id,
            instruction_id=bytes.fromhex(params["instructionId"].removeprefix("0x")),
            tee_id=params["teeId"],
            proxy_id=params["proxyId"],
            submission_tag=params["submissionTag"],
        )

        if isinstance(verdict, Refused):
            self.stdout.write(f"REFUSED: {verdict.reason}")
            return
        self.stdout.write(
            f"ADMITTED: key {verdict.key.hex()} ({len(verdict.raw)} bytes)"
        )
