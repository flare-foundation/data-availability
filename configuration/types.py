import json
import logging
import os
from typing import Self

from attrs import field, frozen

from configuration.contract_types import Contracts


@frozen
class EpochSettings:
    first_voting_round_start_ts: int
    voting_epoch_duration_seconds: int
    first_reward_epoch_start_voting_round_id: int
    reward_epoch_duration_in_voting_epochs: int
    first_v2_reward_epoch: int
    ftso_reveal_deadline_seconds: int = field(init=False, default=45)

    _ATTRIBUTE_MAPPER = (
        ("firstVotingRoundStartTs", "first_voting_round_start_ts"),
        ("votingEpochDurationSeconds", "voting_epoch_duration_seconds"),
        ("firstRewardEpochStartVotingRoundId", "first_reward_epoch_start_voting_round_id"),
        ("rewardEpochDurationInVotingEpochs", "reward_epoch_duration_in_voting_epochs"),
    )

    @classmethod
    def from_json(cls, relative_path, *_, **kwargs) -> Self:
        with open(relative_path) as f:
            chain_config = json.load(f)
            kkwargs = {a: chain_config[m] for m, a in cls._ATTRIBUTE_MAPPER}
            return cls(**kkwargs, **kwargs)


@frozen
class ProtocolProvider:
    name: str
    url: str
    api_key: str | None


@frozen
class ProtocolConfig:
    protocol_id: int
    providers: list[ProtocolProvider]


@frozen
class SyncingConfig:
    start_height: int
    max_processing_block_batch: int
    processing_sleep_cycle: int


@frozen
class Configuration:
    rpc_url: str
    epoch_settings: EpochSettings
    ftso: ProtocolConfig
    fdc: ProtocolConfig
    contracts: Contracts
    syncing_config: SyncingConfig


logger = logging.getLogger(__name__)


def parse_protocol_providers(protocol_prefix: str) -> list[ProtocolProvider]:
    assert protocol_prefix in ["FTSO", "FDC"], f"unknown protocol {protocol_prefix}"

    e = os.environ

    provider_names = e.get(f"{protocol_prefix}_PROVIDER_LOGGING_NAMES")
    provider_urls = e.get(f"{protocol_prefix}_PROVIDER_URLS")
    provider_keys = e.get(f"{protocol_prefix}_PROVIDER_API_KEYS")

    providers = (provider_names, provider_urls, provider_keys)

    valid_config = True
    for provider in providers:
        if provider is not None:
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
