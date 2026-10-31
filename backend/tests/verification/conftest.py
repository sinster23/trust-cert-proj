"""Shared fixtures for the verification tests.

Real implementations are used wherever practical:

* ``CryptoService`` with a temporary Ed25519 key pair (``tmp_path``);
* the real ``CertificateRepository`` over M4's in-memory ``FakeCollection``;
* the real ``CertificateService.issue_certificate`` to create signed records.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# M4's in-memory fake. ``tests/`` is not a package, so pytest imports the M4
# test module under the top-level name ``database``.
from database.test_certificate_repository import FakeDatabase

from app.certificates.service import CertificateService
from app.crypto import CryptoService
from app.crypto.keys import CryptoSettings, KeyManager
from app.database.repositories.certificate_repository import CertificateRepository

KEY_ID = "test-key-v1"

STUDENT = {
    "student_id": "CS2021-001",
    "student_name": "Asha Rao",
    "institution": "Example Institute of Technology",
    "degree": "Bachelor of Technology",
    "field_of_study": "Computer Science and Engineering",
    "graduation_date": "2025-06-15",
    "issue_date": "2025-07-01",
}


def write_key_pair(directory, name: str = "signing"):
    private_key = Ed25519PrivateKey.generate()
    private_path = directory / f"{name}-private.pem"
    public_path = directory / f"{name}-public.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return private_path, public_path


def make_crypto(private_path, public_path, key_id: str = KEY_ID) -> CryptoService:
    settings = CryptoSettings(
        private_key_path=str(private_path) if private_path else None,
        public_key_path=str(public_path) if public_path else None,
        key_id=key_id,
    )
    return CryptoService(KeyManager(settings))


@pytest.fixture
def key_files(tmp_path):
    private_path, public_path = write_key_pair(tmp_path)
    return SimpleNamespace(private=private_path, public=public_path)


@pytest.fixture
def crypto(key_files) -> CryptoService:
    return make_crypto(key_files.private, key_files.public)


@pytest.fixture
def database() -> FakeDatabase:
    return FakeDatabase()


@pytest.fixture
def repository(database) -> CertificateRepository:
    return CertificateRepository(database)


@pytest.fixture
def issue(crypto, repository):
    """Return an async function that issues a real signed certificate and returns its id."""

    async def _issue(**overrides) -> str:
        values = {**STUDENT, **overrides}
        signed = await CertificateService(crypto, repository).issue_certificate(**values)
        return signed.certificate.certificate_id

    return _issue
