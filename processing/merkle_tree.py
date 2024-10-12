from eth_abi.abi import encode
from web3 import Web3

# from eth_utils import keccak
from processing.utils import prefix_0x, un_prefix_0x


def hash_function(value: str | bytes) -> str:
    return prefix_0x(Web3.solidity_keccak(["bytes"], [value]).hex())


# Function to convert to hexadecimal and pad to bytes
def to_hex(value: str, pad_to_bytes: int) -> str:
    value = un_prefix_0x(value)
    padded_hex = value.rjust(pad_to_bytes * 2, "0")
    return "0x" + padded_hex


# Single value hash function
def single_hash(value: str) -> str:
    return hash_function(value)


# Function for constructing the commit hash
def commit_hash(merkle_root: str, random_number: str, address: str) -> str:
    encoded = encode(["bytes32", "bytes32", "address"], [merkle_root, random_number, address])
    return hash_function(encoded)


# Function to compute a sorted hash of two 32-byte strings
def sorted_hash_pair(x: str, y: str) -> str:
    x = un_prefix_0x(x)
    y = un_prefix_0x(y)
    xx = bytes.fromhex(x)
    yy = bytes.fromhex(y)
    if x <= y:
        encoded = encode(["bytes32", "bytes32"], [xx, yy])
    else:
        encoded = encode(["bytes32", "bytes32"], [yy, xx])
    return hash_function(encoded)


class MerkleTree:
    def __init__(self, values: list[str], initial_hash: bool = False):
        self._tree: list[str] = []
        self.initial_hash = initial_hash
        self.build(values)

    @property
    def root(self) -> str | None:
        return self._tree[0] if self._tree else None

    @property
    def root_bigint(self) -> int:
        return int(self.root, 16) if self.root else 0

    @property
    def tree(self) -> list[str]:
        return self._tree[:]

    @property
    def hash_count(self) -> int:
        return (len(self._tree) + 1) // 2

    @property
    def sorted_hashes(self) -> list[str]:
        return self._tree[self.hash_count - 1 :]

    def parent(self, i: int) -> int:
        return (i - 1) // 2

    def build(self, values: list[str]):
        sorted_values = sorted(to_hex(v, 32) for v in values)
        hashes = []
        for value in sorted_values:
            # To remove duplicates
            if not hashes or value != hashes[-1]:
                hashes.append(value)

        if self.initial_hash:
            hashes = [single_hash(h) for h in hashes]

        n = len(hashes)

        tree = [""] * (n - 1) + hashes

        i = n - 2
        while i >= 0:
            tree[i] = sorted_hash_pair(tree[2 * i + 1], tree[2 * i + 2])
            i -= 1
        self._tree = tree

    def get_hash(self, i: int) -> str | None:
        if self.hash_count == 0 or not (0 <= i < self.hash_count):
            return None
        pos = len(self._tree) - self.hash_count + i
        return self._tree[pos]

    def binary_search(self, target: str) -> int | None:
        low, high = 0, self.hash_count
        while high - low > 1:
            mid = (low + high) // 2
            if target < self.sorted_hashes[mid]:
                high = mid
            else:
                low = mid
        return low if self.sorted_hashes[low] == target else None

    def get_proof(self, target: str) -> list[str] | None:
        target = to_hex(target, 32)
        index = self.binary_search(target)
        if index is None:
            return None

        proof = []
        pos = len(self._tree) - self.hash_count + index
        while pos > 0:
            sibling = pos + 2 * (pos % 2) - 1
            proof.append(self._tree[sibling])
            pos = self.parent(pos)
        return proof


def verify_with_merkle_proof(leaf: str, proof: list[str], root: str) -> bool:
    if not leaf or not proof or not root:
        return False
    current_hash = leaf
    for sibling_hash in proof:
        current_hash = sorted_hash_pair(current_hash, sibling_hash)
    return current_hash == root
