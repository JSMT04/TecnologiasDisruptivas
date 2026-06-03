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
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.openclaw_client import OpenClawClient
from middleware.jwt_auth import require_auth
from models.database import SessionModel, TaskModel, get_db

logger = logging.getLogger("flowstep.tasks")
router = APIRouter(prefix="/api/v1", tags=["tasks"])


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------
class TriageRequest(BaseModel):
    raw_tasks: list[str] = Field(..., min_items=1, max_items=20)


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

    class Config:
        from_attributes = True


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
    auth: dict = Depends(require_auth),
) -> dict:
    """
    Ingest raw tasks, process them through the Notion Agent Manager (Organizador),
    and persist them in both Notion and SQLite (locally) for synchronization.
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

    # Clean existing tasks for this session to allow re-running triage if needed
    try:
        db.query(TaskModel).filter(TaskModel.session_id == session_id).delete()
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear existing tasks: {exc}",
        ) from exc

    # 2. Invoke Agent Manager for Triage Analysis & Notion Creation
    manager = request.app.state.agent_manager
    try:
        result = await manager.process_new_tasks(payload.raw_tasks, session_id)
    except Exception as exc:
        logger.error(f"Notion Agent Manager triage error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to analyze and save tasks via Agent Manager",
        ) from exc

    # 3. Process tasks and write to local SQLite database
    created_tasks = result.get("tasks", [])
    tiempo_total_estimado_min = result.get("tiempo_total_estimado_min", 60)
    triage_warning = result.get("advertencia")

    processed_tasks = []
    for idx, nt in enumerate(created_tasks):
        urgency = nt.get("priority", "Media").lower()
        effort = nt.get("effort", "Medio").lower()
        tipo = nt.get("type", "Otro").lower()

        new_task = TaskModel(
            id=nt.get("page_id") or str(uuid.uuid4()),
            session_id=session_id,
            raw_input=payload.raw_tasks[idx] if idx < len(payload.raw_tasks) else nt.get("name", ""),
            title=nt.get("name", "Tarea sin título"),
            urgency=urgency,
            effort=effort,
            type=tipo,
            order_index=nt.get("order") or (idx + 1),
            status="pendiente",
            expected_path=None,
            started_at=None,
            completed_at=None,
            notes=nt.get("notes"),
        )

        # Infer expected path for local workspace verification features
        text_lower = new_task.title.lower()
        import re
        # Look for explicit path format (e.g. data/base.py, documento.txt, etc.)
        path_match = re.search(r'(?:data/|src/)?[\w\-./]+\.[a-zA-Z0-9]+', new_task.title)
        if path_match:
            new_task.expected_path = path_match.group(0)
        else:
            if any(ext in text_lower for ext in [".py", ".js", ".html", ".css", "code", "código"]):
                new_task.expected_path = "src/app.py" if ".py" in text_lower else "src/index.js"
                if ".html" in text_lower:
                    new_task.expected_path = "index.html"
                elif ".css" in text_lower:
                    new_task.expected_path = "src/index.css"
            elif any(kwd in text_lower for kwd in ["crear archivo", "escribir archivo", "documento", "archivo", "txt", "readme", "markdown"]):
                new_task.expected_path = "README.md" if "readme" in text_lower else "documento.txt"

        db.add(new_task)
        processed_tasks.append(new_task)

    # 4. Update session model stats
    db_session.total_tasks = len(processed_tasks)
    db_session.completed = 0

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to persist tasks: {exc}",
        ) from exc

    return {
        "tasks": processed_tasks,
        "tiempo_total_estimado_min": tiempo_total_estimado_min,
        "advertencia": triage_warning,
    }


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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update task status: {exc}",
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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save reordered tasks: {exc}",
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
