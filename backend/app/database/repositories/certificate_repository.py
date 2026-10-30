"""Persistence for issued certificates (M4).

Stores plain records supplied by the certificate module; it does not import
M5 and does no signing or certificate validation. Certificate content is
insert-only; the only supported mutation is the atomic ACTIVE-to-REVOKED
lifecycle transition.

Record shape::

    {
        "certificate_id": "CERT-...",
        "certificate_data": {...},          # all fields except certificate_id
        "signature_metadata": {"signature": "...", "key_id": "...", "algorithm": "..."},
        "status": "ACTIVE",
    }
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from pymongo import ASCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from ..exceptions import (
    CertificateAlreadyRevokedError,
    CertificateNotFoundError,
    DatabaseOperationError,
    DuplicateDataError,
    InvalidDatabaseOperationError,
)

_RECORD_KEYS = {"certificate_id", "certificate_data", "signature_metadata"}
_SIGNATURE_KEYS = {"signature", "key_id", "algorithm"}
_CERTIFICATE_ID_PATTERN = re.compile(r"^CERT-[0-9a-f]{32}$")
ACTIVE = "ACTIVE"
REVOKED = "REVOKED"


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


class CertificateRepository:
    COLLECTION = "issued_certificates"
    CERTIFICATE_ID_INDEX = "uq_issued_certificates_certificate_id"

    def __init__(self, database: Any) -> None:
        self._collection = database[self.COLLECTION]

    async def ensure_indexes(self) -> None:
        try:
            await self._collection.create_index(
                [("certificate_id", ASCENDING)],
                unique=True,
                name=self.CERTIFICATE_ID_INDEX,
            )
        except PyMongoError as exc:
            raise DatabaseOperationError(
                "Could not initialize certificate constraints"
            ) from exc

    async def create_certificate(self, record: dict[str, Any]) -> dict[str, Any]:
        self._validate_record(record)
        document = deepcopy(record)  # insert_one would otherwise add _id to the caller's dict
        document["status"] = ACTIVE
        try:
            await self._collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise DuplicateDataError("A certificate with this ID already exists") from exc
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not save certificate") from exc
        return deepcopy(document)

    async def get_certificate_by_id(self, certificate_id: str) -> dict[str, Any] | None:
        self._validate_certificate_id(certificate_id)
        try:
            record = await self._collection.find_one(
                {"certificate_id": certificate_id}, {"_id": 0}
            )
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not retrieve certificate") from exc
        if record is not None:
            # Existing records predate lifecycle status and are treated as active.
            record.setdefault("status", ACTIVE)
        return record

    async def revoke_certificate(self, certificate_id: str) -> dict[str, Any]:
        """Atomically transition an active certificate to revoked.

        Legacy records without a status are treated as active so certificates
        issued before lifecycle support can still be revoked.
        """
        self._validate_certificate_id(certificate_id)
        try:
            record = await self._collection.find_one_and_update(
                {
                    "certificate_id": certificate_id,
                    "$or": [
                        {"status": ACTIVE},
                        {"status": {"$exists": False}},
                    ],
                },
                {"$set": {"status": REVOKED}},
                return_document=ReturnDocument.AFTER,
                projection={"_id": 0},
            )
            if record is not None:
                return record

            existing = await self._collection.find_one(
                {"certificate_id": certificate_id}, {"_id": 0}
            )
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not revoke certificate") from exc

        if existing is None:
            raise CertificateNotFoundError("Certificate was not found")
        if existing.get("status") == REVOKED:
            raise CertificateAlreadyRevokedError("Certificate has already been revoked")
        raise DatabaseOperationError("Certificate has an invalid lifecycle status")

    @staticmethod
    def _validate_certificate_id(certificate_id: Any) -> None:
        if not isinstance(certificate_id, str) or not _CERTIFICATE_ID_PATTERN.fullmatch(
            certificate_id
        ):
            raise InvalidDatabaseOperationError("Certificate identifier is invalid")

    @staticmethod
    def _validate_record(record: Any) -> None:
        if not isinstance(record, dict) or set(record) != _RECORD_KEYS:
            raise InvalidDatabaseOperationError("Certificate record has an invalid shape")
        if not _non_empty_str(record["certificate_id"]):
            raise InvalidDatabaseOperationError("Certificate identifier is invalid")
        if not isinstance(record["certificate_data"], dict) or not record["certificate_data"]:
            raise InvalidDatabaseOperationError("Certificate data is invalid")
        if "certificate_id" in record["certificate_data"]:
            raise InvalidDatabaseOperationError("Certificate data must not repeat the ID")
        metadata = record["signature_metadata"]
        if (
            not isinstance(metadata, dict)
            or set(metadata) != _SIGNATURE_KEYS
            or not all(_non_empty_str(metadata[key]) for key in _SIGNATURE_KEYS)
        ):
            raise InvalidDatabaseOperationError("Signature metadata is invalid")
