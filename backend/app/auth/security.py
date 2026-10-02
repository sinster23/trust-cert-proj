"""M1 authentication security operations.

Responsibilities:
- Authentication security configuration (read from environment variables)
- Backend validation of Google ID tokens
- Credence JWT creation and validation

Nothing here touches the database (M4) or decides permissions (M2).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

JWT_ALGORITHM = "HS256"
TOKEN_TYPE_ACCESS = "access"
GOOGLE_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})
MIN_JWT_SECRET_LENGTH = 32
GOOGLE_CLOCK_SKEW_SECONDS = 10

_REQUIRED_JWT_CLAIMS = ["sub", "iss", "aud", "exp", "iat", "typ", "jti"]


# --------------------------------------------------------------------------- #
# Errors (messages are safe to show to clients; details are never attached)
# --------------------------------------------------------------------------- #
class AuthError(Exception):
    """Base class for controlled authentication errors."""


class AuthConfigurationError(AuthError):
    """Authentication is not configured correctly on the server."""


class InvalidGoogleTokenError(AuthError):
    """The Google ID token is invalid, expired, or not acceptable."""


class InvalidTokenError(AuthError):
    """The Credence JWT is missing, malformed, expired, or invalid."""


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class AuthSettings:
    google_client_id: str
    google_allowed_domain: str
    jwt_secret: str
    jwt_issuer: str = "credence"
    jwt_audience: str = "credence-api"
    jwt_expire_minutes: int = 60


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise AuthConfigurationError(f"{name} is not configured")
    return value


def _load_settings() -> AuthSettings:
    secret = _required_env("JWT_SECRET")
    if len(secret) < MIN_JWT_SECRET_LENGTH:
        raise AuthConfigurationError("JWT_SECRET is too short")

    try:
        expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    except ValueError as exc:
        raise AuthConfigurationError("JWT_EXPIRE_MINUTES must be an integer") from exc
    if expire_minutes <= 0:
        raise AuthConfigurationError("JWT_EXPIRE_MINUTES must be positive")

    return AuthSettings(
        google_client_id=_required_env("GOOGLE_CLIENT_ID"),
        google_allowed_domain=_required_env("GOOGLE_ALLOWED_DOMAIN").lstrip("@").casefold(),
        jwt_secret=secret,
        jwt_issuer=os.getenv("JWT_ISSUER", "credence").strip() or "credence",
        jwt_audience=os.getenv("JWT_AUDIENCE", "credence-api").strip() or "credence-api",
        jwt_expire_minutes=expire_minutes,
    )


@lru_cache(maxsize=1)
def get_auth_settings() -> AuthSettings:
    """Load settings once. Call ``get_auth_settings.cache_clear()`` in tests."""
    return _load_settings()


# --------------------------------------------------------------------------- #
# Google identity validation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    hosted_domain: str


def verify_google_id_token(raw_token: str, settings: AuthSettings) -> GoogleIdentity:
    """Independently validate a Google ID token on the backend.

    Checks: signature (Google public certs), expiry, audience (our client id),
    issuer, verified email, and the institutional Workspace domain.

    This function is synchronous (it may fetch Google's certs over the network);
    the service layer runs it in a worker thread. Tests should mock it.
    """
    try:
        claims: dict[str, Any] = google_id_token.verify_oauth2_token(
            raw_token,
            google_requests.Request(),
            audience=settings.google_client_id,
            clock_skew_in_seconds=GOOGLE_CLOCK_SKEW_SECONDS,
        )
    except Exception as exc:  # google-auth raises ValueError/GoogleAuthError/network errors
        raise InvalidGoogleTokenError("Invalid Google credential") from exc

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise InvalidGoogleTokenError("Invalid Google credential")

    # Defence in depth: the library already checks aud, we confirm it explicitly.
    audience = claims.get("aud")
    if audience != settings.google_client_id:
        raise InvalidGoogleTokenError("Invalid Google credential")

    sub = claims.get("sub")
    email = claims.get("email")
    if not isinstance(sub, str) or not sub or not isinstance(email, str) or not email:
        raise InvalidGoogleTokenError("Invalid Google credential")

    # Must be the boolean True (not a truthy string).
    if claims.get("email_verified") is not True:
        raise InvalidGoogleTokenError("Invalid Google credential")

    # Institutional Workspace requirement: the signed `hd` claim AND the email domain.
    allowed = settings.google_allowed_domain
    hosted_domain = claims.get("hd")
    if not isinstance(hosted_domain, str) or hosted_domain.casefold() != allowed:
        raise InvalidGoogleTokenError("Invalid Google credential")
    if email.rpartition("@")[2].casefold() != allowed:
        raise InvalidGoogleTokenError("Invalid Google credential")

    return GoogleIdentity(
        sub=sub,
        email=email,
        email_verified=True,
        hosted_domain=hosted_domain.casefold(),
    )


# --------------------------------------------------------------------------- #
# Credence JWT
# --------------------------------------------------------------------------- #
def create_access_token(
    user_id: str,
    settings: AuthSettings,
    *,
    now: datetime | None = None,
) -> tuple[str, int]:
    """Create a signed Credence access JWT. Returns (token, expires_in_seconds)."""
    issued_at = now or datetime.now(timezone.utc)
    lifetime = timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": issued_at,
        "exp": issued_at + lifetime,
        "typ": TOKEN_TYPE_ACCESS,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str, settings: AuthSettings) -> dict[str, Any]:
    """Validate a Credence JWT and return its claims.

    Validates signature, expiry, issuer, audience, required claims and token type.
    Raises InvalidTokenError for anything wrong, without leaking the reason.
    """
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[JWT_ALGORITHM],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": _REQUIRED_JWT_CLAIMS},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Invalid token") from exc

    if claims.get("typ") != TOKEN_TYPE_ACCESS:
        raise InvalidTokenError("Invalid token")

    subject = claims.get("sub")
    if not isinstance(subject, str):
        raise InvalidTokenError("Invalid token")
    try:
        uuid.UUID(subject)
    except ValueError as exc:
        raise InvalidTokenError("Invalid token") from exc

    return claims