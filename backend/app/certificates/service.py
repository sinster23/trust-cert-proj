"""M5 certificate issuance service: validate -> canonicalize -> sign (M3) -> persist (M4).

Collaborators are injected so this module opens no database connection and
handles no keys. It performs NO authorization: callers (the M5 router) must
enforce M2 issuer permissions before calling ``issue_certificate``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.crypto import CryptoService

from .canonicalization import canonicalize
from .exceptions import CertificateValidationError, StoredCertificateError
from .models import Certificate


@dataclass(frozen=True, slots=True)
class SignedCertificate:
    """Certificate data plus signature metadata, kept as separate concerns."""

    certificate: Certificate
    signature: str
    key_id: str
    algorithm: str


class CertificateService:
    def __init__(self, crypto: CryptoService, certificate_repository: Any) -> None:
        self._crypto = crypto
        self._repository = certificate_repository  # M4 CertificateRepository

    async def issue_certificate(
        self,
        *,
        student_id: str,
        student_name: str,
        institution: str,
        degree: str,
        field_of_study: str,
        graduation_date: str,
        issue_date: str | None = None,
    ) -> SignedCertificate:
        certificate = Certificate.issue(
            student_id=student_id,
            student_name=student_name,
            institution=institution,
            degree=degree,
            field_of_study=field_of_study,
            graduation_date=graduation_date,
            issue_date=issue_date,
        )
        result = self._crypto.sign(canonicalize(certificate))

        certificate_data = certificate.to_dict()
        certificate_data.pop("certificate_id")  # stored once, at the top level
        await self._repository.create_certificate(
            {
                "certificate_id": certificate.certificate_id,
                "certificate_data": certificate_data,
                "signature_metadata": {
                    "signature": result.signature,
                    "key_id": result.key_id,
                    "algorithm": result.algorithm,
                },
            }
        )
        # Reached only if persistence succeeded; M4 errors (e.g. duplicate ID)
        # propagate and nothing is returned.
        return SignedCertificate(
            certificate=certificate,
            signature=result.signature,
            key_id=result.key_id,
            algorithm=result.algorithm,
        )

    async def get_certificate(self, certificate_id: str) -> SignedCertificate | None:
        """Load an issued certificate; None if absent. Stored data is re-validated."""
        record = await self._repository.get_certificate_by_id(certificate_id)
        if record is None:
            return None
        try:
            metadata = record["signature_metadata"]
            certificate = Certificate.from_dict(
                {"certificate_id": record["certificate_id"], **record["certificate_data"]}
            )
            return SignedCertificate(
                certificate=certificate,
                signature=metadata["signature"],
                key_id=metadata["key_id"],
                algorithm=metadata["algorithm"],
            )
        except (CertificateValidationError, KeyError, TypeError) as exc:
            raise StoredCertificateError("Stored certificate record is invalid") from exc