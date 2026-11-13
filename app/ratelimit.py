"""Simple in-process rate limiting for authentication endpoints.

Good enough for a single-process deployment (uvicorn with one worker). If the
app is ever scaled to multiple workers or instances, switch the storage to
Redis or another shared backend.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class SlidingWindowLimiter:
    """Per-key sliding window: at most max_requests hits per window_seconds."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """Record one hit for key; raise 429 if the limit is exceeded."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please try again later.",
                )
            hits.append(now)


# 10 attempts per 5 minutes per IP is generous for a human and tight
# enough to blunt credential-stuffing and brute-force attempts.
_auth_limiter = SlidingWindowLimiter(max_requests=10, window_seconds=300)


def limit_auth(request: Request) -> None:
    """FastAPI dependency: rate-limit auth endpoints by client IP."""
    ip = request.client.host if request.client else "unknown"
    _auth_limiter.check(ip)
