import json
import logging
from unittest.mock import MagicMock, patch

from django.test import TestCase

from configuration.types import ProtocolConfig
from fdc.models import AttestationResult
from fsp.models import ProtocolMessageRelayed
from processing.client.main import FdcClient
from processing.client.types import FdcAttestationResponse, FdcDataResponse
from processing.fdc_processing import FdcProcessor

# DISABLE LOGGING
logging.disable(logging.CRITICAL)


class FdcClientTest(TestCase):
    def setUp(self):
        self.FDCclient = FdcClient("", "", "")

    def test_get_data(self):
        with open("fdc/tests/testing_data.json") as json_data:
            data = json.load(json_data)

        response = MagicMock()
        response.json.return_value = data
        response.raise_for_status.return_value = None
        with patch("processing.client.main.FdcClient._get", return_value=response):
            data_response = self.FDCclient.get_data(0)

        self.assertEqual(isinstance(data_response, FdcDataResponse), True)
        self.assertEqual(data_response.Status, "OK")
        self.assertEqual(len(data_response.Attestations), 14)
        attestation = data_response.Attestations[0]
        self.assertEqual(isinstance(attestation, FdcAttestationResponse), True)
        self.assertEqual(attestation.roundId, 792357)
        self.assertEqual(
            attestation.request,
            "45564d5472616e73616374696f6e00000000000000000000000000000000000074657374464c52000000000000000000000000000000000000000000000000000b2ad6d76e04b416ee083cc689a35c5938765f954504511d7f3e855079a7b9680000000000000000000000000000000000000000000000000000000000000020c426fd5743139c9a83d3b32af75c8570a4f59b491ee5b442767755977514222900000000000000000000000000000000000000000000000000000000000000050000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000a00000000000000000000000000000000000000000000000000000000000000000",
        )
        self.assertEqual(
            attestation.response,
            "000000000000000000000000000000000000000000000000000000000000002045564d5472616e73616374696f6e00000000000000000000000000000000000074657374464c520000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000c1725000000000000000000000000000000000000000000000000000000006719c4e600000000000000000000000000000000000000000000000000000000000000c00000000000000000000000000000000000000000000000000000000000000180c426fd5743139c9a83d3b32af75c8570a4f59b491ee5b442767755977514222900000000000000000000000000000000000000000000000000000000000000050000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000a000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000bf4de7000000000000000000000000000000000000000000000000000000006719c4e6000000000000000000000000c01b98523093ccca5d6473e0b11432ee7d150cdc00000000000000000000000000000000000000000000000000000000000000000000000000000000000000002ca6571daa15ce734bbd0bf27d5c9d16787fc33f000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001200000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000034000000000000000000000000000000000000000000000000000000000000001e4833bf6c0000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000001a000000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000bf4de20000000000000000000000000000000000000000000000000000000000000145000024b159c707f97e3eecb78c2e4f6bee6520e8b1d011d63a6367c293ec09a71f97f4d845e557de254f20e9a2cf6ea6f9fe62a455830b6451eefcc40c2d4f540ceb09b6d597b600e1d6bceafff5079595b7a1ecaae61cd7f02ca5251395650c1d008153441f1fadf76d8991409221d35780c8549b476db2b4c5e125da2211d40000000000000000000000000000000000000000000000000000000000000140000000000000000000000000000000000000000000000000000000000000001cca7af6d8d2339198ac5bc02832871175d287ae2ce09f240ed9db00e076f9916e2af6beaa26fe590c4216ec09f9a80495ee8636b5b88702ebaa32b712a8c9d301000000000000000000000000000000000000000000000000000000000000000d107f304300c01fcfcffc3f07f000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
        )
        self.assertEqual(
            attestation.abi,
            '{"components":[{"internalType":"bytes32","name":"attestationType","type":"bytes32"},{"internalType":"bytes32","name":"sourceId","type":"bytes32"},{"internalType":"uint64","name":"votingRound","type":"uint64"},{"internalType":"uint64","name":"lowestUsedTimestamp","type":"uint64"},{"components":[{"internalType":"bytes32","name":"transactionHash","type":"bytes32"},{"internalType":"uint16","name":"requiredConfirmations","type":"uint16"},{"internalType":"bool","name":"provideInput","type":"bool"},{"internalType":"bool","name":"listEvents","type":"bool"},{"internalType":"uint32[]","name":"logIndices","type":"uint32[]"}],"internalType":"structEVMTransaction.RequestBody","name":"requestBody","type":"tuple"},{"components":[{"internalType":"uint64","name":"blockNumber","type":"uint64"},{"internalType":"uint64","name":"timestamp","type":"uint64"},{"internalType":"address","name":"sourceAddress","type":"address"},{"internalType":"bool","name":"isDeployment","type":"bool"},{"internalType":"address","name":"receivingAddress","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"},{"internalType":"bytes","name":"input","type":"bytes"},{"internalType":"uint8","name":"status","type":"uint8"},{"components":[{"internalType":"uint32","name":"logIndex","type":"uint32"},{"internalType":"address","name":"emitterAddress","type":"address"},{"internalType":"bytes32[]","name":"topics","type":"bytes32[]"},{"internalType":"bytes","name":"data","type":"bytes"},{"internalType":"bool","name":"removed","type":"bool"}],"internalType":"structEVMTransaction.Event[]","name":"events","type":"tuple[]"}],"internalType":"structEVMTransaction.ResponseBody","name":"responseBody","type":"tuple"}],"internalType":"structEVMTransaction.Response","name":"data","type":"tuple"}',
        )
        self.assertEqual(
            attestation.proof,
            [
                "0xce0f21aac7dcd802146863d61d8ed1279e5fa35b0f13878b2abbc496b27e17a7",
                "0xd93757c9e702acc05d15350f44a7b730edf7c2afe2fb5568040865442f78c488",
                "0x81a4cf8785f22818137af2fbe252ef2767a64e27be338e55f17dec090c88fc9f",
                "0xc7b6e23e7b4ff0d0ad2618be56e3f0ab5bd519368652838872b942f847d32b80",
            ],
        )


class FdcProcessorTest(TestCase):
    def setUp(self):
        self.FDCclient = FdcClient("", "", "")
        self.root = ProtocolMessageRelayed(
            block=1,
            protocol_id=200,
            voting_round_id=792357,
            is_secure_random=True,
            merkle_root="dd4a35a73e76d1326be609b349fff9beccc6516ef60692425cdc14a78965c11c",
        )
        self.FDCprocessor = FdcProcessor(ProtocolConfig(protocol_id=200, providers=[]))

        with open("fdc/tests/testing_data.json") as json_data:
            self.data = json.load(json_data)

        response = MagicMock()
        response.json.return_value = self.data
        response.raise_for_status.return_value = None
        with patch("processing.client.main.FdcClient._get", return_value=response):
            self.parsed_response = self.FDCclient.get_data(0)
        with patch(
            "processing.client.main.FdcClient.get_data",
            return_value=self.parsed_response,
        ):
            self.leafs = self.FDCprocessor.process_single_provider(
                self.root, self.FDCclient
            )

    def test_process_single_fdc_provider(self):
        assert self.leafs is not None
        self.assertEqual(len(self.leafs), 14)
        self.assertEqual(isinstance(self.leafs[0], AttestationResult), True)
        self.assertEqual(self.leafs[0].voting_round_id, 792357)
        self.assertEqual(
            self.leafs[0].request_hex,
            "45564d5472616e73616374696f6e00000000000000000000000000000000000074657374464c52000000000000000000000000000000000000000000000000000b2ad6d76e04b416ee083cc689a35c5938765f954504511d7f3e855079a7b9680000000000000000000000000000000000000000000000000000000000000020c426fd5743139c9a83d3b32af75c8570a4f59b491ee5b442767755977514222900000000000000000000000000000000000000000000000000000000000000050000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000a00000000000000000000000000000000000000000000000000000000000000000",
        )
        self.assertEqual(
            self.leafs[0].response_hex,
            "000000000000000000000000000000000000000000000000000000000000002045564d5472616e73616374696f6e00000000000000000000000000000000000074657374464c520000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000c1725000000000000000000000000000000000000000000000000000000006719c4e600000000000000000000000000000000000000000000000000000000000000c00000000000000000000000000000000000000000000000000000000000000180c426fd5743139c9a83d3b32af75c8570a4f59b491ee5b442767755977514222900000000000000000000000000000000000000000000000000000000000000050000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000a000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000bf4de7000000000000000000000000000000000000000000000000000000006719c4e6000000000000000000000000c01b98523093ccca5d6473e0b11432ee7d150cdc00000000000000000000000000000000000000000000000000000000000000000000000000000000000000002ca6571daa15ce734bbd0bf27d5c9d16787fc33f000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001200000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000034000000000000000000000000000000000000000000000000000000000000001e4833bf6c0000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000001a000000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000bf4de20000000000000000000000000000000000000000000000000000000000000145000024b159c707f97e3eecb78c2e4f6bee6520e8b1d011d63a6367c293ec09a71f97f4d845e557de254f20e9a2cf6ea6f9fe62a455830b6451eefcc40c2d4f540ceb09b6d597b600e1d6bceafff5079595b7a1ecaae61cd7f02ca5251395650c1d008153441f1fadf76d8991409221d35780c8549b476db2b4c5e125da2211d40000000000000000000000000000000000000000000000000000000000000140000000000000000000000000000000000000000000000000000000000000001cca7af6d8d2339198ac5bc02832871175d287ae2ce09f240ed9db00e076f9916e2af6beaa26fe590c4216ec09f9a80495ee8636b5b88702ebaa32b712a8c9d301000000000000000000000000000000000000000000000000000000000000000d107f304300c01fcfcffc3f07f000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
        )
        self.assertEqual(
            self.leafs[0].abi,
            '{"components":[{"internalType":"bytes32","name":"attestationType","type":"bytes32"},{"internalType":"bytes32","name":"sourceId","type":"bytes32"},{"internalType":"uint64","name":"votingRound","type":"uint64"},{"internalType":"uint64","name":"lowestUsedTimestamp","type":"uint64"},{"components":[{"internalType":"bytes32","name":"transactionHash","type":"bytes32"},{"internalType":"uint16","name":"requiredConfirmations","type":"uint16"},{"internalType":"bool","name":"provideInput","type":"bool"},{"internalType":"bool","name":"listEvents","type":"bool"},{"internalType":"uint32[]","name":"logIndices","type":"uint32[]"}],"internalType":"structEVMTransaction.RequestBody","name":"requestBody","type":"tuple"},{"components":[{"internalType":"uint64","name":"blockNumber","type":"uint64"},{"internalType":"uint64","name":"timestamp","type":"uint64"},{"internalType":"address","name":"sourceAddress","type":"address"},{"internalType":"bool","name":"isDeployment","type":"bool"},{"internalType":"address","name":"receivingAddress","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"},{"internalType":"bytes","name":"input","type":"bytes"},{"internalType":"uint8","name":"status","type":"uint8"},{"components":[{"internalType":"uint32","name":"logIndex","type":"uint32"},{"internalType":"address","name":"emitterAddress","type":"address"},{"internalType":"bytes32[]","name":"topics","type":"bytes32[]"},{"internalType":"bytes","name":"data","type":"bytes"},{"internalType":"bool","name":"removed","type":"bool"}],"internalType":"structEVMTransaction.Event[]","name":"events","type":"tuple[]"}],"internalType":"structEVMTransaction.ResponseBody","name":"responseBody","type":"tuple"}],"internalType":"structEVMTransaction.Response","name":"data","type":"tuple"}',
        )
        self.assertEqual(
            self.leafs[0].proof,
            [
                "0xce0f21aac7dcd802146863d61d8ed1279e5fa35b0f13878b2abbc496b27e17a7",
                "0xd93757c9e702acc05d15350f44a7b730edf7c2afe2fb5568040865442f78c488",
                "0x81a4cf8785f22818137af2fbe252ef2767a64e27be338e55f17dec090c88fc9f",
                "0xc7b6e23e7b4ff0d0ad2618be56e3f0ab5bd519368652838872b942f847d32b80",
            ],
        )

    def test_process(self):
        with patch(
            "processing.fdc_processing.FdcProcessor.fetch_merkle_tree",
            return_value=self.leafs,
        ):
            self.FDCprocessor.process(self.root)

        self.assertEqual(AttestationResult.objects.count(), 14)

        attestation_results = AttestationResult.objects.all()
        for attestation in self.data["Attestations"]:
            filtered = list(
                filter(
                    lambda obj: obj.voting_round_id == attestation["roundId"]
                    and obj.request_hex == attestation["request"]
                    and obj.response_hex == attestation["response"]
                    and obj.abi == attestation["abi"]
                    and obj.proof == attestation["proof"],
                    attestation_results,
                )
            )
            self.assertEqual(len(filtered), 1)

        self.assertEqual(ProtocolMessageRelayed.objects.count(), 1)
        protocol_message_relayed = ProtocolMessageRelayed.objects.first()
        assert protocol_message_relayed is not None
        self.assertEqual(protocol_message_relayed.block, 1)
        self.assertEqual(protocol_message_relayed.protocol_id, 200)
        self.assertEqual(protocol_message_relayed.voting_round_id, 792357)
        self.assertEqual(protocol_message_relayed.is_secure_random, True)
        self.assertEqual(
            protocol_message_relayed.merkle_root,
            "dd4a35a73e76d1326be609b349fff9beccc6516ef60692425cdc14a78965c11c",
        )
