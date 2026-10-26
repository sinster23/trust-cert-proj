from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.crypto import CryptoService
from app.crypto.exceptions import (
    InvalidDataError,
    InvalidKeyError,
    SigningKeyNotFoundError,
)
from app.crypto.hashing import sha256
from app.crypto.keys import CryptoSettings, KeyManager


def write_key_pair(tmp_path, private_key: Ed25519PrivateKey | None = None):
    private_key = private_key or Ed25519PrivateKey.generate()
    private_path = tmp_path / "signing-private.pem"
    public_path = tmp_path / "signing-public.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return private_path, public_path


def service_for(private_path, public_path=None, key_id="test-key-v1"):
    settings = CryptoSettings(
        private_key_path=str(private_path) if private_path else None,
        public_key_path=str(public_path) if public_path else None,
        key_id=key_id,
    )
    return CryptoService(KeyManager(settings))


def test_sha256_is_deterministic_and_changes_with_input():
    assert sha256(b"certificate") == sha256(b"certificate")
    assert sha256(b"certificate") != sha256(b"certificate!")


def test_hash_rejects_non_bytes():
    with pytest.raises(InvalidDataError):
        sha256("certificate")  # type: ignore[arg-type]


def test_sign_and_verify_canonical_bytes(tmp_path):
    private_path, public_path = write_key_pair(tmp_path)
    crypto = service_for(private_path, public_path)
    data = b"stable canonical certificate bytes"

    result = crypto.sign(data)

    assert result.algorithm == "Ed25519"
    assert result.key_id == "test-key-v1"
    assert crypto.verify_signature(data, result.signature, key_id=result.key_id)
    assert not crypto.verify_signature(data + b" changed", result.signature)
    assert not crypto.verify_signature(data, result.signature, key_id="old-key")


def test_verify_accepts_explicit_public_key(tmp_path):
    private_path, public_path = write_key_pair(tmp_path)
    crypto = service_for(private_path)
    result = crypto.sign(b"payload")

    assert crypto.verify_signature(
        b"payload", result.signature, public_key=public_path.read_bytes()
    )


def test_malformed_signature_is_rejected(tmp_path):
    private_path, public_path = write_key_pair(tmp_path)
    crypto = service_for(private_path, public_path)
    assert not crypto.verify_signature(b"payload", "not-base64!")


def test_missing_private_key_fails_safely():
    crypto = service_for(None)
    with pytest.raises(SigningKeyNotFoundError, match="not configured"):
        crypto.sign(b"payload")


def test_invalid_private_key_is_rejected(tmp_path):
    private_path = tmp_path / "invalid.pem"
    private_path.write_bytes(b"not a private key")
    crypto = service_for(private_path)

    with pytest.raises(InvalidKeyError):
        crypto.sign(b"payload")


def test_mismatched_public_private_pair_is_rejected(tmp_path):
    private_path, _ = write_key_pair(tmp_path)
    other_private = Ed25519PrivateKey.generate()
    other_public_path = tmp_path / "other-public.pem"
    other_public_path.write_bytes(
        other_private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    crypto = service_for(private_path, other_public_path)

    with pytest.raises(InvalidKeyError, match="do not match"):
        crypto.sign(b"payload")


def test_public_key_method_never_returns_private_key(tmp_path):
    private_path, public_path = write_key_pair(tmp_path)
    crypto = service_for(private_path, public_path)

    public_pem = crypto.get_public_key_pem()

    assert b"PUBLIC KEY" in public_pem
    assert b"PRIVATE KEY" not in public_pem
