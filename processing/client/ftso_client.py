from attr import frozen
from requests import Session


@frozen
class BaseClientConfig:
    url: str
    api_key: str
    logging_name: str


class FtsoClient:
    def __init__(self, url: str, api_key: str, logging_name: str):
        session = Session()
        session.headers.update({"X-API-KEY": api_key})
        self.session = session
        self.url = url
        self.logging_name = logging_name

    @classmethod
    def from_config(cls, config: BaseClientConfig):
        return cls(config.url, config.api_key, config.logging_name)

    def __str__(self) -> str:
        return f"Client at {self.logging_name}"

    def _get(self, endpoint: str):
        return self.session.get(self.url + endpoint, timeout=20)

    def get_data(self, voting_round_id: int):
        response = self._get(f"/data/{voting_round_id}")
        response.raise_for_status()
        res = response.json()

        assert isinstance(res, dict)

        return res
