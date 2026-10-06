"""M2 — Authorization & RBAC module ("What is this user allowed to do?")."""

from .dependencies import require_permission, require_role
from .permissions import Permission, Role
from .router import router

__all__ = ["router", "require_permission", "require_role", "Permission", "Role"]
