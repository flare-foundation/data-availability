<p align="left">
  <a href="https://flare.network/" target="blank"><img src="https://flare.network/wp-content/uploads/Artboard-1-1.svg" width="400" height="300" alt="Flare Logo" /></a>
</p>

# Data Availability

Data availability ensures that protocol data is accessible and verifiable by network participants after it has been published.

It connects to the blockchain to retrieve the Protocol message relayed, which contains the Merkle trees of the protocols (FTSO and FDC). It then connects to the protocol's data providers (FTSO Client and FDC Client) to receive their data. Using this data, it constructs a Merkle tree and compares it with the one from the `ProtocolMessageRelayed` event. If the roots of both trees match, the data from the providers is then loaded into the database.

## Protocols

**FTSO Protocol:** Data availability saves the following FTSO protocol data to the database:

- Protocol message relayed: includes block, protocol ID, voting round ID, Merkle root and security status.
- Random result: includes voting round ID, value and security status.
- Voting result: includes voting round ID, feed ID, value, turnout (in BIPS) and decimal.

**FDC Protocol:** Data availability saves the following FDC protocol data to the database:

- Protocol message relayed: includes block, protocol ID, voting round ID, Merkle root and security status.
- Attestation result: includes voting round ID, attestation request (hex), attestation response (hex), ABI and Merkle proof.

## API

If you have `SERVER_PROXY_PORT` set to `8000` in your `.env` file, you can find the raw YAML schema at `localhost:8000/_api_schema` and the Flare Data Availability Client API documentation at `localhost:8000/api-doc`.

## Deployment

Create a `.env` file from `.env.example.prod` and complete it with the necessary information. If you only want to use data availability for one protocol, comment out the other. 

```
docker compose pull
docker compose up -d
```
