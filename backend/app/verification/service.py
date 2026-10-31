"""Public certificate verification workflow.

    validate id -> load record (M4) -> rebuild + canonicalize (M5)
    -> validate signature metadata -> preflight key (M3) -> verify (M3)
    -> evaluate lifecycle status

Outcomes
--------
Returned as a ``VerificationResponse``: VALID, REVOKED, INVALID, NOT_FOUND.
Raised, and mapped to HTTP by the router:

* ``VerificationUnavailableError`` - UNVERIFIABLE (key / store unavailable).
* ``DatabaseError`` (other than "not found") - the store failed.
* ``StoredCertificateError`` - the stored lifecycle status is unknown.
* ``CertificateValidationError`` - the certificate id itself is malformed.

Why the key preflight exists
----------------------------
``CryptoService.verify_signature`` returns ``False`` for an invalid signature
*and* for infrastructure problems (missing or invalid key, key-id mismatch).
Those must not be reported as a forged certificate, so the stored key id and
the public key are checked first, and ``False`` is only interpreted as an
invalid signature after that.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.certificates import Certificate, canonicalize
from app.certificates.exceptions import CertificateError, StoredCertificateError
from app.certificates.models import validate_certificate_id
from app.crypto import CryptoService
from app.crypto.exceptions import CryptoError
from app.crypto.keys import ALGORITHM
from app.database.exceptions import CertificateNotFoundError
from app.database.repositories.certificate_repository import (
    ACTIVE,
    REVOKED,
    CertificateRepository,
)

from .exceptions import VerificationUnavailableError
from .schemas import LifecycleStatus, VerificationResponse

logger = logging.getLogger(__name__)

_SIGNATURE_FIELDS = ("signature", "key_id", "algorithm")


class _InvalidRecord(Exception):
    """Internal: the stored record cannot be a genuine certificate (-> INVALID)."""


@dataclass(frozen=True, slots=True)
class _SignedMaterial:
    canonical_data: bytes
    signature: str
    key_id: str


def _lifecycle_status(record: Any) -> LifecycleStatus | None:
    """The stored status if it is ACTIVE or REVOKED, otherwise None (never assume)."""
    if not isinstance(record, Mapping):
        return None
    status = record.get("status")
    if isinstance(status, str) and status in (ACTIVE, REVOKED):
        return status  # type: ignore[return-value]
    return None


def _extract_signed_material(certificate_id: str, record: Any) -> _SignedMaterial:
    """Rebuild the signed certificate and read the signature metadata.

    Raises ``_InvalidRecord`` for malformed stored data, malformed or missing
    signature metadata, and unsupported algorithms.
    """
    if not isinstance(record, Mapping):
        raise _InvalidRecord("stored record is not an object")

    stored_data = record.get("certificate_data")
    if not isinstance(stored_data, Mapping):
        raise _InvalidRecord("certificate data is missing or malformed")
    if "certificate_id" in stored_data:
        # M4 stores the id once, at the top level. A copy inside the data could
        # silently override it when the two are merged below.
        raise _InvalidRecord("certificate data repeats the certificate id")

    try:
        certificate = Certificate.from_dict(
            {"certificate_id": record.get("certificate_id"), **stored_data}
        )
        canonical_data = canonicalize(certificate.to_dict())
    except (CertificateError, TypeError, ValueError) as exc:
        raise _InvalidRecord(
            f"stored certificate data failed validation ({type(exc).__name__})"
        ) from exc
    if certificate.certificate_id != certificate_id:
        raise _InvalidRecord("stored certificate id does not match the request")

    metadata = record.get("signature_metadata")
    if not isinstance(metadata, Mapping):
        raise _InvalidRecord("signature metadata is missing or malformed")
    values = {name: metadata.get(name) for name in _SIGNATURE_FIELDS}
    if not all(isinstance(value, str) and value.strip() for value in values.values()):
        raise _InvalidRecord("signature metadata has missing or empty fields")
    if values["algorithm"] != ALGORITHM:
        raise _InvalidRecord("unsupported signature algorithm")

    return _SignedMaterial(
        canonical_data=canonical_data,
        signature=values["signature"],
        key_id=values["key_id"],
    )


class VerificationService:
    """Verifies stored certificates. No authentication or authorization (public)."""

    def __init__(
        self,
        crypto: CryptoService | None,
        repository: CertificateRepository | None,
    ) -> None:
        # ``None`` means "could not be configured": reported as UNVERIFIABLE,
        # and only once it is actually needed (a missing certificate is still
        # NOT_FOUND even when the signing key is misconfigured).
        self._crypto = crypto
        self._repository = repository

    async def verify_certificate(self, certificate_id: str) -> VerificationResponse:
        # Defensive: the router already validates the id. Validating here keeps
        # M4's InvalidDatabaseOperationError from ever being mistaken for an outage.
        certificate_id = validate_certificate_id(certificate_id)

        record = await self._load_record(certificate_id)
        if record is None:
            return VerificationResponse.not_found(certificate_id)

        lifecycle = _lifecycle_status(record)

        try:
            material = _extract_signed_material(certificate_id, record)
        except _InvalidRecord as exc:
            logger.warning("Certificate %s classified INVALID: %s", certificate_id, exc)
            return VerificationResponse.invalid(certificate_id, lifecycle)

        crypto = self._preflight(material.key_id)

        if not self._signature_is_valid(crypto, material):
            logger.warning(
                "Certificate %s classified INVALID: signature mismatch", certificate_id
            )
            return VerificationResponse.invalid(certificate_id, lifecycle)

        # Signature verification has priority: lifecycle is only consulted for
        # an authentic certificate.
        if lifecycle == ACTIVE:
            return VerificationResponse.valid(certificate_id)
        if lifecycle == REVOKED:
            return VerificationResponse.revoked(certificate_id)
        raise StoredCertificateError("Stored certificate has an unknown lifecycle status")

    async def _load_record(self, certificate_id: str) -> Mapping[str, Any] | None:
        if self._repository is None:
            raise VerificationUnavailableError("Certificate store is not available")
        try:
            return await self._repository.get_certificate_by_id(certificate_id)
        except CertificateNotFoundError:
            return None
        # Any other DatabaseError propagates; the router maps it to HTTP 503.

    def _preflight(self, key_id: str) -> CryptoService:
        crypto = self._crypto
        if crypto is None:
            raise VerificationUnavailableError("Signing service is not configured")
        if key_id != crypto.key_id:
            raise VerificationUnavailableError(
                "Certificate was signed with a key other than the configured key"
            )
        self._require_public_key(crypto)
        return crypto

    @staticmethod
    def _require_public_key(crypto: CryptoService) -> None:
        try:
            crypto.get_public_key_pem()
        except (CryptoError, OSError) as exc:
            raise VerificationUnavailableError("Public key is unavailable") from exc

    def _signature_is_valid(self, crypto: CryptoService, material: _SignedMaterial) -> bool:
        try:
            valid = crypto.verify_signature(
                material.canonical_data, material.signature, key_id=material.key_id
            )
        except CryptoError as exc:
            raise VerificationUnavailableError("Signature verification is unavailable") from exc
        if valid:
            return True
        # ``False`` can also mean the key vanished after the preflight. Check
        # again so a key problem is never reported as a forged certificate.
        self._require_public_key(crypto)
        return False
