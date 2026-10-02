"""M1 request/response models and public user representation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..database.models.user import User


class GoogleLoginRequest(BaseModel):
    """Body of POST /auth/google. Only the Google ID token is accepted;
    nothing else from the client is trusted or used to build the user."""

    model_config = ConfigDict(extra="forbid")

    id_token: str = Field(min_length=1, max_length=8192)


class UserPublic(BaseModel):
    """Public representation of a Credence user (never includes password_hash)."""

    id: UUID
    email: str
    is_active: bool
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserPublic":
        return cls(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at,
        )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class ErrorResponse(BaseModel):
    detail: str