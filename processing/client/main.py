from attr import frozen
from requests import Session

from processing.client.types import FdcDataResponse, FtsoDataResponse


@frozen
class BaseClientConfig:
    url: str
    api_key: str
    logging_name: str


class _BaseClient:
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

    def _validation_status_check(self, response):
        if "status" not in response:
            return False
        if "status" in response and response["status"] != "OK":
            return False
        return True


class FtsoClient(_BaseClient):
    def get_data(self, voting_round_id: int) -> FtsoDataResponse:
        response = self._get(f"/data/{voting_round_id}")
        response.raise_for_status()
        res = response.json()
        assert isinstance(res, dict)
        assert self._validation_status_check(res), "Status not successful (OK)"

        if "tree" not in res:
            raise Exception("Tree not in response")

        if len(res["tree"]) < 1:
            raise Exception("Tree is empty")

        res["random"] = res["tree"][0]
        res["medians"] = res["tree"][1:]
        del res["tree"]
        try:
            return FtsoDataResponse(**res)
        except Exception as e:
            raise e


class FdcClient(_BaseClient):
    def get_data(self, voting_round_id: int) -> FdcDataResponse:
        response = self._get(f"/da/getAttestations/{voting_round_id}")
        response.raise_for_status()
        res = response.json()
        assert isinstance(res, dict)
        assert self._validation_status_check(res), "Status not successful (OK)"
        try:
            return FdcDataResponse(**res)
        except Exception as e:
            raise e
