import logging
import os

from django.conf import settings

from configuration.contract_types import Contracts
from configuration.types import (
    Configuration,
    EpochSettings,
    ProtocolProvider,
    SyncingConfig,
)
from processing.client.ftso_client import BaseClientConfig

logger = logging.getLogger(__name__)


def get_config() -> Configuration:
    CHAIN = settings.CONFIG_MODULE
    e = os.environ
    RPC_URL = e.get("RPC_URL")
    if RPC_URL is None:
        raise ValueError("RPC_URL must be set")

    provider_names = e.get("FTSO_PROVIDER_LOGGING_NAMES", None)
    provider_urls = e.get("FTSO_PROVIDER_URLS", None)
    provider_keys = e.get("FTSO_PROVIDER_API_KEYS", None)

    if provider_urls is None or provider_keys is None or provider_names is None:
        raise ValueError("FTSO provider names, urls and keys must be set")

    provider_names = provider_names.split(",")
    provider_urls = provider_urls.split(",")
    provider_keys = provider_keys.split(",")

    if len(provider_urls) != len(provider_keys) != len(provider_names):
        raise ValueError("FTSO provider names urls and keys must be of equal length (comma separated)")

    logger.info(f"FTSO providers ({len(provider_names)}): {provider_names}")

    epoch_settings = EpochSettings.from_json(
        f"configuration/chain/{CHAIN}/config.json",
        first_v2_reward_epoch=2466,
    )

    contracts = Contracts.default()

    return Configuration(
        rpc_url=RPC_URL,
        epoch_settings=epoch_settings,
        ftso_provider=ProtocolProvider(
            protocol_id=100,
            client_configs=[
                BaseClientConfig(logging_name=name, url=url, api_key=key)
                for name, url, key in zip(provider_names, provider_urls, provider_keys, strict=True)
            ],
        ),
        fdc_provider=ProtocolProvider(
            protocol_id=200,
            client_configs=[],
        ),
        contracts=contracts,
        syncing_config=SyncingConfig(
            start_height=23_970_000,
            max_processing_block_batch=50,
            processing_sleep_cycle=5,
        ),
    )
