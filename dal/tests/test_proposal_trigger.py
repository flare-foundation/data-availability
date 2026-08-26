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
    PMW_UTXO_PROPOSAL_CHECK,
    TEE_INSTRUCTIONS_SENT,
    attestation_type,
    topic0,
)
from dal.chain.indexer import LogRow, Window
from dal.chain.triggers import OP_FDC2, OP_PROVE, discover_proposal_requests
from dal.models import Expectation, ExpectationState

CONTRACT = "1234567890abcdef1234567890abcdef12345678"
WALLET = b"\x11" * 32
PACKAGE = b"\xab" * 32
SUBMITTER = to_checksum_address("0x" + "0" * 36 + "5e11")
CLAIM_BACK = to_checksum_address("0x" + "0" * 36 + "c1a1")
TX = "cd" * 32


def request_message(
    package=PACKAGE, wallet=WALLET, generation=3, a_type=PMW_UTXO_PROPOSAL_CHECK
) -> bytes:
    body = abi_encode(
        ["bytes32", "uint32", "uint64", "uint32", "uint64", "bytes32"],
        [wallet, 0, 7, 0, generation, package],
    )
    return abi_encode(
        ["((bytes32,bytes32,uint16,address),bytes)"],
        [((a_type, attestation_type("BTC"), 0, "0x" + "00" * 20), body)],
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
        # Needed later to ask whether the proposer was admitted for THAT
        # contest, rather than at whatever moment the fetch happens.
        discover([instruction_log(request_message(generation=9))])
        assert Expectation.objects.get().params["generation"] == 9

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
    assert PMW_UTXO_PROPOSAL_CHECK.hex() == b"PMWUtxoProposalCheck".hex() + "00" * 12
