import logging
import os

from attr import frozen
from django.conf import settings

from configuration.contract_types import Contracts
from configuration.types import (
    Configuration,
    EpochSettings,
    ProtocolProvider,
    SyncingConfig,
)
from processing.client.main import BaseClientConfig

logger = logging.getLogger(__name__)


@frozen
class ProviderCredentials:
    names: list[str]
    urls: list[str]
    keys: list[str]

    def iterate(self):
        return zip(self.names, self.urls, self.keys, strict=True)


def parse_protocol_providers(protocol_prefix: str) -> ProviderCredentials:
    e = os.environ

    provider_names = e.get(f"{protocol_prefix}_PROVIDER_LOGGING_NAMES", None)
    provider_urls = e.get(f"{protocol_prefix}_PROVIDER_URLS", None)
    provider_keys = e.get(f"{protocol_prefix}_PROVIDER_API_KEYS", None)

    if provider_urls is None or provider_keys is None or provider_names is None:
        raise ValueError(f"{protocol_prefix} provider names, urls and keys must be set")

    provider_names = provider_names.split(",")
    provider_urls = provider_urls.split(",")
    provider_keys = provider_keys.split(",")

    if len(provider_urls) != len(provider_keys) != len(provider_names):
        raise ValueError(f"{protocol_prefix} provider names urls and keys must be of equal length (comma separated)")

    logger.info(f"{protocol_prefix} providers ({len(provider_names)}): {provider_names}")

    return ProviderCredentials(names=provider_names, urls=provider_urls, keys=provider_keys)


def get_config() -> Configuration:
    CHAIN = settings.CONFIG_MODULE
    e = os.environ
    RPC_URL = e.get("RPC_URL")
    if RPC_URL is None:
        raise ValueError("RPC_URL must be set")

    epoch_settings = EpochSettings.from_json(
        f"configuration/chain/{CHAIN}/config.json",
        first_v2_reward_epoch=2466,
    )

    contracts = Contracts.default()

    ftso_providers = parse_protocol_providers("FTSO")
    fdc_providers = parse_protocol_providers("FDC")

    return Configuration(
        rpc_url=RPC_URL,
        epoch_settings=epoch_settings,
        ftso_provider=ProtocolProvider(
            protocol_id=100,
            client_configs=[
                BaseClientConfig(logging_name=name, url=url, api_key=key) for name, url, key in ftso_providers.iterate()
            ],
        ),
        fdc_provider=ProtocolProvider(
            protocol_id=200,
            client_configs=[
                BaseClientConfig(logging_name=name, url=url, api_key=key) for name, url, key in fdc_providers.iterate()
            ],
        ),
        contracts=contracts,
        syncing_config=SyncingConfig(
            start_height=24_256_750,
            max_processing_block_batch=50,
            processing_sleep_cycle=5,
        ),
    )
