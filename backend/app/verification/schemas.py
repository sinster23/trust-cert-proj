"""Response schema for public certificate verification.

Every verification outcome uses the same five fields. No student data and no
internal details are ever part of the response.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class VerificationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    REVOKED = "REVOKED"
    NOT_FOUND = "NOT_FOUND"
    UNVERIFIABLE = "UNVERIFIABLE"


# Mirrors ACTIVE / REVOKED in the M4 certificate repository (checked by a test).
LifecycleStatus = Literal["ACTIVE", "REVOKED"]

MESSAGE_VALID = "Certificate is authentic and active."
MESSAGE_REVOKED = "Certificate is authentic but has been revoked."
MESSAGE_INVALID = "Certificate integrity verification failed."
MESSAGE_NOT_FOUND = "Certificate was not found."
MESSAGE_UNVERIFIABLE = "Certificate verification is temporarily unavailable."


class VerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    certificate_id: str
    status: VerificationStatus
    signature_valid: bool | None
    certificate_status: LifecycleStatus | None
    message: str

    @classmethod
    def valid(cls, certificate_id: str) -> "VerificationResponse":
        return cls(
            certificate_id=certificate_id,
            status=VerificationStatus.VALID,
            signature_valid=True,
            certificate_status="ACTIVE",
            message=MESSAGE_VALID,
        )

    @classmethod
    def revoked(cls, certificate_id: str) -> "VerificationResponse":
        return cls(
            certificate_id=certificate_id,
            status=VerificationStatus.REVOKED,
            signature_valid=True,
            certificate_status="REVOKED",
            message=MESSAGE_REVOKED,
        )

    @classmethod
    def invalid(
        cls, certificate_id: str, certificate_status: LifecycleStatus | None
    ) -> "VerificationResponse":
        """``certificate_status`` is None when it cannot be safely determined."""
        return cls(
            certificate_id=certificate_id,
            status=VerificationStatus.INVALID,
            signature_valid=False,
            certificate_status=certificate_status,
            message=MESSAGE_INVALID,
        )

    @classmethod
    def not_found(cls, certificate_id: str) -> "VerificationResponse":
        return cls(
            certificate_id=certificate_id,
            status=VerificationStatus.NOT_FOUND,
            signature_valid=None,
            certificate_status=None,
            message=MESSAGE_NOT_FOUND,
        )

    @classmethod
    def unverifiable(cls, certificate_id: str) -> "VerificationResponse":
        return cls(
            certificate_id=certificate_id,
            status=VerificationStatus.UNVERIFIABLE,
            signature_valid=None,
            certificate_status=None,
            message=MESSAGE_UNVERIFIABLE,
        )
