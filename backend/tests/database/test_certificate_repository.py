from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.certificates.service import CertificateService
from app.database.exceptions import (
    CertificateAlreadyRevokedError,
    CertificateNotFoundError,
    DatabaseOperationError,
    DuplicateDataError,
    InvalidDatabaseOperationError,
)
from app.database.repositories.certificate_repository import CertificateRepository

CERTIFICATE_ID = "CERT-0123456789abcdef0123456789abcdef"


def make_record(certificate_id: str = CERTIFICATE_ID) -> dict:
    return {
        "certificate_id": certificate_id,
        "certificate_data": {
            "student_name": "Asha Rao",
            "degree": "Bachelor of Technology",
        },
        "signature_metadata": {
            "signature": "signed-value",
            "key_id": "key-1",
            "algorithm": "Ed25519",
        },
    }


class FakeCollection:
    def __init__(self):
        self.documents = {}
        self.failure = None

    async def insert_one(self, document):
        if self.failure:
            raise self.failure
        certificate_id = document["certificate_id"]
        if certificate_id in self.documents:
            raise DuplicateKeyError("sensitive duplicate detail")
        self.documents[certificate_id] = deepcopy(document)

    async def find_one(self, query, projection=None):
        if self.failure:
            raise self.failure
        record = self.documents.get(query["certificate_id"])
        return deepcopy(record) if record is not None else None

    async def find_one_and_update(
        self, query, update, *, return_document, projection=None
    ):
        if self.failure:
            raise self.failure
        record = self.documents.get(query["certificate_id"])
        if record is None:
            return None
        active_or_legacy = record.get("status") == "ACTIVE" or "status" not in record
        if not active_or_legacy:
            return None
        record.update(deepcopy(update["$set"]))
        return deepcopy(record)


class FakeDatabase:
    def __init__(self):
        self.collection = FakeCollection()

    def __getitem__(self, name):
        assert name == "issued_certificates"
        return self.collection


@pytest.fixture
def database():
    return FakeDatabase()


@pytest.fixture
def repository(database):
    return CertificateRepository(database)


@pytest.mark.asyncio
async def test_create_defaults_status_and_retrieval_returns_complete_record(repository, database):
    source = make_record()
    created = await repository.create_certificate(source)

    assert source == make_record()  # caller's signed input is not mutated
    assert created == {**source, "status": "ACTIVE"}
    assert database.collection.documents[CERTIFICATE_ID] == created
    assert await repository.get_certificate_by_id(CERTIFICATE_ID) == created


@pytest.mark.asyncio
async def test_revocation_changes_only_status(repository, database):
    created = await repository.create_certificate(make_record())
    original_data = deepcopy(created["certificate_data"])
    original_metadata = deepcopy(created["signature_metadata"])

    revoked = await repository.revoke_certificate(CERTIFICATE_ID)

    assert revoked["status"] == "REVOKED"
    assert revoked["certificate_data"] == original_data
    assert revoked["signature_metadata"] == original_metadata
    assert database.collection.documents[CERTIFICATE_ID] == revoked
    assert await repository.get_certificate_by_id(CERTIFICATE_ID) == revoked


@pytest.mark.asyncio
async def test_legacy_certificate_without_status_is_active_and_can_be_revoked(repository, database):
    legacy = make_record()
    database.collection.documents[CERTIFICATE_ID] = deepcopy(legacy)

    assert await repository.get_certificate_by_id(CERTIFICATE_ID) == {
        **legacy,
        "status": "ACTIVE",
    }
    revoked = await repository.revoke_certificate(CERTIFICATE_ID)
    assert revoked == {**legacy, "status": "REVOKED"}


@pytest.mark.asyncio
async def test_missing_and_repeated_revocation_have_explicit_errors(repository):
    with pytest.raises(CertificateNotFoundError, match="not found"):
        await repository.revoke_certificate(CERTIFICATE_ID)

    await repository.create_certificate(make_record())
    await repository.revoke_certificate(CERTIFICATE_ID)
    with pytest.raises(CertificateAlreadyRevokedError, match="already been revoked"):
        await repository.revoke_certificate(CERTIFICATE_ID)


@pytest.mark.asyncio
async def test_certificate_id_validation(repository):
    for bad_id in ("", "CERT-123", None):
        with pytest.raises(InvalidDatabaseOperationError):
            await repository.revoke_certificate(bad_id)
    with pytest.raises(InvalidDatabaseOperationError):
        await repository.get_certificate_by_id("CERT-123")


@pytest.mark.asyncio
async def test_repository_database_errors_are_wrapped_and_sanitized(repository, database):
    database.collection.failure = PyMongoError("mongodb://user:secret@host/internal")
    with pytest.raises(DatabaseOperationError) as error:
        await repository.revoke_certificate(CERTIFICATE_ID)
    assert "secret" not in str(error.value)

    with pytest.raises(DatabaseOperationError):
        await repository.get_certificate_by_id(CERTIFICATE_ID)


@pytest.mark.asyncio
async def test_duplicate_certificate_id_handling_is_preserved(repository):
    await repository.create_certificate(make_record())
    with pytest.raises(DuplicateDataError):
        await repository.create_certificate(make_record())


@pytest.mark.asyncio
async def test_certificate_issuance_keeps_existing_repository_contract(repository):
    class FakeCrypto:
        def sign(self, _message):
            return SimpleNamespace(
                signature="signature",
                key_id="key-1",
                algorithm="Ed25519",
            )

    service = CertificateService(FakeCrypto(), repository)
    issued = await service.issue_certificate(
        student_id="CS2021-001",
        student_name="Asha Rao",
        institution="Example Institute",
        degree="Bachelor of Technology",
        field_of_study="Computer Science",
        graduation_date="2025-06-15",
        issue_date="2025-07-01",
    )

    stored = await repository.get_certificate_by_id(issued.certificate.certificate_id)
    assert stored is not None
    assert stored["status"] == "ACTIVE"
    assert stored["signature_metadata"]["signature"] == "signature"
    assert stored["certificate_data"]["student_name"] == "Asha Rao"
