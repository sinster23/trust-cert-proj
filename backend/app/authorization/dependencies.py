"""Reusable authorization dependencies for protected routes.

    from app.authorization.dependencies import require_permission
    from app.authorization.permissions import Permission

    @router.post("/certificates")
    async def create(user = Depends(require_permission(Permission.CERTIFICATE_ISSUE))): ...

Authentication stays in M1 (``get_current_user``); this layer only decides
what the already-authenticated user may do. Decisions use the role stored in
the database (M1 reloads the user on every request), never a role in the JWT
or anything sent by the client.
"""

from __future__ import annotations

from typing import Annotated, Any, Callable

from fastapi import Depends, HTTPException, status

from ..auth.dependencies import get_current_user, get_user_repository
from ..database.repositories.user_repository import UserRepository
from .permissions import Permission, Role, has_permission, role_of
from .service import AuthorizationService


def forbidden() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def get_authorization_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthorizationService:
    return AuthorizationService(repository)


def require_permission(permission: Permission) -> Callable[..., Any]:
    """Dependency factory: authenticated AND holding ``permission``, else 401/403."""

    async def checker(user: Annotated[Any, Depends(get_current_user)]) -> Any:
        if not has_permission(user, permission):
            raise forbidden()
        return user

    return checker


def require_role(*roles: Role) -> Callable[..., Any]:
    """Dependency factory: authenticated AND having one of ``roles``, else 401/403."""

    allowed = frozenset(roles)

    async def checker(user: Annotated[Any, Depends(get_current_user)]) -> Any:
        if role_of(user) not in allowed:
            raise forbidden()
        return user

    return checker
