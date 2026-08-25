"""Key derivation: uniqueness, domain separation, and the content-key passthrough."""

import pytest
from eth_utils.crypto import keccak

from dal.keys import (
    action_result_key,
    instruction_index_key,
    proposal_key,
    round_payload_key,
)

INSTRUCTION = bytes.fromhex(
    "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
)
MACHINE_A = "0x2c7536E3605D9C16a7a3D7b1898e529396a65c23"
MACHINE_B = "0x0000000000000000000000000000000000000001"


def test_every_key_is_32_bytes():
    keys = [
        round_payload_key(100, 7),
        round_payload_key(200, 7),
        action_result_key(INSTRUCTION, MACHINE_A, "threshold"),
        instruction_index_key(INSTRUCTION),
        proposal_key(keccak(b"envelope")),
    ]
    assert all(len(k) == 32 for k in keys)


def test_the_two_protocols_do_not_share_a_round_key():
    # Same round number, different protocol: FTSO's payload and FDC's payload
    # are different artifacts and must not overwrite each other.
    assert round_payload_key(100, 7) != round_payload_key(200, 7)


def test_rounds_are_distinct():
    assert round_payload_key(200, 7) != round_payload_key(200, 8)


@pytest.mark.parametrize("tag", ["threshold", "end"], ids=str)
def test_machines_do_not_share_a_key(tag):
    assert action_result_key(INSTRUCTION, MACHINE_A, tag) != action_result_key(
        INSTRUCTION, MACHINE_B, tag
    )


def test_tags_do_not_share_a_key():
    assert action_result_key(INSTRUCTION, MACHINE_A, "threshold") != (
        action_result_key(INSTRUCTION, MACHINE_A, "end")
    )


def test_the_address_case_does_not_change_the_key():
    # Addresses arrive checksummed from chain reads and lowercase from some
    # JSON payloads; one artifact must not acquire two keys because of it.
    assert action_result_key(INSTRUCTION, MACHINE_A, "end") == action_result_key(
        INSTRUCTION, MACHINE_A.lower(), "end"
    )


def test_the_secondary_index_is_not_a_primary_key():
    # An instruction's index key must not collide with any artifact key under
    # it, or a set lookup would find the set itself.
    index = instruction_index_key(INSTRUCTION)
    assert index != action_result_key(INSTRUCTION, MACHINE_A, "threshold")
    assert index != action_result_key(INSTRUCTION, MACHINE_A, "end")


def test_the_proposal_key_is_the_proposal_hash_unchanged():
    # Every existing CSP consumer binds fetched bytes to proposalHash. Hashing
    # it again would give the store a name nothing else in the system uses.
    h = keccak(b"envelope")
    assert proposal_key(h) == h


@pytest.mark.parametrize("bad", [b"", b"\x01" * 31, b"\x01" * 33], ids=len)
def test_short_identifiers_are_refused(bad):
    with pytest.raises(ValueError):
        action_result_key(bad, MACHINE_A, "end")
    with pytest.raises(ValueError):
        proposal_key(bad)


def test_a_non_address_is_refused():
    with pytest.raises(ValueError):
        action_result_key(INSTRUCTION, "0xdeadbeef", "end")
