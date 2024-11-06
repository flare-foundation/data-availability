# CONTRIBUTING

## Dev environment

### docker

Create a `.env` file from `.env.example.dev` and fill it out.

```bash
# build containers
docker compose build
# start containers
docker compose up -d
```

### python for lsp and lint

Install python 3.12.7.

```bash
python -m venv venv
source ./venv/bin/activate
pip install -U -r requirements.txt dev-requirements.txt
```

### lint & format

```bash
# install git precomit hooks
pre-commit install

# run lint
ruff check
# autofix errors
ruff check --fix

# run code formatter
ruff format
```

### tests

Since we are running Django in Docker, tests need to be run in Docker as well; you can run them like this:

```bash
docker compose exec appserver python manage.py test
```
