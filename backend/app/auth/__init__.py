"""M1 — Authentication module (identity: "Who is this user?")."""

from .dependencies import get_current_user
from .router import router

__all__ = ["router", "get_current_user"]