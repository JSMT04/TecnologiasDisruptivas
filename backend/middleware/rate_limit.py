"""
FlowStep AI — Rate Limiting Middleware
Simple in-memory sliding window: 60 requests per minute per session_id.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Depends, HTTPException, status

from middleware.jwt_auth import require_auth

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_REQUESTS = 60       # Maximum requests allowed
WINDOW_SECONDS = 60     # Time window in seconds

# In-memory store: session_id → list of request timestamps
_request_log: dict[str, list[float]] = defaultdict(list)


def _cleanup(timestamps: list[float], now: float) -> list[float]:
    """Remove timestamps older than the current window."""
    cutoff = now - WINDOW_SECONDS
    return [t for t in timestamps if t > cutoff]


async def check_rate_limit(
    payload: dict = Depends(require_auth),
) -> dict:
    """
    FastAPI dependency — enforces per-session rate limiting.

    Must be used **after** ``require_auth`` so we have a valid session_id.
    Returns the JWT payload unchanged if the request is within limits.

    Raises
    ------
    HTTPException 429
        If the session has exceeded 60 requests in the last 60 seconds.
    """
    session_id: str = payload.get("session_id", "unknown")
    now = time.time()

    # Clean up stale entries
    _request_log[session_id] = _cleanup(_request_log[session_id], now)

    # Check limit
    if len(_request_log[session_id]) >= MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit exceeded: {MAX_REQUESTS} requests per "
                f"{WINDOW_SECONDS} seconds. Try again later."
            ),
        )

    # Record this request
    _request_log[session_id].append(now)

    return payload
