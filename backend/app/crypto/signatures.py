"""Ed25519 signing and verification primitives."""

from __future__ import annotations

import base64
import binascii

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .exceptions import InvalidDataError


def sign_bytes(private_key: Ed25519PrivateKey, data: bytes) -> bytes:
    if not isinstance(data, bytes):
        raise InvalidDataError("Data must be bytes")
    return private_key.sign(data)


def verify_bytes(public_key: Ed25519PublicKey, data: bytes, signature: bytes) -> bool:
    if not isinstance(data, bytes) or not isinstance(signature, bytes):
        return False
    try:
        public_key.verify(signature, data)
    except (InvalidSignature, ValueError):
        return False
    return True


def encode_signature(signature: bytes) -> str:
    """Encode signature bytes as unpadded URL-safe Base64."""
    return base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")


def decode_signature(signature: str) -> bytes | None:
    """Decode an unpadded URL-safe Base64 signature; malformed input returns None."""
    if not isinstance(signature, str) or not signature:
        return None
    try:
        encoded = signature.encode("ascii")
        return base64.b64decode(encoded + b"=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError):
        return None
