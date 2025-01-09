import os

from django.conf import settings

from configuration.contract_types import Contracts
from configuration.types import (
    Configuration,
    EpochSettings,
    ProtocolConfig,
    SyncingConfig,
    parse_protocol_providers,
)


def get_config() -> Configuration:
    CHAIN = settings.CONFIG_MODULE
    e = os.environ
    RPC_URL = e.get("RPC_URL")
    if RPC_URL is None:
        raise ValueError("RPC_URL must be set")

    epoch_settings = EpochSettings.from_json(
        f"configuration/chain/{CHAIN}/config.json",
        first_v2_reward_epoch=183,
    )

    contracts = Contracts.from_json(f"configuration/chain/{CHAIN}/contracts.json")

    ftso_provider = ProtocolConfig(
        protocol_id=100,
        providers=parse_protocol_providers("FTSO"),
    )

    fdc_provider = ProtocolConfig(
        protocol_id=200,
        providers=parse_protocol_providers("FDC"),
    )

    starting_config = SyncingConfig(
        start_height=int(e.get("INDEXING_DEFAULT_HEIGHT", "73422149")),
        max_processing_block_batch=int(e.get("INDEXING_BATCH_SIZE", "30")),
        processing_sleep_cycle=int(e.get("INDEXING_SLEEP_CYCLE", "20")),
    )

    return Configuration(
        rpc_url=RPC_URL,
        epoch_settings=epoch_settings,
        ftso=ftso_provider,
        fdc=fdc_provider,
        contracts=contracts,
        syncing_config=starting_config,
    )
