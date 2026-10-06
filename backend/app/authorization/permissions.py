"""Central role and permission definitions for Credence (M2).

Every module checks permissions through the definitions here; nobody else
should invent their own authorization rules.

Design notes
------------
* A user has exactly one role.
* Permissions follow least privilege: ADMIN manages users and roles but does
  NOT automatically get certificate issuing permissions.
* A missing role (user record created before roles existed) means STUDENT.
  A role that is present but unrecognised means NO permissions (deny).
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class Role(str, Enum):
    STUDENT = "STUDENT"
    ISSUER = "ISSUER"
    ADMIN = "ADMIN"


DEFAULT_ROLE = Role.STUDENT


class Permission(str, Enum):
    # Student
    PROFILE_READ_OWN = "profile:read_own"
    CERTIFICATE_VIEW_OWN = "certificate:view_own"
    # Issuer
    CERTIFICATE_CREATE = "certificate:create"
    CERTIFICATE_ISSUE = "certificate:issue"
    # Admin
    USER_LIST = "user:list"
    ISSUER_MANAGE = "issuer:manage"  # grant / revoke ISSUER
    ADMIN_MANAGE = "admin:manage"  # grant / revoke ADMIN


ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]] = MappingProxyType(
    {
        Role.STUDENT: frozenset(
            {Permission.PROFILE_READ_OWN, Permission.CERTIFICATE_VIEW_OWN}
        ),
        Role.ISSUER: frozenset(
            {
                Permission.PROFILE_READ_OWN,
                Permission.CERTIFICATE_CREATE,
                Permission.CERTIFICATE_ISSUE,
            }
        ),
        Role.ADMIN: frozenset(
            {
                Permission.PROFILE_READ_OWN,
                Permission.USER_LIST,
                Permission.ISSUER_MANAGE,
                Permission.ADMIN_MANAGE,
            }
        ),
    }
)


def parse_role(value: Any) -> Role | None:
    """Return the Role for an exact, valid value, otherwise None."""
    if isinstance(value, Role):
        return value
    if isinstance(value, str):
        try:
            return Role(value)
        except ValueError:
            return None
    return None


def role_of(user: Any) -> Role | None:
    """Resolve a user's role.

    * no ``role`` attribute at all  -> STUDENT (default for existing users)
    * valid role                    -> that role
    * present but invalid/unknown   -> None (no permissions)
    """
    if not hasattr(user, "role"):
        return DEFAULT_ROLE
    return parse_role(getattr(user, "role"))


def permissions_for_role(role: Role | None) -> frozenset[Permission]:
    if role is None:
        return frozenset()
    return ROLE_PERMISSIONS.get(role, frozenset())


def permissions_of(user: Any) -> frozenset[Permission]:
    return permissions_for_role(role_of(user))


def has_permission(user: Any, permission: Permission) -> bool:
    return permission in permissions_of(user)
