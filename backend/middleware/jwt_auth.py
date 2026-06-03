"""
FlowStep AI — JWT Authentication Middleware
FastAPI dependency that validates Bearer tokens on protected routes.
"""

from __future__ import annotations

import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
ALGORITHM = "HS256"

# FastAPI security scheme — extracts "Bearer <token>" from Authorization header
_bearer_scheme = HTTPBearer()


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """
    Validate the JWT token from the Authorization header.

    Returns
    -------
    dict
        Decoded JWT payload containing at least ``session_id``.

    Raises
    ------
    HTTPException 401
        If the token is missing, malformed, expired, or has an invalid signature.
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Ensure the payload contains a session_id
    if "session_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing session_id",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload
