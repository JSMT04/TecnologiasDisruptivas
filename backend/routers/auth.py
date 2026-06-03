"""
FlowStep AI — Authentication Router
Handles session creation and JWT token issuance.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from config import JWT_ALGORITHM, JWT_SECRET, SESSION_TIMEOUT_MINUTES
from middleware.rate_limit import check_session_creation_rate_limit
from models.database import SessionModel, get_db

logger = logging.getLogger("flowstep.auth")

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/auth/session")
async def create_session(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Create a new work session.

    Returns a signed JWT containing the session_id and its expiration.
    Also persists the session record in SQLite.
    """
    # Throttle anonymous session creation per client IP to prevent JWT farming
    check_session_creation_rate_limit(request)

    # Generate identifiers & timestamps
    session_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(minutes=SESSION_TIMEOUT_MINUTES)

    # Build JWT payload
    payload = {
        "session_id": session_id,
        "exp": expires_at,
    }

    try:
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    except Exception as exc:
        logger.error("Failed to generate token: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate authentication token",
        ) from exc

    # Persist session in database
    new_session = SessionModel(
        id=session_id,
        created_at=now.isoformat(),
        ended_at=None,
        status="active",
        total_tasks=0,
        completed=0,
        report_path=None,
    )

    try:
        db.add(new_session)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist session: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to persist session",
        ) from exc

    return {
        "token": token,
        "session_id": session_id,
        "expires_at": expires_at.isoformat(),
    }
