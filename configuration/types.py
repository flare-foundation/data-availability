from typing import Callable

from attrs import frozen
from py_flare_common.fsp.epoch.epoch import RewardEpoch, VotingEpoch
from py_flare_common.fsp.epoch.factory import RewardEpochFactory, VotingEpochFactory

from configuration.contract_types import Contract


@frozen
class Epoch:
    voting_epoch: Callable[[int], VotingEpoch]
    reward_epoch: Callable[[int], RewardEpoch]
    voting_epoch_factory: VotingEpochFactory
    reward_epoch_factory: RewardEpochFactory


@frozen
class Contracts:
    relay: Contract


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
    epoch: Epoch
    ftso: ProtocolConfig
    fdc: ProtocolConfig
    contracts: Contracts
    syncing_config: SyncingConfig
