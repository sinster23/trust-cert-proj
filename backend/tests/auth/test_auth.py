"""M1 authentication tests.

Google is mocked and MongoDB is replaced by an in-memory fake repository that
raises the same M4 exceptions. Run from backend/:

    python -m pytest tests/auth -v
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import security, service
from app.auth.dependencies import get_user_repository
from app.auth.router import router as auth_router
from app.auth.security import (
    AuthSettings,
    GoogleIdentity,
    InvalidGoogleTokenError,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    get_auth_settings,
    verify_google_id_token,
)
from app.auth.service import AccountUnavailableError, AuthService
from app.database.exceptions import (
    DuplicateDataError,
    InvalidDatabaseOperationError,
    UserNotFoundError,
)
from app.database.models.user import User

CLIENT_ID = "test-client-id.apps.googleusercontent.com"
DOMAIN = "example.edu"
SECRET = "x" * 48
_MISSING = object()


# --------------------------------------------------------------------------- #
# Helpers / fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def auth_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("GOOGLE_ALLOWED_DOMAIN", DOMAIN)
    monkeypatch.setenv("JWT_SECRET", SECRET)
    get_auth_settings.cache_clear()
    yield
    get_auth_settings.cache_clear()


@pytest.fixture
def settings() -> AuthSettings:
    return AuthSettings(
        google_client_id=CLIENT_ID,
        google_allowed_domain=DOMAIN,
        jwt_secret=SECRET,
    )


class FakeUserRepository:
    """In-memory stand-in for M4's UserRepository (same exceptions)."""

    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    async def find_by_id(self, user_id):
        try:
            key = str(user_id if isinstance(user_id, UUID) else UUID(user_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidDatabaseOperationError("User identifier is invalid") from exc
        if key not in self.users:
            raise UserNotFoundError("User was not found")
        return self.users[key]

    async def find_by_email(self, email):
        for user in self.users.values():
            if user.email == email.strip().casefold():
                return user
        raise UserNotFoundError("User was not found")

    async def find_by_google_sub(self, google_sub):
        if not isinstance(google_sub, str) or not google_sub.strip():
            raise InvalidDatabaseOperationError("Google account identifier is invalid")
        for user in self.users.values():
            if user.google_sub == google_sub.strip():
                return user
        raise UserNotFoundError("User was not found")

    async def create_user(self, user):
        if (
            str(user.id) in self.users
            or any(u.email == user.email for u in self.users.values())
            or any(u.google_sub == user.google_sub for u in self.users.values())
        ):
            raise DuplicateDataError("A user with this email or Google account already exists")
        self.users[str(user.id)] = user
        return user


@pytest.fixture
def repo() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def client(repo) -> TestClient:
    app = FastAPI()  # test-only app; the real one lives in app.main
    app.include_router(auth_router)
    app.dependency_overrides[get_user_repository] = lambda: repo
    return TestClient(app)


def google_claims(**overrides) -> dict:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1234567890",
        "email": f"student@{DOMAIN}",
        "email_verified": True,
        "hd": DOMAIN,
    }
    for key, value in overrides.items():
        if value is _MISSING:
            claims.pop(key, None)
        else:
            claims[key] = value
    return claims


def mock_google_library(monkeypatch, claims=None, error: Exception | None = None):
    def fake_verify(token, request, audience=None, clock_skew_in_seconds=0):
        if error is not None:
            raise error
        return claims

    monkeypatch.setattr(security.google_id_token, "verify_oauth2_token", fake_verify)


def mock_service_identity(monkeypatch, sub="1234567890", email=f"student@{DOMAIN}"):
    identity = GoogleIdentity(sub=sub, email=email, email_verified=True, hosted_domain=DOMAIN)
    monkeypatch.setattr(service, "verify_google_id_token", lambda token, settings: identity)


def forge_jwt(secret=SECRET, drop=(), algorithm="HS256", **overrides) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid.uuid4()),
        "iss": "credence",
        "aud": "credence-api",
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "typ": "access",
        "jti": uuid.uuid4().hex,
    }
    payload.update(overrides)
    for key in drop:
        payload.pop(key, None)
    return jwt.encode(payload, secret, algorithm=algorithm)


# --------------------------------------------------------------------------- #
# Google authentication
# --------------------------------------------------------------------------- #
class TestGoogleAuthentication:
    def test_valid_institutional_account(self, monkeypatch, settings):
        mock_google_library(monkeypatch, google_claims())
        identity = verify_google_id_token("tok", settings)
        assert identity.sub == "1234567890"
        assert identity.email == f"student@{DOMAIN}"

    def test_invalid_token(self, monkeypatch, settings):
        mock_google_library(monkeypatch, error=ValueError("Could not verify token signature"))
        with pytest.raises(InvalidGoogleTokenError):
            verify_google_id_token("garbage", settings)

    def test_expired_token(self, monkeypatch, settings):
        mock_google_library(monkeypatch, error=ValueError("Token expired"))
        with pytest.raises(InvalidGoogleTokenError):
            verify_google_id_token("tok", settings)

    def test_incorrect_audience(self, monkeypatch, settings):
        mock_google_library(monkeypatch, google_claims(aud="someone-elses-client-id"))
        with pytest.raises(InvalidGoogleTokenError):
            verify_google_id_token("tok", settings)

    @pytest.mark.parametrize("issuer", ["https://evil.example.com", "accounts.google.com.evil.com", _MISSING])
    def test_incorrect_issuer(self, monkeypatch, settings, issuer):
        mock_google_library(monkeypatch, google_claims(iss=issuer))
        with pytest.raises(InvalidGoogleTokenError):
            verify_google_id_token("tok", settings)

    @pytest.mark.parametrize("verified", [False, "true", _MISSING])
    def test_unverified_email(self, monkeypatch, settings, verified):
        mock_google_library(monkeypatch, google_claims(email_verified=verified))
        with pytest.raises(InvalidGoogleTokenError):
            verify_google_id_token("tok", settings)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"hd": "other.edu"},  # different Workspace
            {"hd": _MISSING, "email": "someone@gmail.com"},  # personal account
            {"email": "student@other.edu"},  # email domain mismatch
            {"email": "student@" + DOMAIN + ".evil.com"},  # look-alike domain
        ],
    )
    def test_non_institutional_account(self, monkeypatch, settings, overrides):
        mock_google_library(monkeypatch, google_claims(**overrides))
        with pytest.raises(InvalidGoogleTokenError):
            verify_google_id_token("tok", settings)

    def test_missing_sub_rejected(self, monkeypatch, settings):
        mock_google_library(monkeypatch, google_claims(sub=_MISSING))
        with pytest.raises(InvalidGoogleTokenError):
            verify_google_id_token("tok", settings)


# --------------------------------------------------------------------------- #
# User handling
# --------------------------------------------------------------------------- #
class TestUserHandling:
    def test_new_user_created_through_repository(self, monkeypatch, repo, settings):
        mock_service_identity(monkeypatch)
        result = asyncio.run(AuthService(repo, settings).authenticate_with_google("tok"))
        assert len(repo.users) == 1
        assert result.user.email == f"student@{DOMAIN}"
        assert result.user.google_sub == "1234567890"
        assert not hasattr(result.user, "password_hash")

    def test_existing_user_login_does_not_duplicate(self, monkeypatch, repo, settings):
        mock_service_identity(monkeypatch)
        svc = AuthService(repo, settings)
        first = asyncio.run(svc.authenticate_with_google("tok"))
        second = asyncio.run(svc.authenticate_with_google("tok"))
        assert first.user.id == second.user.id
        assert len(repo.users) == 1

    def test_concurrent_first_login_returns_the_user_created_by_the_other_request(
        self, monkeypatch, repo, settings
    ):
        mock_service_identity(monkeypatch)
        winner = User(email=f"student@{DOMAIN}", google_sub="1234567890")
        original_find = repo.find_by_google_sub
        calls = {"n": 0}

        async def racing_find(sub):
            calls["n"] += 1
            if calls["n"] == 1:
                raise UserNotFoundError("User was not found")
            return await original_find(sub)

        async def racing_create(user):
            repo.users[str(winner.id)] = winner  # the other request wins the race
            raise DuplicateDataError("duplicate")

        monkeypatch.setattr(repo, "find_by_google_sub", racing_find)
        monkeypatch.setattr(repo, "create_user", racing_create)
        result = asyncio.run(AuthService(repo, settings).authenticate_with_google("tok"))
        assert result.user.id == winner.id
        assert len(repo.users) == 1

    def test_sub_maps_to_same_user_even_if_email_changes(self, monkeypatch, repo, settings):
        svc = AuthService(repo, settings)
        mock_service_identity(monkeypatch, sub="sub-A", email=f"old@{DOMAIN}")
        first = asyncio.run(svc.authenticate_with_google("tok"))
        mock_service_identity(monkeypatch, sub="sub-A", email=f"new@{DOMAIN}")
        second = asyncio.run(svc.authenticate_with_google("tok"))
        assert first.user.id == second.user.id
        assert len(repo.users) == 1

    def test_different_subs_map_to_different_users(self, monkeypatch, repo, settings):
        svc = AuthService(repo, settings)
        mock_service_identity(monkeypatch, sub="sub-A", email=f"a@{DOMAIN}")
        a = asyncio.run(svc.authenticate_with_google("tok"))
        mock_service_identity(monkeypatch, sub="sub-B", email=f"b@{DOMAIN}")
        b = asyncio.run(svc.authenticate_with_google("tok"))
        assert a.user.id != b.user.id
        assert a.user.google_sub == "sub-A"
        assert b.user.google_sub == "sub-B"

    def test_email_owned_by_other_user_is_not_linked(self, monkeypatch, repo, settings):
        other = User(email=f"student@{DOMAIN}", google_sub="someone-elses-sub")
        repo.users[str(other.id)] = other
        mock_service_identity(monkeypatch, sub="brand-new-sub")
        with pytest.raises(AccountUnavailableError):
            asyncio.run(AuthService(repo, settings).authenticate_with_google("tok"))
        assert len(repo.users) == 1

    def test_inactive_user_cannot_login(self, monkeypatch, repo, settings):
        inactive = User(email=f"student@{DOMAIN}", google_sub="1234567890", is_active=False)
        repo.users[str(inactive.id)] = inactive
        mock_service_identity(monkeypatch)
        with pytest.raises(AccountUnavailableError):
            asyncio.run(AuthService(repo, settings).authenticate_with_google("tok"))


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
class TestJWT:
    def test_valid_jwt(self, settings):
        uid = str(uuid.uuid4())
        token, expires_in = create_access_token(uid, settings)
        claims = decode_access_token(token, settings)
        assert claims["sub"] == uid
        assert claims["iss"] == settings.jwt_issuer
        assert claims["aud"] == settings.jwt_audience
        assert claims["typ"] == "access"
        assert expires_in == settings.jwt_expire_minutes * 60

    def test_expired_jwt(self, settings):
        past = datetime.now(timezone.utc) - timedelta(hours=3)
        token, _ = create_access_token(str(uuid.uuid4()), settings, now=past)
        with pytest.raises(InvalidTokenError):
            decode_access_token(token, settings)

    def test_invalid_signature(self, settings):
        with pytest.raises(InvalidTokenError):
            decode_access_token(forge_jwt(secret="y" * 48), settings)

    @pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c", "a.b"])
    def test_malformed_jwt(self, settings, token):
        with pytest.raises(InvalidTokenError):
            decode_access_token(token, settings)

    def test_alg_none_rejected(self, settings):
        with pytest.raises(InvalidTokenError):
            decode_access_token(forge_jwt(secret=None, algorithm="none"), settings)

    @pytest.mark.parametrize("claim", ["sub", "iss", "aud", "exp", "iat", "typ", "jti"])
    def test_missing_required_claim(self, settings, claim):
        with pytest.raises(InvalidTokenError):
            decode_access_token(forge_jwt(drop=(claim,)), settings)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"iss": "someone-else"},
            {"aud": "another-api"},
            {"typ": "refresh"},
            {"sub": "not-a-uuid"},
        ],
    )
    def test_invalid_claim_values(self, settings, overrides):
        with pytest.raises(InvalidTokenError):
            decode_access_token(forge_jwt(**overrides), settings)


# --------------------------------------------------------------------------- #
# Authentication dependency + endpoints
# --------------------------------------------------------------------------- #
class TestDependencyAndEndpoints:
    def _login(self, client, monkeypatch):
        mock_service_identity(monkeypatch)
        response = client.post("/auth/google", json={"id_token": "tok"})
        assert response.status_code == 200, response.text
        return response.json()

    def test_login_returns_jwt_and_public_user(self, client, monkeypatch):
        body = self._login(client, monkeypatch)
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["user"]["email"] == f"student@{DOMAIN}"
        assert "password_hash" not in body["user"]

    def test_authenticated_request_returns_current_user(self, client, monkeypatch):
        body = self._login(client, monkeypatch)
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
        assert response.status_code == 200
        assert response.json()["id"] == body["user"]["id"]

    def test_missing_authentication_rejected(self, client):
        response = client.get("/auth/me")
        assert response.status_code == 401

    @pytest.mark.parametrize("header", ["Bearer garbage", "Basic abc", "Bearer "])
    def test_invalid_authentication_rejected(self, client, header):
        response = client.get("/auth/me", headers={"Authorization": header})
        assert response.status_code == 401

    def test_token_for_unknown_user_rejected(self, client):
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {forge_jwt()}"})
        assert response.status_code == 401

    def test_expired_token_rejected(self, client):
        token = forge_jwt(exp=datetime.now(timezone.utc) - timedelta(minutes=5))
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_inactive_user_token_rejected(self, client, repo):
        user = User(email=f"gone@{DOMAIN}", google_sub="sub-gone", is_active=False)
        repo.users[str(user.id)] = user
        token = forge_jwt(sub=str(user.id))
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_login_with_bad_google_token_is_generic_401(self, client, monkeypatch):
        def boom(token, settings):
            raise InvalidGoogleTokenError("internal detail that must not leak")

        monkeypatch.setattr(service, "verify_google_id_token", boom)
        response = client.post("/auth/google", json={"id_token": "tok"})
        assert response.status_code == 401
        assert "internal" not in response.text

    def test_login_rejects_extra_fields_and_empty_token(self, client):
        assert client.post("/auth/google", json={"id_token": ""}).status_code == 422
        assert client.post("/auth/google", json={"id_token": "t", "email": "x@y.z"}).status_code == 422

    def test_missing_configuration_returns_503(self, client, monkeypatch):
        monkeypatch.delenv("JWT_SECRET")
        get_auth_settings.cache_clear()
        response = client.post("/auth/google", json={"id_token": "tok"})
        assert response.status_code == 503