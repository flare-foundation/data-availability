"""Trigger discovery: from one log to the expectations it implies.

The event is the reason this needs no registry: it carries
``(teeId, teeProxyId, url)`` for every machine, as they stood when the
instruction was sent. So the gate's identities come from the trigger itself, and
the at-block-versus-latest question does not arise for this message class.
"""

import dataclasses
from datetime import timedelta

import pytest
from eth_abi.abi import encode as abi_encode
from eth_utils.address import to_checksum_address
from eth_utils.crypto import keccak

from dal.chain.abi import TEE_INSTRUCTIONS_SENT, topic0
from dal.chain.indexer import LogRow, Window
from dal.chain.triggers import discover_tee_instructions
from dal.keys import action_result_key
from dal.models import Expectation

CONTRACT = "1234567890abcdef1234567890abcdef12345678"
INSTRUCTION = bytes.fromhex("a1" * 32)
# Checksummed, because web3's decoder returns the checksummed form and these
# values are compared against what it produced. The gate itself compares
# case-insensitively; the store records whatever the event decoded to.
MACHINE_A = to_checksum_address("0x2c7536e3605d9c16a7a3d7b1898e529396a65c23")
PROXY_A = to_checksum_address("0x" + "0" * 36 + "0aaa")
MACHINE_B = to_checksum_address("0x" + "0" * 36 + "0b0b")
PROXY_B = to_checksum_address("0x" + "0" * 36 + "0bbb")

SIGNATURE = (
    "TeeInstructionsSent(uint256,bytes32,uint32,(address,address,string)[],"
    "bytes32,bytes32,bytes,address[],uint64,address,uint256)"
)


def encode_log(machines, instruction=INSTRUCTION, block=10) -> LogRow:
    data = abi_encode(
        [
            "(address,address,string)[]",
            "bytes32",
            "bytes32",
            "bytes",
            "address[]",
            "uint64",
            "address",
            "uint256",
        ],
        [
            machines,
            b"\x01" * 32,
            b"\x02" * 32,
            b"payload",
            [],
            2,
            "0x" + "00" * 20,
            0,
        ],
    )
    return LogRow(
        address=CONTRACT,
        topic0=topic0(TEE_INSTRUCTIONS_SENT),
        topic1=f"{7:064x}",
        topic2=instruction.hex(),
        topic3=f"{3:064x}",
        data=data.hex(),
        transaction_hash="ab" * 32,
        log_index=0,
        block_number=block,
        timestamp=block * 10,
    )


class FakeReader:
    def __init__(self, rows, window=None):
        self.rows = rows
        self.window = window or Window(chain_tip=1000, last_indexed=900, log_floor=0)
        self.calls = []

    def logs(self, **kwargs):
        self.calls.append(kwargs)
        return self.rows, self.window


def test_the_topic_matches_the_canonical_signature():
    # A typo here produces a filter that matches nothing, which is
    # indistinguishable from a contract that never emitted.
    assert topic0(TEE_INSTRUCTIONS_SENT) == keccak(text=SIGNATURE).hex()


@pytest.mark.django_db
class TestDiscovery:
    def test_one_log_makes_an_expectation_per_machine_and_tag(self):
        rows = [
            encode_log(
                [
                    (MACHINE_A, PROXY_A, "http://a:9/"),
                    (MACHINE_B, PROXY_B, "http://b:9/"),
                ]
            )
        ]
        report = discover_tee_instructions(
            FakeReader(rows), contract_address=CONTRACT, from_block=0
        )
        assert report.expectations_created == 4
        assert Expectation.objects.count() == 4

    def test_the_keys_are_the_ones_the_store_will_serve(self):
        rows = [encode_log([(MACHINE_A, PROXY_A, "http://a:9/")])]
        discover_tee_instructions(
            FakeReader(rows), contract_address=CONTRACT, from_block=0
        )
        assert set(Expectation.objects.values_list("key", flat=True)) == {
            action_result_key(INSTRUCTION, MACHINE_A, "threshold").hex(),
            action_result_key(INSTRUCTION, MACHINE_A, "end").hex(),
        }

    def test_the_gates_identities_come_from_the_event(self):
        # No registry lookup, and therefore no question of reading state at the
        # wrong block: the trigger names both identities as they stood.
        rows = [encode_log([(MACHINE_A, PROXY_A, "http://a:9/")])]
        discover_tee_instructions(
            FakeReader(rows), contract_address=CONTRACT, from_block=0
        )
        params = Expectation.objects.first().params
        assert params["teeId"] == MACHINE_A
        assert params["proxyId"] == PROXY_A

    def test_the_origin_url_comes_from_the_event(self):
        rows = [encode_log([(MACHINE_A, PROXY_A, "http://a:9/")])]
        discover_tee_instructions(
            FakeReader(rows), contract_address=CONTRACT, from_block=0
        )
        assert Expectation.objects.first().origin == "http://a:9/"

    def test_seeing_a_trigger_twice_creates_nothing_new(self):
        # A restart, a reorg, or an overlapping scan must not double an
        # expectation -- and the unique key means it cannot.
        rows = [encode_log([(MACHINE_A, PROXY_A, "http://a:9/")])]
        discover_tee_instructions(
            FakeReader(rows), contract_address=CONTRACT, from_block=0
        )
        second = discover_tee_instructions(
            FakeReader(rows), contract_address=CONTRACT, from_block=0
        )
        assert second.expectations_created == 0
        assert Expectation.objects.count() == 2

    def test_progress_stops_at_what_the_indexer_wrote(self):
        # Not the chain tip. A cursor moved to the tip skips every block the
        # indexer had not reached, and nothing revisits a skipped range.
        reader = FakeReader([], Window(chain_tip=1000, last_indexed=900, log_floor=0))
        report = discover_tee_instructions(
            reader, contract_address=CONTRACT, from_block=0
        )
        assert report.through_block == 900
        assert report.indexer_lag == 100

    def test_a_malformed_log_does_not_stop_the_scan(self):
        good = encode_log([(MACHINE_A, PROXY_A, "http://a:9/")])
        bad = encode_log([(MACHINE_B, PROXY_B, "http://b:9/")], block=11)
        bad = dataclasses.replace(bad, data="00ff")
        report = discover_tee_instructions(
            FakeReader([bad, good]), contract_address=CONTRACT, from_block=0
        )
        assert report.expectations_created == 2
        assert report.logs_read == 2

    def test_expectations_carry_a_backstop(self):
        rows = [encode_log([(MACHINE_A, PROXY_A, "http://a:9/")])]
        discover_tee_instructions(
            FakeReader(rows),
            contract_address=CONTRACT,
            from_block=0,
            ttl=timedelta(days=3),
        )
        e = Expectation.objects.first()
        assert timedelta(days=2) < (e.expires_at - e.first_seen_at) <= timedelta(days=3)
