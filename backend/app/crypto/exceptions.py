"""Controlled errors raised by the cryptography module."""


class CryptoError(Exception):
    """Base class for safe, caller-facing cryptographic errors."""


class InvalidDataError(CryptoError):
    """Input data is not in the byte format required by M3."""


class SigningKeyNotFoundError(CryptoError):
    """The configured signing private key is missing or unavailable."""


class InvalidKeyError(CryptoError):
    """A configured key is malformed, unsupported, or does not match its pair."""


class SigningError(CryptoError):
    """A signing operation could not be completed."""
