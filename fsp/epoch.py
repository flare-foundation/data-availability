import time
from typing import Self

from configuration.config import config


class Epoch:
    _FIRST_EPOCH_TS: int
    _EPOCH_DURATION: int

    def __init__(self, n: int) -> None:
        self.n: int = n

    def __eq__(self, other) -> bool:
        return self.n == other.n

    def next(self) -> Self:
        return type(self)(self.n + 1)

    def previous(self) -> Self:
        return type(self)(self.n - 1)

    @property
    def start_s(self) -> int:
        return self._FIRST_EPOCH_TS + self.n * self._EPOCH_DURATION

    @property
    def end_s(self) -> int:
        return self.next().start_s

    @classmethod
    def duration(cls) -> int:
        return cls._EPOCH_DURATION

    @classmethod
    def from_timestamp(cls, ts: int) -> Self:
        return cls((ts - cls._FIRST_EPOCH_TS) // cls._EPOCH_DURATION)

    @classmethod
    def now(cls) -> Self:
        return cls.from_timestamp(int(time.time()))

    @classmethod
    def now_id(cls) -> int:
        return cls.now().n


class VotingEpoch(Epoch):
    _FIRST_EPOCH_TS = config.epoch_settings.first_voting_round_start_ts
    _EPOCH_DURATION = config.epoch_settings.voting_epoch_duration_seconds

    def to_reward_epoch(self) -> "RewardEpoch":
        return RewardEpoch.from_timestamp(self.start_s)

    def reveal_deadline(self) -> int:
        return self.start_s + config.epoch_settings.ftso_reveal_deadline_seconds


class RewardEpoch(Epoch):
    _FIRST_EPOCH_TS = VotingEpoch(config.epoch_settings.first_reward_epoch_start_voting_round_id).start_s
    _EPOCH_DURATION = config.epoch_settings.reward_epoch_duration_in_voting_epochs * VotingEpoch.duration()

    @classmethod
    def from_voting_epoch(cls, voting_epoch: VotingEpoch) -> Self:
        return cls.from_timestamp(voting_epoch.start_s)

    def to_first_voting_epoch(self) -> VotingEpoch:
        return VotingEpoch.from_timestamp(self.start_s)
