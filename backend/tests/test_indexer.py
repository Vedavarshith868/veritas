"""Unit tests for indexer key math."""
from __future__ import annotations

from app.indexer import index_key


def test_index_key_lowercases_hash() -> None:
    upper = "A" * 64
    lower = "a" * 64
    assert index_key(upper) == index_key(lower)


def test_index_key_shape() -> None:
    key = index_key("abc" * 22)
    assert key.startswith("veritas/index/sha256/")
    assert key.endswith(".json")


def test_index_key_is_deterministic() -> None:
    h = "deadbeef" * 8
    assert index_key(h) == index_key(h)
