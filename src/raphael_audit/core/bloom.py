"""Simple bloom filter for checksum deduplication."""

from __future__ import annotations

import hashlib
import math
from typing import Iterable


class BloomFilter:
    """Probabilistic set with configurable false-positive rate."""

    def __init__(self, expected_items: int = 100_000, false_positive_rate: float = 0.01) -> None:
        m = -expected_items * math.log(false_positive_rate) / (math.log(2) ** 2)
        self.size = max(64, int(m))
        self.hash_count = max(1, int((self.size / expected_items) * math.log(2)))
        self._bits = bytearray(math.ceil(self.size / 8))

    def _indexes(self, key: str) -> Iterable[int]:
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        base = int.from_bytes(digest[:8], "big")
        step = int.from_bytes(digest[8:16], "big") | 1
        for i in range(self.hash_count):
            yield (base + i * step) % self.size

    def add(self, key: str) -> None:
        for index in self._indexes(key):
            byte_index, bit_index = divmod(index, 8)
            self._bits[byte_index] |= 1 << bit_index

    def __contains__(self, key: str) -> bool:
        for index in self._indexes(key):
            byte_index, bit_index = divmod(index, 8)
            if not (self._bits[byte_index] & (1 << bit_index)):
                return False
        return True
