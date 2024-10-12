# flare-da-client

install python 3.12 if not yet installed
```sh
pyenv install 3.12.3
```

set up dev environment
```sh
pyenv virtualenv 3.12.3 flare-da-client
pyenv local flare-da-client
pip install -U -r project/requirements/local.txt
```


if you don't have it yet get [afh](https://git.aflabs.org/janezic.matej/afh) here

set up docker
```sh
cp .env.example .env
afh build
afh up
afh migrate
```

if you have a dump
```sh
afh import dumps/dump_file
```

## lint & format
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
