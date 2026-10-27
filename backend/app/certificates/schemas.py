"""Input/output schemas for the certificate domain (M5).

``CertificateIssueRequest`` is what an issuer may submit. It deliberately has
no ``certificate_id``, ``issue_date`` or ``schema_version``: the backend sets
them, and ``extra="forbid"`` rejects any attempt to supply them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import TYPE_CHECKING

from .exceptions import CertificateValidationError
from .models import (
    MAX_STUDENT_ID_LENGTH,
    MAX_TEXT_LENGTH,
    Certificate,
)
if TYPE_CHECKING:
    from .service import SignedCertificate


class CertificateIssueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    student_id: str = Field(min_length=1, max_length=MAX_STUDENT_ID_LENGTH)
    student_name: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH * 2)
    institution: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH * 2)
    degree: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH * 2)
    field_of_study: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH * 2)
    graduation_date: str = Field(description="ISO 8601 date, YYYY-MM-DD")

    def to_certificate(self, issue_date: str | None = None) -> Certificate:
        """Apply domain validation and attach a backend-generated ID."""
        return Certificate.issue(issue_date=issue_date, **self.model_dump())


class CertificateData(BaseModel):
    """Read-only representation of a certificate (no signature or status)."""

    model_config = ConfigDict(extra="forbid")

    certificate_id: str
    student_id: str
    student_name: str
    institution: str
    degree: str
    field_of_study: str
    graduation_date: str
    issue_date: str
    schema_version: str

    @classmethod
    def from_certificate(cls, certificate: Certificate) -> "CertificateData":
        return cls(**certificate.to_dict())


class SignatureMetadata(BaseModel):
    """Signature details, kept separate from the certificate fields."""

    model_config = ConfigDict(extra="forbid")

    signature: str
    key_id: str
    algorithm: str


class IssuedCertificateResponse(BaseModel):
    certificate: CertificateData
    signature_metadata: SignatureMetadata

    @classmethod
    def from_signed(cls, signed: "SignedCertificate") -> "IssuedCertificateResponse":
        return cls(
            certificate=CertificateData.from_certificate(signed.certificate),
            signature_metadata=SignatureMetadata(
                signature=signed.signature,
                key_id=signed.key_id,
                algorithm=signed.algorithm,
            ),
        )

def parse_issue_request(payload: dict) -> CertificateIssueRequest:
    """Validate raw issuer input, converting Pydantic errors to domain errors."""
    try:
        return CertificateIssueRequest.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0]
        field = str(first["loc"][0]) if first.get("loc") else None
        raise CertificateValidationError(
            f"invalid certificate input: {first['msg']}", field=field
        ) from exc