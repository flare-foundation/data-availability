from attr import frozen

# FTSO data types


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


# FDC data types


@frozen
class FdcAttestationResponse:
    roundId: int
    request: str
    response: str
    abi: str
    proof: list[str]


@frozen
class FdcDataResponse:
    Status: str
    Attestations: list[FdcAttestationResponse]
