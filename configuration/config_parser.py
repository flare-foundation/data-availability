import json
import os

from eth_utils.address import to_checksum_address
from py_flare_common.fsp.epoch.timing import coston, coston2, flare, songbird
from web3 import Web3

from configuration.contract_types import Contract
from configuration.types import (
    Configuration,
    Contracts,
    Epoch,
    ProtocolConfig,
    ProtocolProvider,
    SyncingConfig,
)

# NOTE:(matej) FlareContractRegistry smart contract always provides an up to date
# mapper ({name:address}) for all official Flare contracts. It is deployed on all 4
# chains on the SAME address and is guaranteed to never be redeployed. This is why we
# can hardcode it here
FLARE_CONTRACT_REGISTRY_ADDRESS = to_checksum_address(
    "0xaD67FE66660Fb8dFE9d6b1b4240d8650e30F6019"
)
FLARE_CONTRACT_REGISTRY_ABI = json.load(
    open("configuration/artifacts/FlareContractRegistry.json")
)


def get_epoch(chain_id: int) -> Epoch:
    match chain_id:
        case 14:  # flare
            return Epoch(
                voting_epoch=flare.voting_epoch,
                reward_epoch=flare.reward_epoch,
                voting_epoch_factory=flare.voting_epoch_factory,
                reward_epoch_factory=flare.reward_epoch_factory,
            )
        case 114:  # coston2
            return Epoch(
                voting_epoch=coston2.voting_epoch,
                reward_epoch=coston2.reward_epoch,
                voting_epoch_factory=coston2.voting_epoch_factory,
                reward_epoch_factory=coston2.reward_epoch_factory,
            )
        case 19:  # songbird
            return Epoch(
                voting_epoch=songbird.voting_epoch,
                reward_epoch=songbird.reward_epoch,
                voting_epoch_factory=songbird.voting_epoch_factory,
                reward_epoch_factory=songbird.reward_epoch_factory,
            )
        case 16:  # coston
            return Epoch(
                voting_epoch=coston.voting_epoch,
                reward_epoch=coston.reward_epoch,
                voting_epoch_factory=coston.voting_epoch_factory,
                reward_epoch_factory=coston.reward_epoch_factory,
            )
        case _:
            raise ValueError("Unreachable code. Did you call this manually?")


class ConfigError(Exception):
    pass


def parse_protocol_providers(protocol_prefix: str) -> list[ProtocolProvider]:
    assert protocol_prefix in ["FTSO", "FDC"], f"unknown protocol {protocol_prefix}"

    e = os.environ

    provider_names = e.get(f"{protocol_prefix}_PROVIDER_LOGGING_NAMES")
    provider_urls = e.get(f"{protocol_prefix}_PROVIDER_URLS")
    provider_keys = e.get(f"{protocol_prefix}_PROVIDER_API_KEYS")

    if provider_names is None or provider_urls is None or provider_keys is None:
        return []

    provider_names = provider_names.split(",")
    provider_urls = provider_urls.split(",")
    provider_keys = provider_keys.split(",")

    if len(provider_urls) != len(provider_keys) != len(provider_names):
        raise ConfigError(
            f"{protocol_prefix} provider names, urls and keys must be of equal length (comma separated)"
        )

    return [
        ProtocolProvider(n, u, a or None)
        for n, u, a in zip(provider_names, provider_urls, provider_keys, strict=True)
    ]


def get_config() -> Configuration:
    e = os.environ
    rpc_url = e.get("RPC_URL")

    if rpc_url is None:
        raise ConfigError("RPC_URL environment variable must be set.")

    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        raise ConfigError(f"Unable to connect to rpc with provided {rpc_url=}")

    chain_id = w3.eth.chain_id

    if chain_id not in [16, 114, 19, 14]:
        raise ConfigError(f"Detected unknown chain ({chain_id=})")

    epoch = get_epoch(w3.eth.chain_id)

    registry = w3.eth.contract(
        address=FLARE_CONTRACT_REGISTRY_ADDRESS,
        abi=FLARE_CONTRACT_REGISTRY_ABI,
    )

    relay_address = to_checksum_address(
        registry.functions.getContractAddressByName("Relay").call()
    )

    contracts = Contracts(
        relay=Contract(
            name="Relay",
            address=relay_address,
            abi="configuration/artifacts/Relay.json",
        )
    )

    ftso_provider = ProtocolConfig(
        protocol_id=100,
        providers=parse_protocol_providers("FTSO"),
    )

    fdc_provider = ProtocolConfig(
        protocol_id=200,
        providers=parse_protocol_providers("FDC"),
    )

    starting_config = SyncingConfig(
        start_height=int(e.get("INDEXING_DEFAULT_HEIGHT", w3.eth.block_number)),
        max_processing_block_batch=int(e.get("INDEXING_BATCH_SIZE", "30")),
        processing_sleep_cycle=int(e.get("INDEXING_SLEEP_CYCLE", "20")),
    )

    return Configuration(
        rpc_url=rpc_url,
        epoch=epoch,
        ftso=ftso_provider,
        fdc=fdc_provider,
        syncing_config=starting_config,
        contracts=contracts,
    )
