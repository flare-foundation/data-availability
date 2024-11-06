import logging

import cattrs
from requests import Session

from configuration.types import ProtocolProvider
from processing.client.types import FdcDataResponse, FtsoDataResponse

logger = logging.getLogger(__name__)


class BaseClient:
    status_keyword = "status"

    def __init__(self, url: str, api_key: str | None, logging_name: str):
        session = Session()
        if api_key is not None:
            session.headers.update({"X-API-KEY": api_key})
        self.session = session
        self.url = url
        self.logging_name = logging_name

    @classmethod
    def from_config(cls, config: ProtocolProvider):
        return cls(config.url, config.api_key, config.name)

    def __str__(self) -> str:
        return f"Client <{self.logging_name}>"

    def _get(self, endpoint: str):
        return self.session.get(self.url + endpoint, timeout=20)

    def _validation_status_check(self, response):
        if self.status_keyword not in response:
            return False
        if response[self.status_keyword] != "OK":
            return False
        return True


class FtsoClient(BaseClient):
    def get_data(self, voting_round_id: int) -> FtsoDataResponse:
        request_url = f"/data/{voting_round_id}"
        response = self._get(request_url)
        response.raise_for_status()
        res = response.json()
        assert isinstance(res, dict)
        assert self._validation_status_check(
            res
        ), f"Status not successful (OK) {request_url}"

        if "tree" not in res:
            raise Exception("Tree not in response")

        if len(res["tree"]) == 0:
            raise Exception("Tree is empty")

        res["random"] = res["tree"][0]
        res["medians"] = res["tree"][1:]
        try:
            return cattrs.structure(res, FtsoDataResponse)
        except Exception as e:
            raise e


class FdcClient(BaseClient):
    status_keyword = "Status"

    def get_data(self, voting_round_id: int) -> FdcDataResponse:
        request_url = f"/getAttestations/{voting_round_id}"
        response = self._get(request_url)
        response.raise_for_status()
        res = response.json()
        assert isinstance(res, dict)
        assert self._validation_status_check(
            res
        ), f"Status not successful (OK) {request_url}"
        try:
            return cattrs.structure(res, FdcDataResponse)
        except Exception as e:
            logger.error("Error parsing FdcDataResponse")
            raise e
