"""Fetch one committed proposal package from its proposer, gate it, store it.

The entry point a data provider's own verification path calls when an
attestation request names a package hash it does not yet hold. Also the way to
drive the proposal path by hand while the automatic trigger is being built.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from dal.chain import registry as registry_module
from dal.proposals import collect_proposal


class Command(BaseCommand):
    help = "Fetch, gate and store one proposal package."

    def add_arguments(self, parser):
        parser.add_argument("--wallet-id", required=True)
        parser.add_argument("--account-index", type=int, default=0)
        parser.add_argument(
            "--proposer",
            required=True,
            help="the address that submitted the committing request — an on-chain "
            "fact, never a value taken from a requester",
        )
        parser.add_argument("--package-hash", required=True)
        parser.add_argument(
            "--txid", help="index the package under the txid it describes, too"
        )
        parser.add_argument(
            "--generation",
            type=int,
            help="check admission AT this eligibility generation rather than at latest",
        )

    def handle(self, *args, **options):
        if settings.DAL_CHAIN_ID is None:
            raise CommandError("set DAL_CHAIN_ID")

        def unhex(value, name, length=32):
            raw = bytes.fromhex(value.removeprefix("0x"))
            if len(raw) != length:
                raise CommandError(f"{name} must be {length} bytes")
            return raw

        outcome = collect_proposal(
            registry=registry_module.from_settings(),
            chain_id=settings.DAL_CHAIN_ID,
            wallet_id=unhex(options["wallet_id"], "wallet id"),
            account_index=options["account_index"],
            proposer=options["proposer"],
            package_hash=unhex(options["package_hash"], "package hash"),
            txid=unhex(options["txid"], "txid") if options["txid"] else None,
            generation=options["generation"],
            allow_private=settings.DAL_ALLOW_PRIVATE_ORIGINS,
        )

        if outcome.admitted:
            self.stdout.write(f"ADMITTED {outcome.key}")
            return
        raise CommandError(f"NOT ADMITTED {outcome.key}: {outcome.reason}")
