import json
from typing import Self

from attrs import field, frozen

from configuration.contract_types import Contracts
from processing.client.main import BaseClientConfig


@frozen
class EpochSettings:
    first_voting_round_start_ts: int
    voting_epoch_duration_seconds: int
    first_reward_epoch_start_voting_round_id: int
    reward_epoch_duration_in_voting_epochs: int
    first_v2_reward_epoch: int
    ftso_reveal_deadline_seconds: int = field(init=False, default=20)
    # TODO:(matej) might be able to pick this up from somewhere else

    _ATTRIBUTE_MAPPER = (
        ("firstVotingRoundStartTs", "first_voting_round_start_ts"),
        ("votingEpochDurationSeconds", "voting_epoch_duration_seconds"),
        (
            "firstRewardEpochStartVotingRoundId",
            "first_reward_epoch_start_voting_round_id",
        ),
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
    protocol_id: int
    client_configs: list[BaseClientConfig]


@frozen
class SyncingConfig:
    start_height: int
    max_processing_block_batch: int
    processing_sleep_cycle: int


@frozen
class Configuration:
    rpc_url: str
    epoch_settings: EpochSettings
    ftso_provider: ProtocolProvider
    fdc_provider: ProtocolProvider
    contracts: Contracts
    syncing_config: SyncingConfig
