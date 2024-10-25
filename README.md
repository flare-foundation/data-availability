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

# deployment
services:
  postgresdb:
    container_name: ${COMPOSE_PROJECT_NAME}_db
    image: postgres:16
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "127.0.0.1:${DB_PROXY_PORT}:5432"
    restart: unless-stopped
    volumes:
      - ./db-data/:/var/lib/postgresql/data

  appserver:
    container_name: ${COMPOSE_PROJECT_NAME}_server
    image: ${DOCKER_IMAGE_URL}
    env_file:
      - .env
    ports:
      - "127.0.0.1:${LISTEN_PORT}:3030"
    depends_on:
      - postgresdb
    restart: unless-stopped

  process-ftso-data:
    container_name: ${COMPOSE_PROJECT_NAME}_process_ftso_data
    image: ${DOCKER_IMAGE_URL}
    command: start-process_ftso_data
    env_file:
      - .env
    depends_on:
      - postgresdb
    restart: unless-stopped

  process-fdc-data:
    container_name: ${COMPOSE_PROJECT_NAME}_process_fdc_data
    image: ${DOCKER_IMAGE_URL}
    command: start-process_fdc_data
    env_file:
      - .env
    depends_on:
      - postgresdb
    restart: unless-stopped
