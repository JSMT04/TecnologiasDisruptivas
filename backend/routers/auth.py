"""
FlowStep AI — Authentication Router
Handles session creation and JWT token issuance.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models.database import SessionModel, get_db

router = APIRouter(prefix="/api/v1", tags=["auth"])

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
SESSION_TIMEOUT_MINUTES: int = int(os.getenv("SESSION_TIMEOUT_MINUTES", "480"))


@router.post("/auth/session")
async def create_session(db: Session = Depends(get_db)) -> dict:
    """
    Create a new work session.

    Returns a signed JWT containing the session_id and its expiration.
    Also persists the session record in SQLite.
    """
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
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate token: {exc}",
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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to persist session: {exc}",
        ) from exc

    return {
        "token": token,
        "session_id": session_id,
        "expires_at": expires_at.isoformat(),
    }
