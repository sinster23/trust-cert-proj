"""Environment-based Ed25519 signing key loading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .exceptions import InvalidKeyError, SigningKeyNotFoundError

ALGORITHM = "Ed25519"


@dataclass(frozen=True, slots=True)
class CryptoSettings:
    private_key_path: str | None
    public_key_path: str | None
    key_id: str = "credence-ed25519-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.key_id, str) or not self.key_id.strip():
            raise InvalidKeyError("Signing key id must not be empty")

    @classmethod
    def from_env(cls) -> "CryptoSettings":
        private_path = os.getenv("SIGNING_PRIVATE_KEY_PATH", "").strip() or None
        public_path = os.getenv("SIGNING_PUBLIC_KEY_PATH", "").strip() or None
        key_id = os.getenv("SIGNING_KEY_ID", "credence-ed25519-v1").strip()
        if not key_id:
            raise InvalidKeyError("SIGNING_KEY_ID must not be empty")
        return cls(private_path, public_path, key_id)


class KeyManager:
    """Loads the configured Ed25519 key pair without exposing private bytes."""

    def __init__(self, settings: CryptoSettings | None = None) -> None:
        self.settings = settings or CryptoSettings.from_env()

    def get_private_key(self) -> Ed25519PrivateKey:
        path = self.settings.private_key_path
        if not path:
            raise SigningKeyNotFoundError("Signing private key is not configured")
        try:
            key_bytes = Path(path).read_bytes()
        except FileNotFoundError as exc:
            raise SigningKeyNotFoundError("Signing private key is unavailable") from exc
        except OSError as exc:
            raise SigningKeyNotFoundError("Signing private key is unavailable") from exc

        try:
            key = serialization.load_pem_private_key(key_bytes, password=None)
        except (TypeError, ValueError, UnsupportedAlgorithm) as exc:
            raise InvalidKeyError("Signing private key is invalid or encrypted") from exc
        if not isinstance(key, Ed25519PrivateKey):
            raise InvalidKeyError("Signing private key must use Ed25519")

        if self.settings.public_key_path:
            configured_public = self._load_public_key(self.settings.public_key_path)
            if self._raw_public_key(configured_public) != self._raw_public_key(key.public_key()):
                raise InvalidKeyError("Configured signing keys do not match")
        return key

    def get_public_key(self) -> Ed25519PublicKey:
        path = self.settings.public_key_path
        if path:
            public_key = self._load_public_key(path)
            if self.settings.private_key_path:
                private_key = self.get_private_key()
                if self._raw_public_key(public_key) != self._raw_public_key(private_key.public_key()):
                    raise InvalidKeyError("Configured signing keys do not match")
            return public_key
        return self.get_private_key().public_key()

    def get_public_key_pem(self) -> bytes:
        """Return the public key in SubjectPublicKeyInfo PEM encoding."""
        return self.get_public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    @staticmethod
    def _load_public_key(path: str) -> Ed25519PublicKey:
        try:
            key_bytes = Path(path).read_bytes()
        except OSError as exc:
            raise SigningKeyNotFoundError("Signing public key is unavailable") from exc
        try:
            key = serialization.load_pem_public_key(key_bytes)
        except (TypeError, ValueError, UnsupportedAlgorithm) as exc:
            raise InvalidKeyError("Signing public key is invalid") from exc
        if not isinstance(key, Ed25519PublicKey):
            raise InvalidKeyError("Signing public key must use Ed25519")
        return key

    @staticmethod
    def _raw_public_key(key: Ed25519PublicKey) -> bytes:
        return key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
