"""Public M3 service interface for hashing, signing, and primitive verification."""

from __future__ import annotations

from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .exceptions import CryptoError, InvalidDataError, InvalidKeyError, SigningError
from .hashing import sha256
from .keys import ALGORITHM, KeyManager
from .signatures import decode_signature, encode_signature, sign_bytes, verify_bytes


@dataclass(frozen=True, slots=True)
class SignatureResult:
    """Signature metadata returned to the certificate/domain caller."""

    signature: str
    key_id: str
    algorithm: str = ALGORITHM


class CryptoService:
    """M3 operations over caller-supplied bytes; no certificate serialization."""

    def __init__(self, keys: KeyManager | None = None) -> None:
        self._keys = keys or KeyManager()

    def hash_data(self, data: bytes) -> str:
        return sha256(data)

    def sign(self, canonical_data: bytes) -> SignatureResult:
        """Sign deterministic bytes supplied by the certificate/domain module."""
        if not isinstance(canonical_data, bytes):
            raise InvalidDataError("Canonical data must be bytes")
        try:
            signature = sign_bytes(self._keys.get_private_key(), canonical_data)
        except CryptoError:
            raise
        except Exception as exc:
            # Do not attach provider details to the public exception message.
            raise SigningError("Signing operation failed") from exc
        return SignatureResult(
            signature=encode_signature(signature),
            key_id=self._keys.settings.key_id,
        )

    def verify_signature(
        self,
        canonical_data: bytes,
        signature: str,
        *,
        public_key: bytes | Ed25519PublicKey | None = None,
        key_id: str | None = None,
    ) -> bool:
        """Verify a signature; malformed or invalid signatures return False.

        ``public_key`` may be an Ed25519 key object or PEM-encoded public key.
        If omitted, the configured public key (or the private key's public half)
        is used. A supplied key id must match the configured id.
        """
        if not isinstance(canonical_data, bytes):
            raise InvalidDataError("Canonical data must be bytes")
        if key_id is not None and key_id != self._keys.settings.key_id:
            return False
        signature_bytes = decode_signature(signature)
        if signature_bytes is None:
            return False
        try:
            verifier = (
                self._keys.get_public_key()
                if public_key is None
                else self._resolve_public_key(public_key)
            )
        except (CryptoError, OSError):
            return False
        return verify_bytes(verifier, canonical_data, signature_bytes)

    def get_public_key_pem(self) -> bytes:
        """Expose only the public key, in PEM SubjectPublicKeyInfo form."""
        return self._keys.get_public_key_pem()

    @property
    def key_id(self) -> str:
        return self._keys.settings.key_id

    @staticmethod
    def _resolve_public_key(
        public_key: bytes | Ed25519PublicKey | None,
    ) -> Ed25519PublicKey:
        if public_key is None:
            raise InvalidKeyError("No public key supplied")
        if isinstance(public_key, Ed25519PublicKey):
            return public_key
        if not isinstance(public_key, bytes):
            raise InvalidKeyError("Public key must be Ed25519 or PEM bytes")
        try:
            loaded = serialization.load_pem_public_key(public_key)
        except (TypeError, ValueError) as exc:
            raise InvalidKeyError("Public key is invalid") from exc
        if not isinstance(loaded, Ed25519PublicKey):
            raise InvalidKeyError("Public key must use Ed25519")
        return loaded
