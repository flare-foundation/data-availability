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
