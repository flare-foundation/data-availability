import logging
import os

from django.conf import settings

from configuration.contract_types import Contracts
from configuration.types import (
    Configuration,
    EpochSettings,
    ProtocolConfig,
    ProtocolProvider,
    SyncingConfig,
)

logger = logging.getLogger(__name__)


def parse_protocol_providers(protocol_prefix: str) -> list[ProtocolProvider]:
    assert protocol_prefix in ["FTSO", "FDC"], f"unknown protocol {protocol_prefix}"

    e = os.environ

    provider_names = e.get(f"{protocol_prefix}_PROVIDER_LOGGING_NAMES")
    provider_urls = e.get(f"{protocol_prefix}_PROVIDER_URLS")
    provider_keys = e.get(f"{protocol_prefix}_PROVIDER_API_KEYS")

    providers = zip((provider_names, provider_urls, provider_keys), ("names", "urls", "keys"))

    valid_config = True
    for provider, value in providers:
        if value is not None:
            continue
        valid_config = False
        logger.debug(f"{protocol_prefix} {provider} are not set.")

    if not valid_config:
        return []

    assert provider_names is not None and provider_urls is not None and provider_keys is not None

    provider_names = provider_names.split(",")
    provider_urls = provider_urls.split(",")
    provider_keys = provider_keys.split(",")

    if len(provider_urls) != len(provider_keys) != len(provider_names):
        raise ValueError(f"{protocol_prefix} provider names urls and keys must be of equal length (comma separated)")

    logger.debug(f"{protocol_prefix} providers ({len(provider_names)}): {provider_names}")

    return [
        ProtocolProvider(n, u, a or None)
        for n, u, a in zip(
            provider_names,
            provider_urls,
            provider_keys,
        )
    ]


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

    ftso_provider = ProtocolConfig(
        protocol_id=100,
        providers=parse_protocol_providers("FTSO"),
    )

    fdc_provider = ProtocolConfig(
        protocol_id=200,
        providers=parse_protocol_providers("FDC"),
    )

    return Configuration(
        rpc_url=RPC_URL,
        epoch_settings=epoch_settings,
        ftso=ftso_provider,
        fdc=fdc_provider,
        contracts=contracts,
        syncing_config=SyncingConfig(
            start_height=24862497,
            max_processing_block_batch=50,
            processing_sleep_cycle=5,
        ),
    )
