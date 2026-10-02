"""M1 authentication workflow.

    Google identity -> validate -> find/create Credence user (via M4) -> issue JWT

Google `sub` -> Credence user mapping
-------------------------------------
The M4 user model has no field for the Google `sub`, and M4 must not be changed.
To keep `sub` (not email) as the permanent external identity key, the Credence
user id is derived deterministically from it:

    user_id = uuid5(CREDENCE_GOOGLE_NAMESPACE, "google:" + sub)

Lookups therefore use ``UserRepository.find_by_id``. The same Google account
always maps to the same Credence user, and an email change on the Google side
does not create a second user. If M4 later gains a dedicated `google_sub`
field, only `google_sub_to_user_id` and the lookup in `_get_or_create_user`
need to change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID, uuid5

from starlette.concurrency import run_in_threadpool

from ..database.exceptions import (
    DatabaseError,
    DatabaseUnavailableError,
    DuplicateDataError,
    UserNotFoundError,
)
from ..database.models.user import User
from ..database.repositories.user_repository import UserRepository
from .security import (
    AuthError,
    AuthSettings,
    GoogleIdentity,
    InvalidGoogleTokenError,
    create_access_token,
    verify_google_id_token,
)

logger = logging.getLogger(__name__)

# Fixed namespace for the sub -> user id mapping. NOT a secret, and must never
# change: changing it would map every Google account to a different user.
CREDENCE_GOOGLE_NAMESPACE = UUID("6f1c2d3e-4b5a-4c6d-8e7f-0a1b2c3d4e5f")

# M4's User requires a password_hash, but Google users have no password.
# This marker is not a valid hash for any password scheme, so password
# login can never succeed for these accounts.
UNUSABLE_PASSWORD_HASH = "!google-oauth-no-password"


class ServiceUnavailableError(AuthError):
    """A dependency (database) needed for authentication is unavailable."""


class AccountUnavailableError(AuthError):
    """The Credence account cannot be used (e.g. deactivated or not provisionable)."""


@dataclass(frozen=True, slots=True)
class AuthResult:
    access_token: str
    expires_in: int
    user: User


def google_sub_to_user_id(sub: str) -> UUID:
    """Deterministic, stable Credence user id for a Google `sub`."""
    return uuid5(CREDENCE_GOOGLE_NAMESPACE, f"google:{sub}")


class AuthService:
    def __init__(self, repository: UserRepository, settings: AuthSettings) -> None:
        self._repository = repository
        self._settings = settings

    async def authenticate_with_google(self, raw_google_token: str) -> AuthResult:
        identity = await self._validate_google_token(raw_google_token)
        user = await self._get_or_create_user(identity)
        if not user.is_active:
            raise AccountUnavailableError("Account is not available")
        token, expires_in = create_access_token(str(user.id), self._settings)
        return AuthResult(access_token=token, expires_in=expires_in, user=user)

    async def _validate_google_token(self, raw_token: str) -> GoogleIdentity:
        # google-auth is synchronous (may fetch certs); keep the event loop free.
        try:
            return await run_in_threadpool(verify_google_id_token, raw_token, self._settings)
        except InvalidGoogleTokenError:
            raise
        except AuthError:
            raise
        except Exception as exc:  # never leak internals
            logger.exception("Unexpected error while validating Google token")
            raise InvalidGoogleTokenError("Invalid Google credential") from exc

    async def _get_or_create_user(self, identity: GoogleIdentity) -> User:
        user_id = google_sub_to_user_id(identity.sub)
        try:
            return await self._repository.find_by_id(user_id)
        except UserNotFoundError:
            pass
        except DatabaseUnavailableError as exc:
            raise ServiceUnavailableError("Authentication service unavailable") from exc
        except DatabaseError as exc:
            logger.error("User lookup failed: %s", type(exc).__name__)
            raise ServiceUnavailableError("Authentication service unavailable") from exc

        # First login: the user is built ONLY from validated Google claims.
        try:
            new_user = User(
                id=user_id,
                email=identity.email,
                password_hash=UNUSABLE_PASSWORD_HASH,
            )
            return await self._repository.create_user(new_user)
        except DuplicateDataError:
            # Either a concurrent first login created this user (fine), or the
            # email already belongs to a different Credence user (not linked
            # automatically: email is not the identity key).
            try:
                return await self._repository.find_by_id(user_id)
            except UserNotFoundError as exc:
                logger.warning("Email already registered to a different Credence user")
                raise AccountUnavailableError("Account is not available") from exc
            except DatabaseError as exc:
                raise ServiceUnavailableError("Authentication service unavailable") from exc
        except ValueError as exc:
            raise InvalidGoogleTokenError("Invalid Google credential") from exc
        except DatabaseUnavailableError as exc:
            raise ServiceUnavailableError("Authentication service unavailable") from exc
        except DatabaseError as exc:
            logger.error("User creation failed: %s", type(exc).__name__)
            raise ServiceUnavailableError("Authentication service unavailable") from exc