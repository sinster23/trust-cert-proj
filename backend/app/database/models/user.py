from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    if not isinstance(email, str):
        raise ValueError("email must be a string")
    normalized = email.strip().casefold()
    if not normalized or "@" not in normalized:
        raise ValueError("email must be a valid non-empty address")
    return normalized


def normalize_google_sub(google_sub: str) -> str:
    """Google `sub` values are opaque and case-sensitive: only trim whitespace."""
    if not isinstance(google_sub, str):
        raise ValueError("google_sub must be a string")
    normalized = google_sub.strip()
    if not normalized:
        raise ValueError("google_sub must be a non-empty string")
    return normalized


@dataclass(frozen=True, slots=True)
class User:
    email: str
    google_sub: str
    id: UUID = field(default_factory=uuid4)
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "email", normalize_email(self.email))
        object.__setattr__(self, "google_sub", normalize_google_sub(self.google_sub))
        if not isinstance(self.id, UUID):
            raise ValueError("id must be a UUID")
        if not isinstance(self.is_active, bool):
            raise ValueError("is_active must be a boolean")
        for name in ("created_at", "updated_at"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
            object.__setattr__(self, name, value.astimezone(timezone.utc))

    def to_document(self) -> dict[str, Any]:
        return {
            "_id": str(self.id),
            "email": self.email,
            "google_sub": self.google_sub,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> "User":
        return cls(
            id=UUID(document["_id"]),
            email=document["email"],
            google_sub=document["google_sub"],
            is_active=document["is_active"],
            created_at=document["created_at"].replace(tzinfo=timezone.utc)
            if document["created_at"].tzinfo is None else document["created_at"],
            updated_at=document["updated_at"].replace(tzinfo=timezone.utc)
            if document["updated_at"].tzinfo is None else document["updated_at"],
        )