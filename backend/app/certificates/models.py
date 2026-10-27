"""Certificate domain model, field rules and ID generation (M5, Stage 1).

This is a Credence prototype certificate format, not a verified representation
of any official institutional (e.g. KIIT) certificate.

Schema v1 assumptions (no institutional sample was supplied):
* All nine fields are required; there are no optional or null fields.
* Text fields are normalized to Unicode NFC, trimmed, with internal
  whitespace runs collapsed to a single space.
* Dates are ISO 8601 ``YYYY-MM-DD`` strings (strict, zero-padded).
* ``issue_date`` must not be earlier than ``graduation_date``.
* ``certificate_id`` is ``CERT-`` + 32 lowercase hex chars (UUID4), generated
  by the backend only. It identifies a certificate; it is NOT proof of
  authenticity.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from .exceptions import CertificateValidationError, UnsupportedSchemaVersionError

SCHEMA_VERSION = "1.0"
SUPPORTED_SCHEMA_VERSIONS = frozenset({SCHEMA_VERSION})

CERTIFICATE_ID_PREFIX = "CERT-"
_CERTIFICATE_ID_PATTERN = re.compile(r"^CERT-[0-9a-f]{32}$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_WHITESPACE = re.compile(r"\s+")

# Fields supplied by the issuer (client input). IDs and issue date are not.
INPUT_FIELDS: tuple[str, ...] = (
    "student_id",
    "student_name",
    "institution",
    "degree",
    "field_of_study",
    "graduation_date",
)
# Every field that appears in the signed representation.
CERTIFICATE_FIELDS: tuple[str, ...] = (
    "certificate_id",
    *INPUT_FIELDS,
    "issue_date",
    "schema_version",
)

MAX_TEXT_LENGTH = 200
MAX_STUDENT_ID_LENGTH = 64
_STUDENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/\-]*$")


def generate_certificate_id() -> str:
    """Backend-controlled, DB-independent unique ID. Never accept from clients."""
    return f"{CERTIFICATE_ID_PREFIX}{uuid4().hex}"


def normalize_text(value: Any, field: str) -> str:
    """NFC-normalize, trim and collapse whitespace; reject empty/non-strings."""
    if not isinstance(value, str):
        raise CertificateValidationError(f"{field} must be a string", field=field)
    normalized = _WHITESPACE.sub(" ", unicodedata.normalize("NFC", value)).strip()
    if not normalized:
        raise CertificateValidationError(f"{field} must not be empty", field=field)
    if len(normalized) > MAX_TEXT_LENGTH:
        raise CertificateValidationError(
            f"{field} must be at most {MAX_TEXT_LENGTH} characters", field=field
        )
    if any(unicodedata.category(ch).startswith("C") for ch in normalized):
        raise CertificateValidationError(
            f"{field} contains control characters", field=field
        )
    return normalized


def normalize_student_id(value: Any) -> str:
    student_id = normalize_text(value, "student_id")
    if len(student_id) > MAX_STUDENT_ID_LENGTH or not _STUDENT_ID_PATTERN.fullmatch(
        student_id
    ):
        raise CertificateValidationError(
            "student_id may contain only letters, digits, '.', '_', '/' and '-'",
            field="student_id",
        )
    return student_id


def parse_iso_date(value: Any, field: str) -> date:
    """Strict YYYY-MM-DD; rejects other formats, whitespace and invalid dates."""
    if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value):
        raise CertificateValidationError(
            f"{field} must be an ISO 8601 date in YYYY-MM-DD format", field=field
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CertificateValidationError(
            f"{field} is not a valid calendar date", field=field
        ) from exc


def validate_certificate_id(value: Any) -> str:
    if not isinstance(value, str) or not _CERTIFICATE_ID_PATTERN.fullmatch(value):
        raise CertificateValidationError(
            "certificate_id has an invalid format", field="certificate_id"
        )
    return value


def validate_schema_version(value: Any) -> str:
    if not isinstance(value, str) or value not in SUPPORTED_SCHEMA_VERSIONS:
        raise UnsupportedSchemaVersionError("Unsupported certificate schema version")
    return value


@dataclass(frozen=True, slots=True)
class Certificate:
    """Validated, immutable academic certificate (schema v1).

    Contains certificate data only: no signature metadata and no lifecycle
    status. Those are kept separate (see the M5 security requirements).
    """

    certificate_id: str
    student_id: str
    student_name: str
    institution: str
    degree: str
    field_of_study: str
    graduation_date: str
    issue_date: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        validate_schema_version(self.schema_version)
        set_ = object.__setattr__
        set_(self, "certificate_id", validate_certificate_id(self.certificate_id))
        set_(self, "student_id", normalize_student_id(self.student_id))
        for name in ("student_name", "institution", "degree", "field_of_study"):
            set_(self, name, normalize_text(getattr(self, name), name))
        graduation = parse_iso_date(self.graduation_date, "graduation_date")
        issued = parse_iso_date(self.issue_date, "issue_date")
        if issued < graduation:
            raise CertificateValidationError(
                "issue_date must not be earlier than graduation_date",
                field="issue_date",
            )

    @classmethod
    def issue(
        cls,
        *,
        student_id: str,
        student_name: str,
        institution: str,
        degree: str,
        field_of_study: str,
        graduation_date: str,
        issue_date: str | None = None,
    ) -> "Certificate":
        """Create a new certificate with a backend-generated ID.

        ``issue_date`` defaults to the current UTC date, so the value does not
        depend on the deployment's timezone. Callers may pass it explicitly,
        e.g. for tests.
        """
        return cls(
            certificate_id=generate_certificate_id(),
            student_id=student_id,
            student_name=student_name,
            institution=institution,
            degree=degree,
            field_of_study=field_of_study,
            graduation_date=graduation_date,
            issue_date=(
                issue_date
                if issue_date is not None
                else datetime.now(timezone.utc).date().isoformat()
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in CERTIFICATE_FIELDS}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Certificate":
        """Rebuild from stored/submitted data. Unknown or missing fields fail."""
        if not isinstance(data, dict):
            raise CertificateValidationError("certificate data must be an object")
        unknown = set(data) - set(CERTIFICATE_FIELDS)
        if unknown:
            raise CertificateValidationError(
                f"unknown certificate fields: {', '.join(sorted(map(str, unknown)))}"
            )
        missing = [name for name in CERTIFICATE_FIELDS if name not in data]
        if missing:
            raise CertificateValidationError(
                f"missing certificate fields: {', '.join(missing)}",
                field=missing[0],
            )
        return cls(**{name: data[name] for name in CERTIFICATE_FIELDS})