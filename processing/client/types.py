from attr import frozen


@frozen
class FtsoRandomResponse:
    isSecure: bool
    value: str
    votingRoundId: int


@frozen
class FtsoVotingResponse:
    decimals: int
    id: str
    turnoutBIPS: int
    value: int
    votingRoundId: int


@frozen
class FtsoDataResponse:
    status: str
    protocolId: int
    votingRoundId: int
    merkleRoot: str
    isSecureRandom: bool
    random: FtsoRandomResponse
    medians: list[FtsoVotingResponse]
