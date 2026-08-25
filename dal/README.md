# `dal` — the Data Availability Layer app

What this app adds to the service is one thing: **a gate**. Everything the
service collects today is authorised by rebuilding a Merkle tree and comparing
it to the root the chain relayed. That works, and it only works after consensus
on the round has already happened — so it cannot authorise a TEE machine's
signed result, and it cannot authorise a proposal that must be read *during* a
voting round rather than after one.

The specification is
[`data-availability-layer.md`](https://gitlab.com/flarenetwork/btc-planning)
in the btc-planning repository; this app is phase 2 of it.

| Module | What it is |
|---|---|
| `gate/signing.py` | the payload construction every TEE-produced artifact is signed under |
| `gate/g2.py` | admit an artifact because a registered identity signed it |
| `gate/result.py` | `Admitted` / `Refused` — a refusal is terminal and alarmable, not a retry |
| `keys.py` | how artifacts are named: content keys and coordinate keys |
| `fetch.py` | the fetch boundary — every origin URL is attacker-controlled |
| `collector.py` | the tick: open expectations, fetched, gated, recorded |
| `retention.py` | eviction by lifecycle, with a mandatory max-age backstop |
| `chain/indexer.py` | reading triggers from the c-chain indexer |
| `chain/triggers.py` | turning one log into the expectations it implies |
| `chain/abi.py` | the events decoded, as literals, with their topics |
| `management/commands/` | `collect_dal`, `dal_delete_history` |
| `models.py` | expectations, artifacts, and the set-valued secondary index |

## Running the tests

```bash
uv sync
uv run pytest                 # needs a Postgres for the model tests
uv run pytest dal/tests/test_signing.py dal/tests/test_keys.py dal/tests/test_g2.py
```

The gate and the key derivation depend on nothing Django-specific and need no
database — deliberately, and worth keeping that way, because a gate that needs a
database and a chain to test is a gate that gets tested less. The model tests do
need one; any Postgres will do:

```bash
export DB_NAME=db DB_USER=db DB_PASSWORD= DB_HOST=127.0.0.1 DB_PORT=5432
```

The c-chain indexer tests need a MySQL carrying that indexer's schema, and
**skip cleanly when one is not configured** — a machine without it should not be
told the reader is broken:

```bash
export CCHAIN_DB_HOST=127.0.0.1 CCHAIN_DB_PORT=13306 \
       CCHAIN_DB_NAME=flare_csp_indexer CCHAIN_DB_USER=root CCHAIN_DB_PASSWORD=
```

Create the schema with the indexer's **own** migrator rather than transcribing
it — `database.ConnectAndInitialize` against an empty database is enough, and it
is the only way a fixture cannot drift from the thing it stands in for. The
end-to-end harness (`csp-e2e`) already runs exactly this MySQL on port 13306.

## Migrations

`manage.py` cannot run offline: `configuration/config.py` builds its
`Configuration` at import time and refuses to start without an `RPC_URL`
pointing at a recognised Flare chain, because it resolves `Relay` through
`FlareContractRegistry`. System checks import the URL conf, which imports that
config, so every management command inherits the requirement.

Migrations do not actually need any of it, so:

```bash
uv run python manage.py makemigrations dal --skip-checks
uv run python manage.py migrate --skip-checks
uv run python manage.py makemigrations --check --dry-run --skip-checks   # no drift
```

**The vectors come from Go.** See [`tests/README.md`](tests/README.md) — that is
the part of this app most worth understanding before changing it.


## Running it

Two long-running processes, shaped like `process_ftso_data` and
`delete_history` and deployed the same way — one container each, same image,
differing only in command:

```bash
python manage.py collect_dal --contract 0x… --from-block 0
python manage.py dal_delete_history
```

`docker-compose.yaml` carries both as `collect-dal` and `dal-delete-history`.
They are **optional**: without `CCHAIN_DB_HOST` there is no indexer to read
triggers from and the collector has nothing to do.

`--once` runs a single tick and exits, which is what to reach for when
debugging; the default loops until killed.

**The c-chain indexer must be configured to collect the instruction contract's
logs.** It filters before this service sees anything, so an address missing
from its `collect_logs` yields an indexer that is healthy, fresh and silent —
and a DAL that reports a quiet chain.

`dal_delete_history` is deliberately separate from the existing
`delete_history`. That one prunes FTSO and FDC rounds by voting round; this
prunes artifacts by their own lifecycle, and the two must not share a schedule.
