"""The signing scheme every TEE-produced artifact is authorised under.

One construction serves all of them, and the two properties that matter are
both inside the signed bytes: a 32-byte ``prefix`` domain-separates the artifact
class, so a signature harvested from one class cannot be replayed into another,
and ``chainId`` binds the signature to one network, so a Coston signature cannot
be replayed onto Flare.

    dataHash  = <artifact-specific, see action_result_hash()>
    signHash  = keccak( abi.encode( (prefix, chainId, dataHash) ) )
    signature = secp256k1( EIP-191 text hash of signHash )

Cross-checked against vectors emitted by the Go implementation the TEE stack
actually signs with -- see dal/tests/vectors.json and how it is generated.
"""

from typing import Final

from eth_abi.abi import encode as abi_encode
from eth_keys.datatypes import Signature
from eth_keys.exceptions import BadSignature
from eth_utils.crypto import keccak

__all__ = [
    "CSP_PROPOSAL",
    "PROXY_ACTION_RESULT",
    "TEE_ACTION_RESULT",
    "TEE_VOTE_HASH",
    "SignatureError",
    "action_result_hash",
    "payload_hash",
    "recover",
    "verify",
]

# secp256k1 group order; a signature with s above half of it is malleable.
_SECP256K1_N: Final = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_HALF_N: Final = _SECP256K1_N // 2

_EIP191_PREFIX: Final = b"\x19Ethereum Signed Message:\n32"


def _prefix(name: str) -> bytes:
    """Right-pad a prefix name to 32 bytes, as ``mustStringBytes32`` does."""
    raw = name.encode("ascii")
    if len(raw) > 32:
        raise ValueError(f"prefix {name!r} is longer than 32 bytes")
    return raw.ljust(32, b"\x00")


TEE_ACTION_RESULT: Final = _prefix("TEE_ACTION_RESULT")
PROXY_ACTION_RESULT: Final = _prefix("PROXY_ACTION_RESULT")
TEE_VOTE_HASH: Final = _prefix("TEE_VOTE_HASH")
CSP_PROPOSAL: Final = _prefix("CSP_PROPOSAL")


class SignatureError(Exception):
    """A signature is malformed, non-canonical, or recovers to the wrong signer.

    Deliberately one exception for all three: a caller must treat every one of
    them as a refusal, and distinguishing them in control flow invites treating
    the malformed case as retryable when it is not.
    """


def payload_hash(prefix: bytes, chain_id: int, data_hash: bytes) -> bytes:
    """Hash the Payload struct the TEE contracts and clients agree on.

    ``struct Payload { bytes32 prefix; uint256 chainId; bytes32 dataHash; }``
    ABI-encoded as a single tuple, then keccak256.
    """
    if len(prefix) != 32:
        raise ValueError(f"prefix must be 32 bytes, got {len(prefix)}")
    if len(data_hash) != 32:
        raise ValueError(f"dataHash must be 32 bytes, got {len(data_hash)}")
    if not 0 <= chain_id < 2**256:
        raise ValueError(f"chainId {chain_id} is out of range")

    encoded = abi_encode(["(bytes32,uint256,bytes32)"], [(prefix, chain_id, data_hash)])
    return keccak(encoded)


def action_result_hash(
    data: bytes, action_id: bytes, submission_tag: str, status: int
) -> bytes:
    """``keccak(keccak(data) || id || keccak(submissionTag) || status)``.

    The status is one byte, so a result that succeeded and one that failed hash
    differently even when they carry the same payload.
    """
    if len(action_id) != 32:
        raise ValueError(f"action id must be 32 bytes, got {len(action_id)}")
    if not 0 <= status <= 0xFF:
        raise ValueError(f"status {status} does not fit in a byte")

    packed = (
        keccak(data)
        + action_id
        + keccak(submission_tag.encode("utf-8"))
        + bytes([status])
    )
    return keccak(packed)


def _check_canonical(signature: bytes) -> tuple[int, int, int]:
    """Split [R || S || V] and reject anything malleable or malformed.

    Rejecting high-S is what keeps ``(artifact, signature)`` a unique pair: with
    it allowed, every signature has a second equally valid form, and a store
    keyed on content would admit the same artifact twice.
    """
    if len(signature) != 65:
        raise SignatureError(f"signature must be 65 bytes, got {len(signature)}")

    r = int.from_bytes(signature[0:32], "big")
    s = int.from_bytes(signature[32:64], "big")
    v = signature[64]

    if v in (27, 28):
        v -= 27
    if v not in (0, 1):
        raise SignatureError(f"signature has recovery id {signature[64]}")
    if not 1 <= r < _SECP256K1_N:
        raise SignatureError("signature r is out of range")
    if not 1 <= s <= _HALF_N:
        raise SignatureError("signature s is not canonical (high-S)")

    return r, s, v


def recover(sign_hash: bytes, signature: bytes) -> str:
    """Recover the EIP-191 signer of ``sign_hash``, as a checksummed address."""
    if len(sign_hash) != 32:
        raise SignatureError(f"sign hash must be 32 bytes, got {len(sign_hash)}")

    r, s, v = _check_canonical(signature)
    message_hash = keccak(_EIP191_PREFIX + sign_hash)

    try:
        sig = Signature(vrs=(v, r, s))
        public_key = sig.recover_public_key_from_msg_hash(message_hash)
    except (BadSignature, ValueError) as exc:
        raise SignatureError(f"signature does not recover: {exc}") from exc

    return public_key.to_checksum_address()


def verify(sign_hash: bytes, signature: bytes, expected_signer: str) -> None:
    """Raise unless ``signature`` over ``sign_hash`` was made by the expected signer."""
    actual = recover(sign_hash, signature)
    if actual.lower() != expected_signer.lower():
        raise SignatureError(f"signature recovers to {actual}, not {expected_signer}")
