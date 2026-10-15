"""Hashing helpers for deterministic byte sequences."""

from __future__ import annotations

import hashlib

from .exceptions import InvalidDataError


def sha256(data: bytes) -> str:
    """Return the lowercase hexadecimal SHA-256 digest of ``data``."""
    if not isinstance(data, bytes):
        raise InvalidDataError("Data must be bytes")
    return hashlib.sha256(data).hexdigest()
