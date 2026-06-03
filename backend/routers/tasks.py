"""
FlowStep AI — Tasks Router
Handles task ingestion, triage IA processing, cognitive load balancing, reordering, and status updates.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import MAX_TASKS_PER_SESSION
from middleware.jwt_auth import require_auth
from middleware.rate_limit import check_rate_limit
from models.database import SessionModel, TaskModel, get_db

logger = logging.getLogger("flowstep.tasks")
router = APIRouter(prefix="/api/v1", tags=["tasks"])


# Map Notion Kanban statuses (English) to the local SQLite status vocabulary.
_NOTION_TO_LOCAL_STATUS = {
    "Backlog": "pendiente",
    "To Do": "pendiente",
    "In Progress": "activa",
    "En Revisión": "activa",
    "Done": "completada",
}


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------
class TriageRequest(BaseModel):
    raw_tasks: list[str] = Field(..., min_length=1, max_length=MAX_TASKS_PER_SESSION)

    @field_validator("raw_tasks")
    @classmethod
    def _no_empty_tasks(cls, value: list[str]) -> list[str]:
        cleaned = [t.strip() for t in value if t and t.strip()]
        if not cleaned:
            raise ValueError("raw_tasks must contain at least one non-empty task")
        return cleaned


class TaskResponse(BaseModel):
    id: str
    session_id: str
    raw_input: str
    title: str
    urgency: str
    effort: str
    tipo: str
    order_index: int
    status: str
    expected_path: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TriageResponse(BaseModel):
    tasks: list[TaskResponse]
    tiempo_total_estimado_min: int
    advertencia: Optional[str] = None


class StatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(pendiente|activa|completada|pospuesta|bloqueada)$")
    notes: Optional[str] = None


class ReorderRequest(BaseModel):
    new_index: int = Field(..., ge=1)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/session/{session_id}/tasks", response_model=TriageResponse)
async def create_session_tasks(
    session_id: str,
    payload: TriageRequest,
    request: Request,
    db: Session = Depends(get_db),
    auth: dict = Depends(check_rate_limit),
) -> dict:
    """
    Ingest raw tasks, process them through the Notion Agent Manager (Organizador),
    and persist them in both Notion and SQLite (locally) for synchronization.

    SQLite is rebuilt from the authoritative Notion board for this session in a
    single transaction, so a triage failure never leaves the local DB empty and
    re-running triage keeps both stores in sync.
    """
    # 1. Verify session exists and belongs to this JWT token
    if auth.get("session_id") != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session ID does not match auth token",
        )

    db_session = db.scalar(select(SessionModel).where(SessionModel.id == session_id))
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # 2. Invoke Agent Manager for Triage Analysis & Notion Creation
    #    (Notion is the source of truth — nothing is deleted locally yet.)
    manager = request.app.state.agent_manager
    try:
        result = await manager.process_new_tasks(payload.raw_tasks, session_id)
    except Exception as exc:
        logger.error("Notion Agent Manager triage error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to analyze and save tasks via Agent Manager",
        ) from exc

    tiempo_total_estimado_min = result.get("tiempo_total_estimado_min", 60)
    triage_warning = result.get("advertencia")

    # 3. Re-read the full board for this session from Notion so SQLite mirrors it
    try:
        board_tasks = await manager.notion_client.query_tasks(session_id=session_id)
    except Exception as exc:
        logger.error("Failed to read Notion board after triage: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to read tasks from Notion after triage",
        ) from exc

    # 4. Rebuild SQLite atomically: delete + insert in a single transaction so a
    #    failure rolls back cleanly without losing the previous task set.
    processed_tasks: list[TaskModel] = []
    try:
        db.query(TaskModel).filter(TaskModel.session_id == session_id).delete()

        for idx, nt in enumerate(board_tasks):
            local_status = _NOTION_TO_LOCAL_STATUS.get(nt.status, "pendiente")
            new_task = TaskModel(
                id=nt.page_id or str(uuid.uuid4()),
                session_id=session_id,
                raw_input=nt.name or "Tarea sin título",
                title=nt.name or "Tarea sin título",
                urgency=(nt.priority or "Media").lower(),
                effort=(nt.effort or "Medio").lower(),
                type=(nt.type or "Otro").lower(),
                order_index=nt.order or (idx + 1),
                status=local_status,
                expected_path=_infer_expected_path(nt.name or ""),
                started_at=None,
                completed_at=nt.last_edited_time if local_status == "completada" else None,
                notes=nt.notes,
            )
            db.add(new_task)
            processed_tasks.append(new_task)

        db_session.total_tasks = len(processed_tasks)
        db_session.completed = sum(
            1 for t in processed_tasks if t.status == "completada"
        )

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist tasks: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to persist tasks",
        ) from exc

    return {
        "tasks": processed_tasks,
        "tiempo_total_estimado_min": tiempo_total_estimado_min,
        "advertencia": triage_warning,
    }


def _infer_expected_path(title: str) -> Optional[str]:
    """Best-effort guess of a workspace file path from a task title."""
    text_lower = title.lower()
    if any(ext in text_lower for ext in [".py", ".js", ".html", ".css", "code", "código"]):
        if ".html" in text_lower:
            return "index.html"
        if ".css" in text_lower:
            return "src/index.css"
        return "src/app.py" if ".py" in text_lower else "src/index.js"
    if any(kwd in text_lower for kwd in ["crear archivo", "escribir archivo", "documento", "archivo", "txt", "readme", "markdown"]):
        return "README.md" if "readme" in text_lower else "documento.txt"
    return None


@router.put("/task/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    task_id: str,
    payload: StatusUpdateRequest,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_auth),
) -> TaskModel:
    """Update the status, timestamps, and notes of a specific task."""
    task = db.scalar(select(TaskModel).where(TaskModel.id == task_id))
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Security check: Ensure task belongs to the authenticated session
    if auth.get("session_id") != task.session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Task belongs to another session",
        )

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    old_status = task.status
    new_status = payload.status

    task.status = new_status
    if payload.notes is not None:
        task.notes = payload.notes

    # Update timestamps based on state transitions
    if new_status == "activa" and old_status != "activa":
        task.started_at = now_iso
    elif new_status == "completada" and old_status != "completada":
        task.completed_at = now_iso
    elif new_status != "completada" and old_status == "completada":
        task.completed_at = None

    # Recalculate and update the session's completed task count
    try:
        db.flush()  # Push updates to SQLite before counting
        completed_count = db.query(TaskModel).filter(
            TaskModel.session_id == task.session_id,
            TaskModel.status == "completada"
        ).count()

        db_session = db.scalar(select(SessionModel).where(SessionModel.id == task.session_id))
        if db_session:
            db_session.completed = completed_count

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to update task status: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to update task status",
        ) from exc

    return task


@router.put("/task/{task_id}/reorder", response_model=list[TaskResponse])
async def reorder_session_task(
    task_id: str,
    payload: ReorderRequest,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_auth),
) -> list[TaskModel]:
    """
    Reorders a task within its session to `new_index` (1-indexed),
    automatically adjusting all other tasks sequentially.
    """
    target_task = db.scalar(select(TaskModel).where(TaskModel.id == task_id))
    if not target_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    session_id = target_task.session_id
    if auth.get("session_id") != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Session mismatch",
        )

    # Fetch all tasks in the session, sorted by order_index
    tasks = db.scalars(
        select(TaskModel)
        .where(TaskModel.session_id == session_id)
        .order_by(TaskModel.order_index)
    ).all()

    total_tasks = len(tasks)
    new_index = min(payload.new_index, total_tasks)

    # Remove target task from the list and insert it at the new 0-indexed position
    tasks_list = [t for t in tasks if t.id != task_id]
    tasks_list.insert(new_index - 1, target_task)

    # Re-assign sequential 1-indexed order_index
    for idx, t in enumerate(tasks_list, start=1):
        t.order_index = idx

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to save reordered tasks: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to save reordered tasks",
        ) from exc

    return tasks_list


@router.get("/session/{session_id}", response_model=dict)
async def get_session_details(
    session_id: str,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_auth),
) -> dict:
    """Retrieve full details of a session, including its tasks sorted by order_index."""
    if auth.get("session_id") != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session ID mismatch",
        )

    db_session = db.scalar(select(SessionModel).where(SessionModel.id == session_id))
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    tasks = db.scalars(
        select(TaskModel)
        .where(TaskModel.session_id == session_id)
        .order_by(TaskModel.order_index)
    ).all()

    return {
        "session": db_session,
        "tasks": tasks
    }
