<p align="left">
  <a href="https://flare.network/" target="blank"><img src="https://flare.network/wp-content/uploads/Artboard-1-1.svg" width="400" height="300" alt="Flare Logo" /></a>
</p>

# Data Availability

Data availability ensures that protocol data is accessible and verifiable by network participants after it has been published.

It connects to the blockchain to retrieve the Protocol message relayed, which contains the merkle trees of the protocols (FTSO and FDC). It then connects to the protocol's data providers (FTSO Client and FDC Client) to receive there data. Using this data, it constructs a merkle tree and compares it with the one from the ProtocolMessageRelayed. If the roots of both trees match, the data from the providers is then loaded into the database.

## Protocols

**FTSO Protocol:** Data availability saves the following FTSO protocol data to the database:

- Protocol message relayed: includes block, protocol ID, voting round ID, merkle root and security status.
- Random result: includes voting round ID, value and security status.
- Voting result: includes voting round ID, feed ID, value, turnout (in BIPS) and decimal.

**FDC Protocol:** Data availability saves the following FDC protocol data to the database:

- Protocol message relayed: includes block, protocol ID, voting round ID, merkle root and security status.
- Attestation result: includes voting round ID, attestation request (hex), attestation response (hex), ABI and merkle proof.

## API

If you have `SERVER_PROXY_PORT` set to `8000` in your `.env` file, you can find the raw YAML schema at `localhost:8000/_api_schema` and the Flare Data Availability Client API documentation at `localhost:8000/api-doc`.

## Deployment

Create a `.env` file from `.env.exampl.prod` and complete it with the necessary information. If you only want to use data availability for one protocol, comment out the other.

You can then run the whole project with below example `docker-compose.yaml`.

```yaml
x-django: &django
  image: local/data-availability
  env_file:
    - .env
  restart: unless-stopped

services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready", "-d", "${DB_NAME}"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - pg_data:/var/lib/postgresql/data

  django:
    <<: *django
    ports:
      - "127.0.0.1:${SERVER_PROXY_PORT}:8000"
    healthcheck:
      test: ["CMD", "curl", "--fail", "http://localhost:8000/api/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    depends_on:
      db:
        condition: service_healthy

  process-ftso-data:
    <<: *django
    command: python manage.py process_ftso_data
    depends_on:
      db:
        condition: service_healthy
      django:
        condition: service_healthy

  process-fdc-data:
    <<: *django
    command: python manage.py process_fdc_data
    depends_on:
      db:
        condition: service_healthy
      django:
        condition: service_healthy

volumes:
  pg_data:
```
