import json
import logging
from unittest.mock import MagicMock, patch

from django.test import TestCase

from configuration.types import ProtocolConfig
from fsp.models import ProtocolMessageRelayed
from ftso.models import FeedResult, RandomResult
from processing.client.main import FtsoClient
from processing.client.types import FtsoDataResponse, FtsoRandomResponse, FtsoVotingResponse
from processing.ftso_processing import FtsoProcessor, process_single_provider

# DISABLE LOGGING
logging.disable(logging.CRITICAL)


class FtsoClientTest(TestCase):
    def setUp(self):
        self.FTSOclient = FtsoClient("", "", "")

    def test_get_data(self):
        with open("ftso/test/testing_data.json") as json_data:
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

        with open("ftso/test/testing_data.json") as json_data:
            data = json.load(json_data)

        response = MagicMock()
        response.json.return_value = data
        response.raise_for_status.return_value = None
        with patch("processing.client.main.FtsoClient._get", return_value=response):
            self.parsed_response = self.FTSOclient.get_data(0)
        with patch("processing.client.main.FtsoClient.get_data", return_value=self.parsed_response):
            processed_data = process_single_provider(self.root, self.FTSOclient)
        assert processed_data is not None
        self.rand, self.res = processed_data

    def test_process_single_provider(self):
        assert self.rand is not None and self.res is not None
        self.assertEqual(len(self.rand), 1)
        self.assertEqual(isinstance(self.rand[0], RandomResult), True)
        self.assertEqual(self.rand[0].voting_round_id, 785250)
        self.assertEqual(self.rand[0].value, "54f2ca3184ad459bc8e518496602f2bb1e414902a47e15a388a11b8255565f82")
        self.assertEqual(self.rand[0].is_secure, True)
        self.assertEqual(len(self.res), 71)
        self.assertEqual(isinstance(self.res[0], FeedResult), True)
        self.assertEqual(self.res[0].voting_round_id, 785250)
        self.assertEqual(self.res[0].feed_id, "01414156452f555344000000000000000000000000")
        self.assertEqual(self.res[0].value, 1563326)
        self.assertEqual(self.res[0].turnout_bips, 9280)
        self.assertEqual(self.res[0].decimals, 4)

    def test_process(self):
        with patch(
            "processing.ftso_processing.FtsoProcessor.fetch_ftso_merkle_tree", return_value=(self.rand, self.res)
        ):
            self.FTSOprocessor.process(self.root)

        self.assertEqual(RandomResult.objects.count(), 1)
        random_result = RandomResult.objects.first()
        assert random_result is not None
        self.assertEqual(random_result.voting_round_id, 785250)
        self.assertEqual(random_result.value, "54f2ca3184ad459bc8e518496602f2bb1e414902a47e15a388a11b8255565f82")
        self.assertEqual(random_result.is_secure, True)

        self.assertEqual(FeedResult.objects.count(), 71)
        feed_result = FeedResult.objects.first()
        assert feed_result is not None
        self.assertEqual(feed_result.voting_round_id, 785250)
        self.assertEqual(feed_result.feed_id, "01414156452f555344000000000000000000000000")
        self.assertEqual(feed_result.value, 1563326)
        self.assertEqual(feed_result.turnout_bips, 9280)
        self.assertEqual(feed_result.decimals, 4)

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
