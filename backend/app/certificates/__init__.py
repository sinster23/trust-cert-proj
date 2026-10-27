"""Certificate domain module (M5): schema, validation and canonicalization."""

from .canonicalization import canonicalize
from .exceptions import (
    CanonicalizationError,
    CertificateError,
    CertificateValidationError,
    UnsupportedSchemaVersionError,
)
from .models import SCHEMA_VERSION, Certificate, generate_certificate_id
from .schemas import CertificateData, CertificateIssueRequest, parse_issue_request

__all__ = [
    "SCHEMA_VERSION",
    "Certificate",
    "CertificateData",
    "CertificateIssueRequest",
    "CertificateError",
    "CertificateValidationError",
    "CanonicalizationError",
    "UnsupportedSchemaVersionError",
    "canonicalize",
    "generate_certificate_id",
    "parse_issue_request",
]