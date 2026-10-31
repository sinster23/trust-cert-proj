"""Tests for the public verification endpoint.

Uses the real ``app.main.app`` with ``dependency_overrides``. ``TestClient`` is
not used as a context manager, so the MongoDB-connecting lifespan never runs.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import PyMongoError

from app.certificates import models as certificate_models
from app.certificates.router import CERTIFICATE_ID_PATTERN as ISSUANCE_ROUTER_PATTERN
from app.main import app
from app.verification.router import (
    CERTIFICATE_ID_PATTERN,
    get_verification_crypto,
    get_verification_repository,
)

from .conftest import STUDENT, make_crypto

FIVE_FIELDS = {"certificate_id", "status", "signature_valid", "certificate_status", "message"}
UNVERIFIABLE_MESSAGE = "Certificate verification is temporarily unavailable."
VERIFY_PATH = "/certificates/verify/{certificate_id}"


@pytest.fixture
def client(crypto, repository):
    app.dependency_overrides[get_verification_crypto] = lambda: crypto
    app.dependency_overrides[get_verification_repository] = lambda: repository
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def cid(issue) -> str:
    return asyncio.run(issue())


def verify(client, certificate_id, **kwargs):
    return client.get(f"/certificates/verify/{certificate_id}", **kwargs)


def stored(database, certificate_id):
    return database.collection.documents[certificate_id]


def assert_five_fields_only(response):
    body = response.json()
    assert set(body) == FIVE_FIELDS
    text = response.text
    for private_value in STUDENT.values():
        assert private_value not in text  # no student information
    return body


# --------------------------------------------------------------------------- #
# 1-5. Outcomes and exact response bodies
# --------------------------------------------------------------------------- #
def test_valid_certificate(client, cid):
    response = verify(client, cid)

    assert response.status_code == 200
    assert response.json() == {
        "certificate_id": cid,
        "status": "VALID",
        "signature_valid": True,
        "certificate_status": "ACTIVE",
        "message": "Certificate is authentic and active.",
    }


def test_revoked_certificate(client, repository, cid):
    asyncio.run(repository.revoke_certificate(cid))

    response = verify(client, cid)

    assert response.status_code == 200
    assert response.json() == {
        "certificate_id": cid,
        "status": "REVOKED",
        "signature_valid": True,
        "certificate_status": "REVOKED",
        "message": "Certificate is authentic but has been revoked.",
    }


def test_invalid_signature(client, database, crypto, cid):
    stored(database, cid)["signature_metadata"]["signature"] = crypto.sign(b"other").signature

    response = verify(client, cid)

    assert response.status_code == 200
    assert response.json() == {
        "certificate_id": cid,
        "status": "INVALID",
        "signature_valid": False,
        "certificate_status": "ACTIVE",
        "message": "Certificate integrity verification failed.",
    }


def test_tampered_data_is_invalid(client, database, cid):
    stored(database, cid)["certificate_data"]["student_name"] = "Mallory Smith"

    response = verify(client, cid)

    assert response.status_code == 200
    assert response.json()["status"] == "INVALID"
    assert "Mallory" not in response.text


def test_revoked_certificate_with_invalid_signature_is_invalid(client, repository, database, cid):
    asyncio.run(repository.revoke_certificate(cid))
    stored(database, cid)["certificate_data"]["degree"] = "Doctor of Philosophy"

    response = verify(client, cid)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "INVALID"
    assert body["signature_valid"] is False
    assert body["certificate_status"] == "REVOKED"


def test_certificate_not_found_uses_the_five_field_body_not_detail(client):
    unknown = "CERT-" + "9" * 32

    response = verify(client, unknown)

    assert response.status_code == 404
    assert response.json() == {
        "certificate_id": unknown,
        "status": "NOT_FOUND",
        "signature_valid": None,
        "certificate_status": None,
        "message": "Certificate was not found.",
    }
    assert "detail" not in response.json()


# --------------------------------------------------------------------------- #
# 6. Malformed certificate id -> 422 (request validation), before any lookup
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "bad_id",
    [
        "CERT-123",
        "cert-" + "a" * 32,
        "CERT-" + "A" * 32,
        "CERT-" + "a" * 31,
        "CERT-" + "a" * 33,
        "CERT-" + "g" * 32,
        "INVALID",
        "CERT-" + "a" * 32 + "x",
        "%20CERT-" + "a" * 32,
    ],
)
def test_malformed_certificate_id_returns_422_without_touching_the_database(client, database, bad_id):
    database.collection.failure = PyMongoError("would surface as 503 if the database were reached")

    response = verify(client, bad_id)

    assert response.status_code == 422
    body = response.json()
    assert isinstance(body["detail"], list)  # FastAPI's normal validation format
    assert "status" not in body


def test_id_pattern_matches_the_m5_certificate_id_format():
    assert CERTIFICATE_ID_PATTERN == r"^CERT-[0-9a-f]{32}$"
    assert CERTIFICATE_ID_PATTERN == certificate_models._CERTIFICATE_ID_PATTERN.pattern
    assert CERTIFICATE_ID_PATTERN == ISSUANCE_ROUTER_PATTERN


# --------------------------------------------------------------------------- #
# 7-9. Malformed stored data, metadata, algorithm -> INVALID (200)
# --------------------------------------------------------------------------- #
def test_malformed_stored_certificate_data_is_invalid(client, database, cid):
    stored(database, cid)["certificate_data"]["graduation_date"] = "not-a-date"

    response = verify(client, cid)

    assert response.status_code == 200
    body = assert_five_fields_only(response)
    assert body["status"] == "INVALID"
    assert body["signature_valid"] is False
    assert "not-a-date" not in response.text


@pytest.mark.parametrize("field", ["signature", "key_id", "algorithm"])
def test_missing_signature_metadata_field_is_invalid(client, database, cid, field):
    del stored(database, cid)["signature_metadata"][field]

    response = verify(client, cid)

    assert response.status_code == 200
    assert response.json()["status"] == "INVALID"


def test_malformed_signature_metadata_is_invalid(client, database, cid):
    stored(database, cid)["signature_metadata"] = "garbage"

    response = verify(client, cid)

    assert response.status_code == 200
    assert response.json()["status"] == "INVALID"


def test_unsupported_signature_algorithm_is_invalid(client, database, cid):
    stored(database, cid)["signature_metadata"]["algorithm"] = "RSA"

    response = verify(client, cid)

    assert response.status_code == 200
    assert response.json()["status"] == "INVALID"


def test_garbled_signature_value_is_invalid_not_unavailable(client, database, cid):
    stored(database, cid)["signature_metadata"]["signature"] = "!!!not-base64!!!"

    response = verify(client, cid)

    assert response.status_code == 200
    assert response.json()["status"] == "INVALID"


# --------------------------------------------------------------------------- #
# 10-12. UNVERIFIABLE (503) in the five-field format, without internals
# --------------------------------------------------------------------------- #
def assert_unverifiable(response, certificate_id):
    assert response.status_code == 503
    assert response.json() == {
        "certificate_id": certificate_id,
        "status": "UNVERIFIABLE",
        "signature_valid": None,
        "certificate_status": None,
        "message": UNVERIFIABLE_MESSAGE,
    }


def test_unsupported_key_id_is_unverifiable(client, database, cid):
    stored(database, cid)["signature_metadata"]["key_id"] = "retired-key-v0"

    response = verify(client, cid)

    assert_unverifiable(response, cid)
    assert "retired-key-v0" not in response.text
    assert "test-key-v1" not in response.text  # configured key id stays internal


def test_missing_public_key_is_unverifiable(client, key_files, cid):
    key_files.public.unlink()

    response = verify(client, cid)

    assert_unverifiable(response, cid)
    assert str(key_files.public) not in response.text
    assert ".pem" not in response.text


def test_invalid_key_configuration_is_unverifiable(client, key_files, cid):
    key_files.public.write_text("not a key")

    assert_unverifiable(verify(client, cid), cid)


def test_signing_service_that_cannot_be_configured_is_unverifiable(repository, cid):
    app.dependency_overrides[get_verification_crypto] = lambda: None
    app.dependency_overrides[get_verification_repository] = lambda: repository
    try:
        response = verify(TestClient(app), cid)
    finally:
        app.dependency_overrides.clear()

    assert_unverifiable(response, cid)


def test_database_failure_is_service_unavailable(client, database, cid):
    database.collection.failure = PyMongoError("mongodb://user:secret@host/internal")

    response = verify(client, cid)

    assert_unverifiable(response, cid)
    assert "secret" not in response.text
    assert "mongodb" not in response.text


def test_unconfigured_application_reports_unverifiable_instead_of_crashing():
    app.dependency_overrides.clear()  # real dependencies; lifespan never ran, so no database manager
    target = "CERT-" + "7" * 32

    response = verify(TestClient(app), target)

    assert_unverifiable(response, target)


# --------------------------------------------------------------------------- #
# 13. Unknown lifecycle status -> 500 without internals
# --------------------------------------------------------------------------- #
def test_unknown_lifecycle_status_returns_a_safe_500(client, database, cid):
    stored(database, cid)["status"] = "SUSPENDED"

    response = verify(client, cid)

    assert response.status_code == 500
    assert response.json() == {"detail": "Stored certificate could not be verified"}
    assert "SUSPENDED" not in response.text
    assert "Traceback" not in response.text


def test_unknown_lifecycle_status_is_never_reported_as_valid(client, database, cid):
    stored(database, cid)["status"] = "active"  # wrong case

    response = verify(client, cid)

    assert response.status_code == 500
    assert "VALID" not in response.text


# --------------------------------------------------------------------------- #
# 14-15. Public access and response shape
# --------------------------------------------------------------------------- #
def test_endpoint_is_public_and_needs_no_authentication(client, cid):
    response = verify(client, cid)  # no Authorization header at all

    assert response.status_code == 200
    assert "security" not in app.openapi()["paths"][VERIFY_PATH]["get"]


def test_authorization_header_is_ignored_not_validated(client, cid):
    response = verify(client, cid, headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 200
    assert response.json()["status"] == "VALID"


def test_every_outcome_has_exactly_five_fields_and_no_student_information(client, repository, database, cid):
    responses = [verify(client, cid)]  # VALID

    asyncio.run(repository.revoke_certificate(cid))
    responses.append(verify(client, cid))  # REVOKED

    stored(database, cid)["certificate_data"]["student_name"] = "Mallory"
    responses.append(verify(client, cid))  # INVALID

    responses.append(verify(client, "CERT-" + "1" * 32))  # NOT_FOUND

    stored(database, cid)["signature_metadata"]["key_id"] = "old"
    responses.append(verify(client, cid))  # UNVERIFIABLE (key id)

    assert [r.status_code for r in responses] == [200, 200, 200, 404, 503]
    assert [r.json()["status"] for r in responses] == [
        "VALID", "REVOKED", "INVALID", "NOT_FOUND", "UNVERIFIABLE",
    ]
    for response in responses:
        assert_five_fields_only(response)


def test_results_are_not_cacheable(client, cid):
    for target in (cid, "CERT-" + "2" * 32):  # 200 and 404
        assert verify(client, target).headers["cache-control"] == "no-store"


# --------------------------------------------------------------------------- #
# Integration with the existing application
# --------------------------------------------------------------------------- #
def test_verification_route_is_registered_next_to_the_existing_certificate_routes():
    paths = app.openapi()["paths"]

    assert VERIFY_PATH in paths
    assert "/certificates/{certificate_id}" in paths  # M5 retrieval is untouched
    assert "/certificates" in paths  # M5 issuance is untouched


def test_verification_does_not_shadow_certificate_retrieval_route(client, cid):
    """``/certificates/verify/<id>`` must resolve to verification, not ``/certificates/{id}``."""
    response = verify(client, cid)

    assert response.status_code == 200
    assert set(response.json()) == FIVE_FIELDS  # not an IssuedCertificateResponse


def test_verification_matches_certificate_issued_with_a_different_crypto_instance(
    client, key_files, cid
):
    """A fresh ``CryptoService`` over the same key files verifies the same certificate."""
    fresh = make_crypto(key_files.private, key_files.public)
    app.dependency_overrides[get_verification_crypto] = lambda: fresh

    assert verify(client, cid).json()["status"] == "VALID"
