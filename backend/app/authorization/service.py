"""M2 authorization business logic: role assignment, revocation, decisions.

Persistence goes through an M4 repository. This module only depends on the
small ``RoleRepository`` interface below, so it never touches MongoDB.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID

from ..database.exceptions import DatabaseError, UserNotFoundError
from .permissions import Permission, Role, has_permission, role_of

logger = logging.getLogger(__name__)


class RoleRepository(Protocol):
    """What M2 needs from M4. ``find_by_id`` / ``find_by_email`` exist today;
    the other three are the M4 extension M2 depends on (see README section)."""

    async def find_by_id(self, user_id: UUID | str) -> Any: ...

    async def find_by_email(self, email: str) -> Any: ...

    async def update_role(self, user_id: UUID | str, role: str) -> Any: ...

    async def list_users(
        self, *, role: str | None = None, skip: int = 0, limit: int = 50
    ) -> list[Any]: ...

    async def count_by_role(self, role: str) -> int: ...


# --------------------------------------------------------------------------- #
# Errors (messages are safe to return to clients)
# --------------------------------------------------------------------------- #
class AuthorizationError(Exception):
    """Base class for controlled authorization errors."""


class PermissionDeniedError(AuthorizationError):
    """The acting user is not allowed to do this."""


class TargetUserNotFoundError(AuthorizationError):
    """The user being managed does not exist."""


class InvalidRoleChangeError(AuthorizationError):
    """The requested role change breaks a rule (no-op, last admin, ...)."""


class AuthorizationUnavailableError(AuthorizationError):
    """A dependency (database) needed for the decision is unavailable."""


class BootstrapNotAllowedError(AuthorizationError):
    """Initial admin provisioning is only allowed while no admin exists."""


class AuthorizationService:
    def __init__(self, repository: RoleRepository) -> None:
        self._repository = repository

    # -- decisions ---------------------------------------------------------- #
    @staticmethod
    def has_permission(user: Any, permission: Permission) -> bool:
        return has_permission(user, permission)

    @staticmethod
    def require_permission(user: Any, permission: Permission) -> None:
        if not has_permission(user, permission):
            raise PermissionDeniedError("Forbidden")

    # -- role management ---------------------------------------------------- #
    async def change_role(self, actor: Any, target_id: UUID, new_role: Role) -> Any:
        """Set ``target_id``'s role to ``new_role`` on behalf of ``actor``.

        Rules:
        * actor must hold ISSUER_MANAGE or ADMIN_MANAGE (checked before any
          lookup so unprivileged callers learn nothing about other users)
        * nobody can change their own role
        * touching ADMIN (granting or revoking) needs ADMIN_MANAGE, anything
          else needs ISSUER_MANAGE
        * no-op changes are rejected
        * privileged roles cannot be granted to deactivated users
        * the last remaining ADMIN cannot be demoted
        """
        if not (
            has_permission(actor, Permission.ISSUER_MANAGE)
            or has_permission(actor, Permission.ADMIN_MANAGE)
        ):
            raise PermissionDeniedError("Forbidden")

        if str(actor.id) == str(target_id):
            raise PermissionDeniedError("You cannot change your own role")

        try:
            target = await self._repository.find_by_id(target_id)
        except UserNotFoundError as exc:
            raise TargetUserNotFoundError("User not found") from exc
        except DatabaseError as exc:
            raise self._unavailable("user lookup", exc) from exc

        current = role_of(target)
        touches_admin = Role.ADMIN in (current, new_role) or current is None
        needed = Permission.ADMIN_MANAGE if touches_admin else Permission.ISSUER_MANAGE
        self.require_permission(actor, needed)

        if current == new_role:
            raise InvalidRoleChangeError("User already has this role")

        if new_role != Role.STUDENT and not getattr(target, "is_active", True):
            raise InvalidRoleChangeError("Cannot grant a privileged role to an inactive user")

        try:
            if current == Role.ADMIN:
                # NOTE: check-then-update is not atomic; M4 should make the
                # last-admin guarantee safe under concurrency.
                if await self._repository.count_by_role(Role.ADMIN.value) <= 1:
                    raise InvalidRoleChangeError("Cannot remove the last administrator")
            updated = await self._repository.update_role(target_id, new_role.value)
        except UserNotFoundError as exc:
            raise TargetUserNotFoundError("User not found") from exc
        except DatabaseError as exc:
            raise self._unavailable("role update", exc) from exc

        logger.info(
            "role_change actor=%s target=%s old=%s new=%s",
            actor.id,
            target_id,
            current.value if current else None,
            new_role.value,
        )
        return updated

    async def list_users(
        self, actor: Any, *, role: Role | None = None, skip: int = 0, limit: int = 50
    ) -> list[Any]:
        self.require_permission(actor, Permission.USER_LIST)
        try:
            return await self._repository.list_users(
                role=role.value if role else None, skip=skip, limit=limit
            )
        except DatabaseError as exc:
            raise self._unavailable("user listing", exc) from exc

    # -- bootstrap ---------------------------------------------------------- #
    async def bootstrap_admin(self, email: str) -> Any:
        """Promote an existing user to ADMIN, only while NO admin exists.

        Meant for a one-time, operator-run setup script, never for a public
        endpoint. The user must have logged in once (M1 creates the account).
        """
        try:
            if await self._repository.count_by_role(Role.ADMIN.value) > 0:
                raise BootstrapNotAllowedError("An administrator already exists")
            user = await self._repository.find_by_email(email)
            return await self._repository.update_role(user.id, Role.ADMIN.value)
        except UserNotFoundError as exc:
            raise TargetUserNotFoundError("User not found") from exc
        except DatabaseError as exc:
            raise self._unavailable("admin bootstrap", exc) from exc

    @staticmethod
    def _unavailable(action: str, exc: Exception) -> AuthorizationUnavailableError:
        logger.error("Authorization %s failed: %s", action, type(exc).__name__)
        return AuthorizationUnavailableError("Authorization service unavailable")
