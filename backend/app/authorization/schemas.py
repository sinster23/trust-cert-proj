"""M2 request/response models."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .permissions import Role, permissions_of, role_of


class RoleChangeRequest(BaseModel):
    """Body of PUT /authorization/users/{user_id}/role."""

    model_config = ConfigDict(extra="forbid")

    role: Role


class MyAuthorization(BaseModel):
    role: Role | None
    permissions: list[str]

    @classmethod
    def from_user(cls, user: Any) -> "MyAuthorization":
        return cls(
            role=role_of(user),
            permissions=sorted(p.value for p in permissions_of(user)),
        )


class UserRoleInfo(BaseModel):
    id: UUID
    email: str
    role: Role | None
    is_active: bool

    @classmethod
    def from_user(cls, user: Any) -> "UserRoleInfo":
        return cls(
            id=user.id,
            email=user.email,
            role=role_of(user),
            is_active=user.is_active,
        )


class UserRoleList(BaseModel):
    users: list[UserRoleInfo]
    skip: int
    limit: int


class ErrorResponse(BaseModel):
    detail: str
