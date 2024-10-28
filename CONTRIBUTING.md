# CONTRIBUTING

## Dev environment

### docker 

Create a `.env` file from `.env.example.dev` and fill it out.

```
# build containers
docker compose build
# start containers
docker compose up -d
```

### python for lsp and lint

install python 3.12 if not yet installed (eg.: via `pyenv`)
```sh
pyenv install 3.12.3
pyenv virtualenv 3.12.3 data-availability
pyenv local data-availability
pip install -U -r requirements.txt dev-requirements.txt
```

### lint & format
```sh
# install git precomit hooks
pre-commit install

# run lint
ruff check
# autofix errors
ruff check --fix

# run code formatter
ruff format
```
