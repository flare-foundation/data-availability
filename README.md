# data-availability

## Deployment

Create a `.env` file from `.env.example.prod` and fill it out.

You can then run the whole project with below example `docker-compose.yaml`.

```yaml
services:
  postgresdb:
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
    image: ${DOCKER_IMAGE_URL}
    env_file:
      - .env
    ports:
      - "127.0.0.1:${SERVER_PROXY_PORT}:3030"
    depends_on:
      - postgresdb
    restart: unless-stopped

  process-ftso-data:
    image: ${DOCKER_IMAGE_URL}
    command: start-process_ftso_data
    env_file:
      - .env
    depends_on:
      - postgresdb
    restart: unless-stopped

  process-fdc-data:
    image: ${DOCKER_IMAGE_URL}
    command: start-process_fdc_data
    env_file:
      - .env
    depends_on:
      - postgresdb
    restart: unless-stopped
```
