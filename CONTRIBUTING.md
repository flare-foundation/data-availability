# Contributing

This document describes the process of contributing to this project. It is
intended for anyone considering opening an issue or pull request.

## AI Assistance

> [!IMPORTANT]
>
> If you are using **any kind of AI assistance** to contribute to this project,
> it must be disclosed in the pull request.

If you are using any kind of AI assistance while contributing to this project,
**this must be disclosed in the pull request**, along with the extent to which
AI assistance was used. Trivial tab-completion doesn't need to be disclosed, as
long as it is limited to single keywords or short phrases.

An example disclosure:

> This PR was written primarily by Claude Code.

Or a more detailed disclosure:

> I consulted ChatGPT to understand the codebase but the solution was fully
> authored manually by myself.

## Quick start

If you'd like to contribute, report a bug, suggest a feature or you've
implemented a feature you should open an issue or pull request.

Any contribution to the project is expected to contain code that is formatted,
linted and that the existing tests still pass. Adding unit tests for new code is
also welcome.

## Dev environment

### Docker

Create a `.env` file from `.env.example.dev` and fill it out.

```bash
docker compose build
docker compose up -d
```

### Native

Install python 3.14 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

### Linting and formatting

```bash
# install git pre-commit hooks
pre-commit install

# run lint
uv run ruff check
# autofix errors
uv run ruff check --fix

# run code formatter
uv run ruff format
```

### Testing

```bash
# run tests (requires a running postgres instance)
uv run pytest

# run tests with coverage
uv run pytest --cov
```
