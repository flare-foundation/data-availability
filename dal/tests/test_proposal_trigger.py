"""Proposal expectations, discovered from the requests proposers committed.

This is what closes the gap the harness used to paper over by calling the
collector from its own publish step. The trigger is a proposer's own FDC2
attestation request — which the hub turns into a TeeInstructionsSent
instruction, the same event already indexed for machine results.

The property under test throughout: **provenance comes from the transaction's
sender**, never from a field in the request. The instruction carries a
claimBackAddress chosen by the caller, and these tests exist partly to prove it
is not what gets believed.
"""

import dataclasses

import pytest
from eth_abi.abi import encode as abi_encode
from eth_utils.address import to_checksum_address

from dal.chain.abi import (
    CSP_PROPOSAL_CHECK,
    TEE_INSTRUCTIONS_SENT,
    attestation_type,
    topic0,
)
from dal.chain.indexer import LogRow, Window
from dal.chain.triggers import OP_FDC2, OP_PROVE, discover_proposal_requests
from dal.models import Expectation, ExpectationState

CONTRACT = "1234567890abcdef1234567890abcdef12345678"
SENDER = "bcrt1qexampleaccount"
SOURCE = attestation_type("testBTC")
PACKAGE = b"\xab" * 32
SUBMITTER = to_checksum_address("0x" + "0" * 36 + "5e11")
CLAIM_BACK = to_checksum_address("0x" + "0" * 36 + "c1a1")
TX = "cd" * 32


def request_message(
    package=PACKAGE,
    sender=SENDER,
    generation=3,
    a_type=CSP_PROPOSAL_CHECK,
    source=SOURCE,
    body=None,
) -> bytes:
    # ICspProposalCheck.RequestBody: (senderAddress, sequencePosition, attempt,
    # eligibleGeneration, packageHash).
    if body is None:
        body = abi_encode(
            ["(string,uint64,uint32,uint64,bytes32)"],
            [(sender, 7, 0, generation, package)],
        )
    return abi_encode(
        ["((bytes32,bytes32,uint16,address),bytes)"],
        [((a_type, source, 0, "0x" + "00" * 20), body)],
    )


def instruction_log(
    message: bytes, op_type=OP_FDC2, op_command=OP_PROVE, block=10
) -> LogRow:
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
        [[], op_type, op_command, message, [], 1, CLAIM_BACK, 0],
    )
    return LogRow(
        address=CONTRACT,
        topic0=topic0(TEE_INSTRUCTIONS_SENT),
        topic1=f"{0:064x}",
        topic2="aa" * 32,
        topic3=f"{3:064x}",
        data=data.hex(),
        transaction_hash=TX,
        log_index=0,
        block_number=block,
        timestamp=block * 10,
    )


class FakeReader:
    def __init__(self, rows):
        self.rows = rows

    def logs(self, **kwargs):
        return self.rows, Window(chain_tip=100, last_indexed=100, log_floor=0)


def discover(rows, submitter=SUBMITTER):
    return discover_proposal_requests(
        FakeReader(rows),
        contract_address=CONTRACT,
        from_block=0,
        submitter_of=lambda _tx: submitter,
    )


@pytest.mark.django_db
class TestDiscovery:
    def test_a_committed_request_becomes_an_expectation(self):
        report = discover([instruction_log(request_message())])
        assert report.expectations_created == 1
        e = Expectation.objects.get()
        assert e.key == PACKAGE.hex()
        assert e.state == ExpectationState.OPEN

    def test_provenance_is_the_transaction_sender(self):
        # NOT claimBackAddress, which the caller chooses and could set to anyone.
        discover([instruction_log(request_message())])
        params = Expectation.objects.get().params
        assert params["proposer"] == SUBMITTER
        assert params["proposer"] != CLAIM_BACK

    def test_the_generation_the_proposal_binds_to_is_kept(self):
        # Not for admission, which is asked live. An expectation is never
        # re-derived, so it is the only record of the request, and the
        # generation is what says when the proposal stops being finalizable.
        discover([instruction_log(request_message(generation=9))])
        assert Expectation.objects.get().params["generation"] == 9

    def test_the_account_is_the_source_and_the_sender_address(self):
        # (header.sourceId, senderAddress) is the WalletAccount the diamond's
        # reads take, so it is recorded exactly as isAllowedProposer is asked.
        discover([instruction_log(request_message())])
        e = Expectation.objects.get()
        assert e.params["sourceId"] == "0x" + SOURCE.hex()
        assert e.params["senderAddress"] == SENDER
        assert e.trigger_ref == f"0x{SOURCE.hex()}/{SENDER}#7.0"

    def test_a_p2wsh_account_fits_the_trigger_reference(self):
        # A real P2WSH account address is 62-64 characters and the source is a
        # full bytes32, so the reference passes 128 characters. It overflowed a
        # varchar(128) on Postgres, and the exception stopped the collector.
        sender = "bcrt1qvxpc2smteghvw5xckh8xs7aen33qwmzg6wq9ugs7vnxnv73ma5wq0nsa8r"
        report = discover([instruction_log(request_message(sender=sender))])
        assert report.expectations_created == 1
        e = Expectation.objects.get()
        assert e.trigger_ref == f"0x{SOURCE.hex()}/{sender}#7.0"
        assert len(e.trigger_ref) > 128

    def test_a_reissued_request_is_a_retry_not_a_rival(self):
        # An identical request may be submitted again for another processing
        # round. The FIRST commitment keeps provenance, so the second must not
        # create a second expectation or overwrite the proposer.
        log = instruction_log(request_message())
        discover([log])
        second = discover_proposal_requests(
            FakeReader([log]),
            contract_address=CONTRACT,
            from_block=0,
            submitter_of=lambda _tx: to_checksum_address("0x" + "0" * 36 + "beef"),
        )
        assert second.expectations_created == 0
        assert Expectation.objects.count() == 1
        assert Expectation.objects.get().params["proposer"] == SUBMITTER

    def test_a_request_with_no_readable_sender_is_skipped(self):
        # Without a sender there is no provenance, and guessing one would be
        # worse than having none.
        report = discover([instruction_log(request_message())], submitter=None)
        assert report.expectations_created == 0
        assert not Expectation.objects.exists()


@pytest.mark.django_db
class TestWhatIsIgnored:
    def test_another_attestation_type_is_not_a_proposal(self):
        message = request_message(a_type=attestation_type("PMWPaymentStatus"))
        assert discover([instruction_log(message)]).expectations_created == 0

    def test_an_instruction_that_is_not_a_prove_is_ignored(self):
        log = instruction_log(request_message(), op_command=b"Sign".ljust(32, b"\x00"))
        assert discover([log]).expectations_created == 0

    def test_a_non_fdc2_instruction_is_ignored(self):
        log = instruction_log(request_message(), op_type=b"F_BTC".ljust(32, b"\x00"))
        assert discover([log]).expectations_created == 0

    def test_a_body_in_another_layout_is_not_a_proposal(self):
        # A body whose head is not a string offset (here a leading address, as
        # a wallet-registry-first layout would carry) fails to decode rather
        # than yielding a shifted account.
        body = abi_encode(
            ["address", "bytes32", "uint32", "uint64", "uint32", "uint64", "bytes32"],
            [CLAIM_BACK, b"\x11" * 32, 0, 7, 0, 3, PACKAGE],
        )
        message = request_message(body=body)
        assert discover([instruction_log(message)]).expectations_created == 0

    def test_an_undecodable_message_does_not_stop_the_scan(self):
        bad = dataclasses.replace(instruction_log(request_message()), data="00ff")
        good = instruction_log(request_message(), block=11)
        assert discover([bad, good]).expectations_created == 1


def test_the_op_identifiers_are_pinned():
    """The literal bytes, because every other test here is self-consistent.

    The tests above build their fixture from OP_FDC2 and OP_PROVE, so they pass
    whatever those happen to be — and they did pass while both were wrong, which
    is how a filter that matches nothing reached a run. A wrong identifier reads
    exactly like a chain on which no proposal was ever requested.

    The values come from go-flare-common's op package: `FDC2 Type = "F_FDC2"`
    and `Prove Command = "PROVE"`, UTF-8 padded to 32 bytes by op.Type.Hash().
    Pinning the hex catches an edit here; only a run against a real chain can
    catch the two drifting apart.
    """
    assert (
        OP_FDC2.hex()
        == "465f4644433200000000000000000000000000000000000000000000000000"[:62] + "00"
    )
    assert OP_PROVE.hex() == "50524f5645" + "00" * 27
    assert CSP_PROPOSAL_CHECK.hex() == b"CspProposalCheck".hex() + "00" * 16


# A CspProposalCheck request exactly as the owners' Fdc2Hub put it into a
# TeeInstructionsSent message on a csp-e2e chain (flare-smart-contracts-v2
# csp-utxo-payments e4d6d26c, btc-proposer as the requester): the body is
# abi.encode of the struct, a tuple behind an offset. Every other test here
# encodes the body itself, so this is the one that would notice the two
# encoders disagreeing.
GOLDEN_MESSAGE = bytes.fromhex(
    "0000000000000000000000000000000000000000000000000000000000000020"
    "43737050726f706f73616c436865636b00000000000000000000000000000000"
    "4254430000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000a0"
    "0000000000000000000000000000000000000000000000000000000000000120"
    "0000000000000000000000000000000000000000000000000000000000000020"
    "00000000000000000000000000000000000000000000000000000000000000a0"
    "0000000000000000000000000000000000000000000000000000000000000001"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000002"
    "7a2a8ce304619fee50425948955fac717e1ac169f6ccff1e919dbc87dc3a0ab7"
    "0000000000000000000000000000000000000000000000000000000000000040"
    "6263727431717664326b36646e6b376e68763879737774676373746370687635"
    "71763972386d6638726130647334767a686d6838666d73366b7333336574337a"
)


def test_the_hubs_own_bytes_decode():
    from dal.chain.triggers import _proposal_request

    parsed = _proposal_request(GOLDEN_MESSAGE)
    assert parsed is not None
    assert parsed["source_id"] == b"BTC".ljust(32, b"\x00")
    assert parsed["sender_address"].startswith("bcrt1q")
    assert parsed["sequence_position"] == 1
    assert parsed["attempt"] == 0
