"""Reusable authentication dependencies for other modules.

Other modules obtain the authenticated Credence user with:

    from app.auth.dependencies import get_current_user

    @router.get("/something")
    async def something(user: User = Depends(get_current_user)): ...

They never validate JWTs themselves.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..database.connection import DatabaseManager
from ..database.exceptions import DatabaseError, UserNotFoundError
from ..database.models.user import User
from ..database.repositories.user_repository import UserRepository
from .security import (
    AuthConfigurationError,
    AuthSettings,
    InvalidTokenError,
    decode_access_token,
    get_auth_settings,
)
from .service import AuthService

logger = logging.getLogger(__name__)

# M4's DatabaseManager is expected on `app.state` (see M4 `get_database`).
# The integration lead's main.py may use any of these attribute names.
DATABASE_MANAGER_STATE_ATTRS = ("db_manager", "database_manager", "database", "db")

_bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication service unavailable",
    )


def get_settings() -> AuthSettings:
    try:
        return get_auth_settings()
    except AuthConfigurationError:
        logger.error("Authentication is not configured correctly")
        raise _unavailable()


def get_user_repository(request: Request) -> UserRepository:
    """Build an M4 UserRepository from the shared DatabaseManager on app.state."""
    for attr in DATABASE_MANAGER_STATE_ATTRS:
        manager = getattr(request.app.state, attr, None)
        if isinstance(manager, DatabaseManager):
            try:
                return UserRepository(manager.get_database())
            except DatabaseError:
                raise _unavailable()
    logger.error("DatabaseManager not found on app.state")
    raise _unavailable()


def get_auth_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[AuthSettings, Depends(get_settings)],
) -> AuthService:
    return AuthService(repository, settings)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[AuthSettings, Depends(get_settings)],
) -> User:
    """Return the authenticated, active Credence user or raise 401/503."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _unauthorized()

    try:
        claims = decode_access_token(credentials.credentials, settings)
    except InvalidTokenError:
        raise _unauthorized()

    try:
        user = await repository.find_by_id(claims["sub"])
    except UserNotFoundError:
        raise _unauthorized()
    except DatabaseError:
        raise _unavailable()

    if not user.is_active:
        raise _unauthorized()
    return user