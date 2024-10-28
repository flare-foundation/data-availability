import json
import logging
from unittest.mock import MagicMock, patch

from django.test import TestCase

from configuration.types import ProtocolConfig
from fsp.models import ProtocolMessageRelayed
from ftso.models import FeedResult, RandomResult
from processing.client.main import FtsoClient
from processing.client.types import FtsoDataResponse, FtsoRandomResponse, FtsoVotingResponse
from processing.ftso_processing import FtsoProcessor

# DISABLE LOGGING
logging.disable(logging.CRITICAL)


class FtsoClientTest(TestCase):
    def setUp(self):
        self.FTSOclient = FtsoClient("", "", "")

    def test_get_data(self):
        with open("ftso/tests/testing_data.json") as json_data:
            data = json.load(json_data)

        response = MagicMock()
        response.json.return_value = data
        response.raise_for_status.return_value = None
        with patch("processing.client.main.FtsoClient._get", return_value=response):
            data_response = self.FTSOclient.get_data(0)

        self.assertEqual(isinstance(data_response, FtsoDataResponse), True)
        self.assertEqual(data_response.status, "OK")
        self.assertEqual(data_response.protocolId, 100)
        self.assertEqual(data_response.votingRoundId, 785250)
        self.assertEqual(data_response.merkleRoot, "0x9124d58e40bb8ad0cfb8c022e49d103d487d4cf7a23d57077dd9d726e316730a")
        self.assertEqual(data_response.isSecureRandom, True)
        self.assertEqual(isinstance(data_response.random, FtsoRandomResponse), True)
        self.assertEqual(data_response.random.isSecure, True)
        self.assertEqual(
            data_response.random.value, "0x54f2ca3184ad459bc8e518496602f2bb1e414902a47e15a388a11b8255565f82"
        )
        self.assertEqual(data_response.random.votingRoundId, 785250)
        self.assertEqual(len(data_response.medians), 71)
        ftso_voting_response = data_response.medians[0]
        self.assertEqual(isinstance(ftso_voting_response, FtsoVotingResponse), True)
        self.assertEqual(ftso_voting_response.decimals, 4)
        self.assertEqual(ftso_voting_response.id, "0x01414156452f555344000000000000000000000000")
        self.assertEqual(ftso_voting_response.turnoutBIPS, 9280)
        self.assertEqual(ftso_voting_response.value, 1563326)
        self.assertEqual(ftso_voting_response.votingRoundId, 785250)


class FtsoProcessorTest(TestCase):
    def setUp(self):
        self.FTSOclient = FtsoClient("", "", "")
        self.root = ProtocolMessageRelayed(
            block=1,
            protocol_id=100,
            voting_round_id=785250,
            is_secure_random=True,
            merkle_root="9124d58e40bb8ad0cfb8c022e49d103d487d4cf7a23d57077dd9d726e316730a",
        )
        self.FTSOprocessor = FtsoProcessor(ProtocolConfig(protocol_id=100, providers=[]))

        with open("ftso/tests/testing_data.json") as json_data:
            self.data = json.load(json_data)

        response = MagicMock()
        response.json.return_value = self.data
        response.raise_for_status.return_value = None
        with patch("processing.client.main.FtsoClient._get", return_value=response):
            self.parsed_response = self.FTSOclient.get_data(0)
        with patch("processing.client.main.FtsoClient.get_data", return_value=self.parsed_response):
            processed_data = self.FTSOprocessor.process_single_provider(self.root, self.FTSOclient)
        assert processed_data is not None
        self.rand, self.res = processed_data

    def test_process_single_provider(self):
        assert self.rand is not None and self.res is not None
        self.assertEqual(len(self.rand), 1)
        rand = self.rand[0]
        self.assertEqual(isinstance(rand, RandomResult), True)
        self.assertEqual(rand.voting_round_id, 785250)
        self.assertEqual(rand.value, "54f2ca3184ad459bc8e518496602f2bb1e414902a47e15a388a11b8255565f82")
        self.assertEqual(rand.is_secure, True)
        self.assertEqual(len(self.res), 71)
        res = self.res[0]
        self.assertEqual(isinstance(res, FeedResult), True)
        self.assertEqual(res.voting_round_id, 785250)
        self.assertEqual(res.feed_id, "01414156452f555344000000000000000000000000")
        self.assertEqual(res.value, 1563326)
        self.assertEqual(res.turnout_bips, 9280)
        self.assertEqual(res.decimals, 4)

    def test_process(self):
        with patch("processing.ftso_processing.FtsoProcessor.fetch_merkle_tree", return_value=(self.rand, self.res)):
            self.FTSOprocessor.process(self.root)

        self.assertEqual(RandomResult.objects.count(), 1)
        random_result = RandomResult.objects.first()
        assert random_result is not None
        self.assertEqual(random_result.voting_round_id, 785250)
        self.assertEqual(random_result.value, "54f2ca3184ad459bc8e518496602f2bb1e414902a47e15a388a11b8255565f82")
        self.assertEqual(random_result.is_secure, True)

        self.assertEqual(FeedResult.objects.count(), 71)

        feed_results = FeedResult.objects.all()
        for feed in self.data["tree"][1:]:
            filtered = list(
                filter(
                    lambda obj: obj.voting_round_id == feed["votingRoundId"]
                    and obj.feed_id == feed["id"][2:]
                    and obj.value == feed["value"]
                    and obj.turnout_bips == feed["turnoutBIPS"]
                    and obj.decimals == feed["decimals"],
                    feed_results,
                )
            )
            self.assertEqual(len(filtered), 1)

        self.assertEqual(ProtocolMessageRelayed.objects.count(), 1)
        protocol_message_relayed = ProtocolMessageRelayed.objects.first()
        assert protocol_message_relayed is not None
        self.assertEqual(protocol_message_relayed.block, 1)
        self.assertEqual(protocol_message_relayed.protocol_id, 100)
        self.assertEqual(protocol_message_relayed.voting_round_id, 785250)
        self.assertEqual(protocol_message_relayed.is_secure_random, True)
        self.assertEqual(
            protocol_message_relayed.merkle_root, "9124d58e40bb8ad0cfb8c022e49d103d487d4cf7a23d57077dd9d726e316730a"
        )
