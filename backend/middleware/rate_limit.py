"""
FlowStep AI — Rate Limiting Middleware
Simple in-memory sliding window: 60 requests per minute per session_id.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, status

from middleware.jwt_auth import require_auth

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_REQUESTS = 60       # Maximum authenticated requests per window
WINDOW_SECONDS = 60     # Time window in seconds

# Anonymous session creation is far more sensitive (JWT farming / DoS)
MAX_SESSION_CREATIONS = 10   # Max new sessions per IP per window
SESSION_WINDOW_SECONDS = 60

# In-memory store: session_id → list of request timestamps
_request_log: dict[str, list[float]] = defaultdict(list)
# In-memory store: client_ip → list of session-creation timestamps
_session_creation_log: dict[str, list[float]] = defaultdict(list)


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


def check_session_creation_rate_limit(request: Request) -> None:
    """Throttle anonymous session creation by client IP.

    Unlike :func:`check_rate_limit` this does not require a JWT, so it can guard
    the public ``POST /auth/session`` endpoint against token farming / DoS.

    Raises
    ------
    HTTPException 429
        If the IP exceeded ``MAX_SESSION_CREATIONS`` in the last window.
    """
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    cutoff = now - SESSION_WINDOW_SECONDS

    _session_creation_log[client_ip] = [
        t for t in _session_creation_log[client_ip] if t > cutoff
    ]

    if len(_session_creation_log[client_ip]) >= MAX_SESSION_CREATIONS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Too many sessions created: max {MAX_SESSION_CREATIONS} per "
                f"{SESSION_WINDOW_SECONDS} seconds. Try again later."
            ),
        )

    _session_creation_log[client_ip].append(now)
