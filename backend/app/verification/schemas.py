from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.certificates import Certificate

from .masking import mask_student_id


class VerificationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    REVOKED = "REVOKED"
    NOT_FOUND = "NOT_FOUND"
    UNVERIFIABLE = "UNVERIFIABLE"


LifecycleStatus = Literal["ACTIVE", "REVOKED"]
DETAIL_STATUSES = frozenset({VerificationStatus.VALID, VerificationStatus.REVOKED})

MESSAGE_VALID = "Certificate is authentic and active."
MESSAGE_REVOKED = "Certificate is authentic but has been revoked."
MESSAGE_INVALID = "Certificate integrity verification failed."
MESSAGE_NOT_FOUND = "Certificate was not found."
MESSAGE_UNVERIFIABLE = "Certificate verification is temporarily unavailable."


class CertificateDetails(BaseModel):
    """The seven public fields. student_id is always the masked form."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    student_id: str
    student_name: str
    institution: str
    degree: str
    field_of_study: str
    graduation_date: str
    issue_date: str

    @classmethod
    def from_certificate(cls, certificate: Certificate) -> "CertificateDetails":
        # Only call with a certificate whose signature has been verified.
        return cls(
            student_id=mask_student_id(certificate.student_id),
            student_name=certificate.student_name,
            institution=certificate.institution,
            degree=certificate.degree,
            field_of_study=certificate.field_of_study,
            graduation_date=certificate.graduation_date,
            issue_date=certificate.issue_date,
        )


class VerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    certificate_id: str
    status: VerificationStatus
    signature_valid: bool | None
    certificate_status: LifecycleStatus | None
    message: str
    details_available: bool
    certificate_details: CertificateDetails | None

    @model_validator(mode="after")
    def _details_only_for_valid_or_revoked(self) -> "VerificationResponse":
        has_details = self.certificate_details is not None
        if has_details and self.status not in DETAIL_STATUSES:
            raise ValueError("certificate details are only allowed for VALID or REVOKED")
        if self.details_available != has_details:
            raise ValueError("details_available must match certificate_details")
        return self

    @classmethod
    def valid(cls, certificate_id: str, details: CertificateDetails | None = None):
        return cls(certificate_id=certificate_id, status=VerificationStatus.VALID,
                   signature_valid=True, certificate_status="ACTIVE", message=MESSAGE_VALID,
                   details_available=details is not None, certificate_details=details)

    @classmethod
    def revoked(cls, certificate_id: str, details: CertificateDetails | None = None):
        return cls(certificate_id=certificate_id, status=VerificationStatus.REVOKED,
                   signature_valid=True, certificate_status="REVOKED", message=MESSAGE_REVOKED,
                   details_available=details is not None, certificate_details=details)

    @classmethod
    def invalid(cls, certificate_id: str, certificate_status: LifecycleStatus | None):
        return cls(certificate_id=certificate_id, status=VerificationStatus.INVALID,
                   signature_valid=False, certificate_status=certificate_status,
                   message=MESSAGE_INVALID, details_available=False, certificate_details=None)

    @classmethod
    def not_found(cls, certificate_id: str):
        return cls(certificate_id=certificate_id, status=VerificationStatus.NOT_FOUND,
                   signature_valid=None, certificate_status=None, message=MESSAGE_NOT_FOUND,
                   details_available=False, certificate_details=None)

    @classmethod
    def unverifiable(cls, certificate_id: str):
        return cls(certificate_id=certificate_id, status=VerificationStatus.UNVERIFIABLE,
                   signature_valid=None, certificate_status=None, message=MESSAGE_UNVERIFIABLE,
                   details_available=False, certificate_details=None)