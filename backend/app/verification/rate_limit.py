from __future__ import annotations

import hmac, ipaddress, logging, math, threading, time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from . import config

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60.0
CLIENT_IP_HEADER = "x-credence-client-ip"
PROXY_SECRET_HEADER = "x-credence-proxy-secret"
RATE_LIMIT_DETAIL = "Too many verification requests. Please try again shortly."


class SlidingWindowRateLimiter:
    """In-memory: per process, resets on restart, not shared across instances."""

    def __init__(self, window_seconds: float = WINDOW_SECONDS,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._next_prune = clock() + window_seconds

    def hit(self, key: str, limit: int) -> int | None:
        """None if allowed, else seconds to wait (>= 1). Blocked hits are not counted."""
        now = self._clock()
        cutoff = now - self._window
        with self._lock:
            self._prune(now, cutoff)
            window = self._hits.setdefault(key, deque())
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= limit:
                return max(1, math.ceil(window[0] + self._window - now))
            window.append(now)
            return None

    def _prune(self, now: float, cutoff: float) -> None:
        if now < self._next_prune:
            return
        self._next_prune = now + self._window
        for key in [k for k, w in self._hits.items() if not w or w[-1] <= cutoff]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = SlidingWindowRateLimiter()


def _parse_ip(value: str | None):
    if not value:
        return None
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


def _bucket(address) -> str:
    if isinstance(address, ipaddress.IPv6Address):      # limit IPv6 per /64
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def resolve_client_key(request: Request) -> str:
    """Trust the forwarded IP ONLY if the shared secret matches. Never read X-Forwarded-For."""
    secret = config.proxy_secret()
    if secret is not None:
        supplied = request.headers.get(PROXY_SECRET_HEADER, "")
        if hmac.compare_digest(supplied.encode("utf-8"), secret.encode("utf-8")):
            forwarded = _parse_ip(request.headers.get(CLIENT_IP_HEADER))
            if forwarded is not None:
                return _bucket(forwarded)
    peer = request.client.host if request.client else "unknown"
    address = _parse_ip(peer)
    return _bucket(address) if address is not None else peer


async def enforce_rate_limit(request: Request) -> None:
    retry_after = rate_limiter.hit(resolve_client_key(request), config.rate_limit_per_minute())
    if retry_after is not None:
        logger.warning("Verification rate limit exceeded")   # no IP, no student data
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=RATE_LIMIT_DETAIL,
            headers={"Retry-After": str(retry_after), "Cache-Control": "no-store"},
        )