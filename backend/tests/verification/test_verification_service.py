"""Tests for the verification workflow (service layer).

Real CryptoService (temporary Ed25519 keys), real CertificateRepository over
M4's in-memory FakeCollection, and real certificate issuance.
"""

from __future__ import annotations

from typing import get_args

import pytest
from pymongo.errors import PyMongoError

from app.certificates.exceptions import CertificateValidationError, StoredCertificateError
from app.database.exceptions import (
    CertificateNotFoundError,
    DatabaseError,
    DatabaseOperationError,
    DatabaseUnavailableError,
)
from app.database.repositories.certificate_repository import ACTIVE, REVOKED
from app.verification.exceptions import VerificationUnavailableError
from app.verification.schemas import LifecycleStatus, VerificationResponse, VerificationStatus
from app.verification.service import VerificationService

from .conftest import KEY_ID, make_crypto, write_key_pair

FIVE_FIELDS = {"certificate_id", "status", "signature_valid", "certificate_status", "message"}
MISSING = object()


def service_for(crypto, repository) -> VerificationService:
    return VerificationService(crypto, repository)


def stored(database, certificate_id: str) -> dict:
    return database.collection.documents[certificate_id]


# --------------------------------------------------------------------------- #
# 1-4. Signature and lifecycle outcomes
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_valid_signature_and_active_certificate(crypto, repository, issue):
    cid = await issue()
    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.VALID
    assert result.certificate_id == cid
    assert result.signature_valid is True
    assert result.certificate_status == "ACTIVE"
    assert result.message == "Certificate is authentic and active."


@pytest.mark.asyncio
async def test_valid_signature_and_revoked_certificate(crypto, repository, issue):
    cid = await issue()
    await repository.revoke_certificate(cid)

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.REVOKED
    assert result.signature_valid is True
    assert result.certificate_status == "REVOKED"
    assert result.message == "Certificate is authentic but has been revoked."


@pytest.mark.asyncio
async def test_signature_from_other_data_is_invalid(crypto, repository, database, issue):
    cid = await issue()
    stored(database, cid)["signature_metadata"]["signature"] = crypto.sign(b"other data").signature

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.INVALID
    assert result.signature_valid is False
    assert result.certificate_status == "ACTIVE"
    assert result.message == "Certificate integrity verification failed."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,new_value",
    [
        ("student_name", "Mallory Smith"),
        ("degree", "Master of Technology"),
        ("graduation_date", "2024-06-15"),
        ("student_id", "CS2021-999"),
        ("institution", "Another Institute"),
    ],
)
async def test_tampered_certificate_data_is_invalid(crypto, repository, database, issue, field, new_value):
    cid = await issue()
    stored(database, cid)["certificate_data"][field] = new_value  # still valid data, wrong signature

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.INVALID
    assert result.signature_valid is False


@pytest.mark.asyncio
async def test_revoked_certificate_with_invalid_signature_is_invalid(crypto, repository, database, issue):
    cid = await issue()
    await repository.revoke_certificate(cid)
    stored(database, cid)["certificate_data"]["student_name"] = "Mallory Smith"

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.INVALID  # signature has priority
    assert result.signature_valid is False
    assert result.certificate_status == "REVOKED"


@pytest.mark.asyncio
@pytest.mark.parametrize("signature", ["!!!not-base64!!!", "AAAA", "A" * 86, "ab cd"])
async def test_malformed_signature_value_is_invalid_not_an_infrastructure_error(
    crypto, repository, database, issue, signature
):
    cid = await issue()
    stored(database, cid)["signature_metadata"]["signature"] = signature

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.INVALID
    assert result.signature_valid is False


# --------------------------------------------------------------------------- #
# 5-6. Not found and malformed id
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_certificate_not_found(crypto, repository):
    cid = "CERT-" + "a" * 32

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.NOT_FOUND
    assert result.certificate_id == cid
    assert result.signature_valid is None
    assert result.certificate_status is None
    assert result.message == "Certificate was not found."


@pytest.mark.asyncio
async def test_repository_not_found_error_is_also_not_found(crypto):
    class Repo:
        async def get_certificate_by_id(self, certificate_id):
            raise CertificateNotFoundError("Certificate was not found")

    result = await service_for(crypto, Repo()).verify_certificate("CERT-" + "b" * 32)

    assert result.status is VerificationStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_unknown_certificate_is_not_found_even_if_signing_key_is_unconfigured(repository):
    result = await service_for(None, repository).verify_certificate("CERT-" + "c" * 32)

    assert result.status is VerificationStatus.NOT_FOUND


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_id",
    ["", "CERT-123", "cert-" + "a" * 32, "CERT-" + "A" * 32, "CERT-" + "a" * 33, "CERT-" + "g" * 32, None, 42],
)
async def test_malformed_certificate_id_never_reaches_the_database(crypto, repository, database, bad_id):
    database.collection.failure = PyMongoError("would surface as a database error if reached")

    with pytest.raises(CertificateValidationError):
        await service_for(crypto, repository).verify_certificate(bad_id)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# 7. Malformed stored certificate data
# --------------------------------------------------------------------------- #
def _drop(field):
    return lambda doc: doc["certificate_data"].pop(field)


def _set(field, value):
    return lambda doc: doc["certificate_data"].__setitem__(field, value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutate",
    [
        _drop("degree"),
        _drop("issue_date"),
        _drop("schema_version"),
        _set("graduation_date", "15-06-2025"),
        _set("graduation_date", "2025-02-30"),
        _set("issue_date", "2025-06-14"),  # before graduation
        _set("student_name", ""),
        _set("student_name", 123),
        _set("student_id", "bad id!"),
        _set("schema_version", "9.9"),
        _set("unexpected_field", "x"),
        _set("certificate_id", "CERT-" + "f" * 32),  # id must only be stored once
        lambda doc: doc.__setitem__("certificate_data", "not an object"),
        lambda doc: doc.__setitem__("certificate_data", None),
        lambda doc: doc.__setitem__("certificate_data", ["student_name"]),
        lambda doc: doc.pop("certificate_data"),
    ],
)
async def test_malformed_stored_certificate_data_is_invalid(crypto, repository, database, issue, mutate):
    cid = await issue()
    mutate(stored(database, cid))

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.INVALID
    assert result.signature_valid is False
    assert result.certificate_status == "ACTIVE"


@pytest.mark.asyncio
async def test_malformed_stored_data_never_leaks_validation_details(crypto, repository, database, issue):
    cid = await issue()
    stored(database, cid)["certificate_data"]["graduation_date"] = "15-06-2025"

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert "graduation" not in result.message.lower()
    assert "15-06-2025" not in result.model_dump_json()


# --------------------------------------------------------------------------- #
# 8-9. Signature metadata and algorithm
# --------------------------------------------------------------------------- #
def _meta_drop(field):
    return lambda doc: doc["signature_metadata"].pop(field)


def _meta_set(field, value):
    return lambda doc: doc["signature_metadata"].__setitem__(field, value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutate",
    [
        _meta_drop("signature"),
        _meta_drop("key_id"),
        _meta_drop("algorithm"),
        _meta_set("signature", ""),
        _meta_set("key_id", "   "),
        _meta_set("algorithm", ""),
        _meta_set("signature", 12345),
        _meta_set("key_id", None),
        _meta_set("algorithm", ["Ed25519"]),
        lambda doc: doc.__setitem__("signature_metadata", None),
        lambda doc: doc.__setitem__("signature_metadata", "signature"),
        lambda doc: doc.__setitem__("signature_metadata", ["x"]),
        lambda doc: doc.pop("signature_metadata"),
    ],
)
async def test_missing_or_malformed_signature_metadata_is_invalid(crypto, repository, database, issue, mutate):
    cid = await issue()
    mutate(stored(database, cid))

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.INVALID
    assert result.signature_valid is False


@pytest.mark.asyncio
@pytest.mark.parametrize("algorithm", ["RSA", "ed25519", "Ed448", "HS256", "none", " Ed25519"])
async def test_unsupported_signature_algorithm_is_invalid(crypto, repository, database, issue, algorithm):
    cid = await issue()
    stored(database, cid)["signature_metadata"]["algorithm"] = algorithm

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.INVALID
    assert result.signature_valid is False


# --------------------------------------------------------------------------- #
# 10-11. Key id and public key problems are UNVERIFIABLE, not INVALID
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_unsupported_key_id_is_unverifiable(crypto, repository, database, issue):
    cid = await issue()
    stored(database, cid)["signature_metadata"]["key_id"] = "an-older-key"

    with pytest.raises(VerificationUnavailableError):
        await service_for(crypto, repository).verify_certificate(cid)


@pytest.mark.asyncio
async def test_crypto_configured_with_a_different_key_id_is_unverifiable(key_files, repository, issue):
    cid = await issue()  # signed with KEY_ID
    rotated = make_crypto(key_files.private, key_files.public, key_id="credence-ed25519-v2")

    with pytest.raises(VerificationUnavailableError):
        await service_for(rotated, repository).verify_certificate(cid)


@pytest.mark.asyncio
async def test_missing_public_key_file_is_unverifiable(crypto, key_files, repository, issue):
    cid = await issue()
    key_files.public.unlink()

    with pytest.raises(VerificationUnavailableError):
        await service_for(crypto, repository).verify_certificate(cid)


@pytest.mark.asyncio
async def test_invalid_public_key_configuration_is_unverifiable(crypto, key_files, repository, issue):
    cid = await issue()
    key_files.public.write_text("this is not a PEM public key")

    with pytest.raises(VerificationUnavailableError):
        await service_for(crypto, repository).verify_certificate(cid)


@pytest.mark.asyncio
async def test_mismatched_key_pair_is_unverifiable(crypto, tmp_path, key_files, repository, issue):
    cid = await issue()
    _, other_public = write_key_pair(tmp_path, name="other")
    key_files.public.write_bytes(other_public.read_bytes())  # public no longer matches private

    with pytest.raises(VerificationUnavailableError):
        await service_for(crypto, repository).verify_certificate(cid)


@pytest.mark.asyncio
async def test_no_signing_keys_configured_is_unverifiable(repository, issue):
    cid = await issue()
    unconfigured = make_crypto(None, None)

    with pytest.raises(VerificationUnavailableError):
        await service_for(unconfigured, repository).verify_certificate(cid)


@pytest.mark.asyncio
async def test_crypto_that_could_not_be_created_is_unverifiable(repository, issue):
    cid = await issue()

    with pytest.raises(VerificationUnavailableError):
        await service_for(None, repository).verify_certificate(cid)


@pytest.mark.asyncio
async def test_key_that_disappears_during_verification_is_not_reported_as_forgery(
    crypto, key_files, repository, issue, monkeypatch
):
    cid = await issue()

    def vanishing_key_verify(*_args, **_kwargs):
        key_files.public.unlink()  # key lost after the preflight succeeded
        return False  # M3 reports infrastructure problems as False

    monkeypatch.setattr(crypto, "verify_signature", vanishing_key_verify)

    with pytest.raises(VerificationUnavailableError):
        await service_for(crypto, repository).verify_certificate(cid)


@pytest.mark.asyncio
async def test_key_problem_does_not_hide_malformed_metadata(crypto, key_files, repository, database, issue):
    cid = await issue()
    stored(database, cid)["signature_metadata"]["algorithm"] = "RSA"
    key_files.public.unlink()

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.INVALID  # metadata is checked before the key


# --------------------------------------------------------------------------- #
# 12. Database failures
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_database_retrieval_failure_propagates_as_database_error(crypto, repository, database, issue):
    cid = await issue()
    database.collection.failure = PyMongoError("mongodb://user:secret@host/internal")

    with pytest.raises(DatabaseOperationError) as error:
        await service_for(crypto, repository).verify_certificate(cid)
    assert "secret" not in str(error.value)


@pytest.mark.asyncio
async def test_database_unavailable_error_propagates(crypto):
    class Repo:
        async def get_certificate_by_id(self, certificate_id):
            raise DatabaseUnavailableError("Database has not been connected")

    with pytest.raises(DatabaseError):
        await service_for(crypto, Repo()).verify_certificate("CERT-" + "d" * 32)


@pytest.mark.asyncio
async def test_missing_repository_is_unverifiable(crypto):
    with pytest.raises(VerificationUnavailableError):
        await service_for(crypto, None).verify_certificate("CERT-" + "e" * 32)


# --------------------------------------------------------------------------- #
# 13. Lifecycle status
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["SUSPENDED", "active", "", " ACTIVE", None, ["ACTIVE"], 1, {"x": 1}])
async def test_unknown_lifecycle_status_is_an_internal_error_never_assumed_active(
    crypto, repository, database, issue, status
):
    cid = await issue()
    stored(database, cid)["status"] = status

    with pytest.raises(StoredCertificateError):
        await service_for(crypto, repository).verify_certificate(cid)


@pytest.mark.asyncio
async def test_invalid_signature_takes_priority_over_unknown_status(crypto, repository, database, issue):
    cid = await issue()
    stored(database, cid)["status"] = "SUSPENDED"
    stored(database, cid)["certificate_data"]["student_name"] = "Mallory Smith"

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.INVALID
    assert result.certificate_status is None  # cannot be safely determined


@pytest.mark.asyncio
async def test_legacy_record_without_status_is_active(crypto, repository, database, issue):
    cid = await issue()
    del stored(database, cid)["status"]  # issued before lifecycle support

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.VALID
    assert result.certificate_status == "ACTIVE"


@pytest.mark.asyncio
async def test_unknown_key_id_status_check_does_not_apply_before_signature(crypto, repository, database, issue):
    cid = await issue()
    stored(database, cid)["status"] = "SUSPENDED"
    stored(database, cid)["signature_metadata"]["key_id"] = "an-older-key"

    with pytest.raises(VerificationUnavailableError):  # infrastructure outranks lifecycle
        await service_for(crypto, repository).verify_certificate(cid)


# --------------------------------------------------------------------------- #
# Integrity of the verification itself
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_verification_does_not_modify_stored_records(crypto, repository, database, issue):
    from copy import deepcopy

    cid = await issue()
    before = deepcopy(stored(database, cid))

    await service_for(crypto, repository).verify_certificate(cid)

    assert stored(database, cid) == before


@pytest.mark.asyncio
async def test_certificate_signed_by_another_key_pair_is_invalid(tmp_path, crypto, repository, database, issue):
    cid = await issue()
    other = make_crypto(*write_key_pair(tmp_path, name="attacker"), key_id=KEY_ID)
    from app.certificates import Certificate, canonicalize

    record = stored(database, cid)
    forged = other.sign(
        canonicalize(Certificate.from_dict({"certificate_id": cid, **record["certificate_data"]}))
    )
    record["signature_metadata"]["signature"] = forged.signature  # same key id, different key

    result = await service_for(crypto, repository).verify_certificate(cid)

    assert result.status is VerificationStatus.INVALID


@pytest.mark.asyncio
async def test_genuine_record_of_another_certificate_is_invalid(crypto, repository, database, issue):
    """A genuine signed record must not be accepted as the answer for a different id."""
    from copy import deepcopy

    first = await issue()
    second = await issue(student_id="CS2021-002")

    class SubstitutingRepository:
        async def get_certificate_by_id(self, certificate_id):
            return deepcopy(stored(database, first))  # valid record, but for ``first``

    result = await service_for(crypto, SubstitutingRepository()).verify_certificate(second)

    assert result.status is VerificationStatus.INVALID
    assert result.certificate_id == second


# --------------------------------------------------------------------------- #
# Response schema
# --------------------------------------------------------------------------- #
def test_response_has_exactly_five_fields():
    assert set(VerificationResponse.model_fields) == FIVE_FIELDS
    cid = "CERT-" + "0" * 32
    for response in (
        VerificationResponse.valid(cid),
        VerificationResponse.revoked(cid),
        VerificationResponse.invalid(cid, "ACTIVE"),
        VerificationResponse.invalid(cid, None),
        VerificationResponse.not_found(cid),
        VerificationResponse.unverifiable(cid),
    ):
        assert set(response.model_dump()) == FIVE_FIELDS


def test_lifecycle_literals_match_the_repository_constants():
    assert get_args(LifecycleStatus) == (ACTIVE, REVOKED)
