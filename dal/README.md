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

The project targets Python 3.14 and `uv`. The `dal` package deliberately depends
on nothing Django-specific, so its tests run under a plain virtualenv with four
packages:

```bash
python3 -m venv .venv
.venv/bin/pip install eth-utils eth-keys eth-abi "eth-hash[pycryptodome]" pytest
PYTHONPATH=. .venv/bin/python -m pytest dal/tests -q -c /dev/null
```

`-c /dev/null` skips the project's pytest configuration, which loads Django
settings this app does not need. Under the project's own toolchain, plain
`pytest dal/tests` works and is what CI should run.

**The vectors come from Go.** See [`tests/README.md`](tests/README.md) — that is
the part of this app most worth understanding before changing it.
