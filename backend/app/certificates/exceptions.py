"""Controlled errors raised by the certificate domain module (M5)."""


class CertificateError(Exception):
    """Base class for certificate-domain errors."""


class CertificateValidationError(CertificateError):
    """Certificate data failed a field or domain-level validation rule."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class CanonicalizationError(CertificateError):
    """Certificate data could not be converted into canonical bytes."""


class UnsupportedSchemaVersionError(CertificateError):
    """The certificate schema version is not recognised by this build."""

class StoredCertificateError(CertificateError):
    """A persisted certificate record is malformed or fails validation."""