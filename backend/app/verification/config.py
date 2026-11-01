from __future__ import annotations
import os

DEFAULT_RATE_LIMIT_PER_MINUTE = 30
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def show_details_enabled() -> bool:
    # Anything but 1/true/yes/on is off, so a typo fails closed.
    return os.getenv("VERIFICATION_SHOW_DETAILS", "").strip().lower() in _TRUE_VALUES


def rate_limit_per_minute() -> int:
    try:
        value = int(os.getenv("VERIFICATION_RATE_LIMIT_PER_MINUTE", "").strip())
    except ValueError:
        return DEFAULT_RATE_LIMIT_PER_MINUTE
    return value if value > 0 else DEFAULT_RATE_LIMIT_PER_MINUTE


def proxy_secret() -> str | None:
    return os.getenv("VERIFICATION_PROXY_SECRET", "").strip() or None