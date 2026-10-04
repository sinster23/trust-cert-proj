"""M1 authentication workflow.

    Google identity -> validate -> find/create Credence user (via M4) -> issue JWT

Identity
--------
Google's stable `sub` is the permanent external identity and is stored on the
M4 user as `google_sub` (unique index). Users are looked up with
``UserRepository.find_by_google_sub``; email is never the identity key.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

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


class ServiceUnavailableError(AuthError):
    """A dependency (database) needed for authentication is unavailable."""


class AccountUnavailableError(AuthError):
    """The Credence account cannot be used (e.g. deactivated or not provisionable)."""


@dataclass(frozen=True, slots=True)
class AuthResult:
    access_token: str
    expires_in: int
    user: User


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
        try:
            return await self._repository.find_by_google_sub(identity.sub)
        except UserNotFoundError:
            pass
        except DatabaseUnavailableError as exc:
            raise ServiceUnavailableError("Authentication service unavailable") from exc
        except DatabaseError as exc:
            logger.error("User lookup failed: %s", type(exc).__name__)
            raise ServiceUnavailableError("Authentication service unavailable") from exc

        # First login: the user is built ONLY from validated Google claims.
        try:
            new_user = User(email=identity.email, google_sub=identity.sub)
            return await self._repository.create_user(new_user)
        except DuplicateDataError:
            # Either a concurrent first login created this user (fine), or the
            # email already belongs to a different Credence user (not linked
            # automatically: email is not the identity key).
            try:
                return await self._repository.find_by_google_sub(identity.sub)
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