"""M2 authorization endpoints. No business logic here; see service.py."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth.dependencies import get_current_user
from .dependencies import get_authorization_service, require_permission
from .permissions import Permission, Role
from .schemas import (
    ErrorResponse,
    MyAuthorization,
    RoleChangeRequest,
    UserRoleInfo,
    UserRoleList,
)
from .service import (
    AuthorizationService,
    AuthorizationUnavailableError,
    InvalidRoleChangeError,
    PermissionDeniedError,
    TargetUserNotFoundError,
)

router = APIRouter(prefix="/authorization", tags=["authorization"])

_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


@router.get("/me", response_model=MyAuthorization, responses=_ERRORS)
async def my_authorization(
    user: Annotated[Any, Depends(get_current_user)],
) -> MyAuthorization:
    """The caller's own role and permissions."""
    return MyAuthorization.from_user(user)


@router.get("/users", response_model=UserRoleList, responses=_ERRORS)
async def list_users(
    actor: Annotated[Any, Depends(require_permission(Permission.USER_LIST))],
    service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    role: Role | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> UserRoleList:
    """List users and their roles (admin only)."""
    try:
        users = await service.list_users(actor, role=role, skip=skip, limit=limit)
    except PermissionDeniedError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    except AuthorizationUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authorization service unavailable")
    return UserRoleList(
        users=[UserRoleInfo.from_user(u) for u in users], skip=skip, limit=limit
    )


@router.put(
    "/users/{user_id}/role",
    response_model=UserRoleInfo,
    responses={**_ERRORS, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def change_user_role(
    user_id: UUID,
    body: RoleChangeRequest,
    actor: Annotated[Any, Depends(get_current_user)],
    service: Annotated[AuthorizationService, Depends(get_authorization_service)],
) -> UserRoleInfo:
    """Grant or revoke a role. Admin only; rules are enforced in the service."""
    try:
        updated = await service.change_role(actor, user_id, body.role)
    except PermissionDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except TargetUserNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    except InvalidRoleChangeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except AuthorizationUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authorization service unavailable")
    return UserRoleInfo.from_user(updated)
