"""Public certificate verification endpoint.

    GET /certificates/verify/{certificate_id}      (no authentication)

The router validates the id, calls ``VerificationService`` and maps outcomes
to HTTP. Every verification outcome uses the same five-field response body;
only a malformed id (422, request validation) and unexpected server errors
(500) use other formats.

Dependencies are defined here on purpose: importing them from the certificate
issuance router would couple the two routers. Unlike that router's
dependencies, these never raise; a component that cannot be configured is
passed on as ``None`` so the service can answer UNVERIFIABLE in the normal
response format (while an unknown certificate is still NOT_FOUND).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status

from app.auth.dependencies import DATABASE_MANAGER_STATE_ATTRS
from app.certificates.exceptions import CertificateError, CertificateValidationError
from app.crypto import CryptoService
from app.crypto.exceptions import CryptoError
from app.database.connection import DatabaseManager
from app.database.exceptions import DatabaseError
from app.database.repositories.certificate_repository import CertificateRepository

from .exceptions import VerificationUnavailableError
from .schemas import VerificationResponse, VerificationStatus
from .service import VerificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/certificates", tags=["verification"])

# Same pattern as the M5 certificate id format (a test keeps them in sync).
CERTIFICATE_ID_PATTERN = r"^CERT-[0-9a-f]{32}$"


def get_verification_crypto() -> CryptoService | None:
    try:
        return CryptoService()
    except CryptoError:
        logger.error("Signing service is not configured correctly")
        return None


def get_verification_repository(request: Request) -> CertificateRepository | None:
    """Build the M4 repository from the shared DatabaseManager on app.state."""
    for attr in DATABASE_MANAGER_STATE_ATTRS:
        manager = getattr(request.app.state, attr, None)
        if isinstance(manager, DatabaseManager):
            try:
                return CertificateRepository(manager.get_database())
            except DatabaseError:
                logger.error("Database is not available for certificate verification")
                return None
    logger.error("DatabaseManager not found on app.state")
    return None


def get_verification_service(
    crypto: Annotated[CryptoService | None, Depends(get_verification_crypto)],
    repository: Annotated[CertificateRepository | None, Depends(get_verification_repository)],
) -> VerificationService:
    return VerificationService(crypto, repository)


@router.get(
    "/verify/{certificate_id}",
    response_model=VerificationResponse,
    summary="Verify a certificate (public)",
    responses={
        404: {"model": VerificationResponse, "description": "Certificate not found"},
        503: {"model": VerificationResponse, "description": "Verification unavailable"},
        500: {"description": "Stored certificate data is inconsistent"},
    },
)
async def verify_certificate(
    certificate_id: Annotated[str, Path(pattern=CERTIFICATE_ID_PATTERN)],
    response: Response,
    service: Annotated[VerificationService, Depends(get_verification_service)],
) -> VerificationResponse:
    # Revocation can change at any time: results must not be cached.
    response.headers["Cache-Control"] = "no-store"
    try:
        result = await service.verify_certificate(certificate_id)
    except (VerificationUnavailableError, DatabaseError):
        logger.exception("Certificate verification unavailable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return VerificationResponse.unverifiable(certificate_id)
    except CertificateValidationError:
        # Unreachable through HTTP (the path pattern rejects it first).
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid certificate ID")
    except CertificateError:
        logger.exception("Stored certificate record is inconsistent")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Stored certificate could not be verified"
        )

    if result.status is VerificationStatus.NOT_FOUND:
        response.status_code = status.HTTP_404_NOT_FOUND
    return result
