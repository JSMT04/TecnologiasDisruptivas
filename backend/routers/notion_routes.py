"""
FlowStep AI — Notion & Agent Routes
REST endpoints for Notion integration, task management, and agent orchestration.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from agents.manager import AgentManager
from middleware.jwt_auth import require_auth
from notion.client import NotionClient
from notion.schemas import MoveTaskRequest
from notion.setup_databases import run_setup

logger = logging.getLogger("flowstep.routes.notion")

router = APIRouter(prefix="/api/v1/notion", tags=["notion"])


# ---------------------------------------------------------------------------
# Dependencies — retrieve singletons from app.state
# ---------------------------------------------------------------------------
def get_notion_client(request: Request) -> NotionClient:
    """FastAPI dependency: return the global NotionClient."""
    client = getattr(request.app.state, "notion_client", None)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El cliente de Notion no está inicializado.",
        )
    return client


def get_agent_manager(request: Request) -> AgentManager:
    """FastAPI dependency: return the global AgentManager."""
    manager = getattr(request.app.state, "agent_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El sistema de agentes no está inicializado.",
        )
    return manager


async def _verify_task_ownership(
    notion: NotionClient, task_page_id: str, session_id: str
) -> None:
    """Ensure the Notion task belongs to the authenticated session.

    Prevents IDOR: a user must not execute/modify tasks from another session.
    Raises 404 if the task does not exist and 403 if it belongs elsewhere.
    """
    try:
        task = await notion.get_task(task_page_id)
    except Exception as exc:
        logger.warning("Tarea no encontrada %s: %s", task_page_id, exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarea no encontrada.",
        ) from exc

    if task.session_id and task.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La tarea pertenece a otra sesión.",
        )


# ---------------------------------------------------------------------------
# Request/Response schemas for routes
# ---------------------------------------------------------------------------
class SetupRequest(BaseModel):
    """Body for the Notion database setup endpoint."""
    parent_page_id: str = Field(..., min_length=1)


class NotesBody(BaseModel):
    """Optional notes payload."""
    notes: str = ""


# ---------------------------------------------------------------------------
# Health — no auth required
# ---------------------------------------------------------------------------
@router.get("/health")
async def notion_health(
    notion: NotionClient = Depends(get_notion_client),
) -> dict:
    """Verificar la conectividad con la API de Notion."""
    try:
        result = await notion.health_check()
        return result
    except Exception as exc:
        logger.error("Error en health check de Notion: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al verificar la conexión con Notion.",
        ) from exc


# ---------------------------------------------------------------------------
# Setup — creates the Notion databases
# ---------------------------------------------------------------------------
@router.post("/setup")
async def notion_setup(
    payload: SetupRequest,
    auth: dict = Depends(require_auth),
) -> dict:
    """Crear las bases de datos de Tasks y Agent Log en Notion.

    Requiere un ``parent_page_id`` válido donde se crearán las DBs.
    """
    token = os.getenv("NOTION_API_TOKEN", "")
    if not token or "PENDIENTE" in token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "NOTION_API_TOKEN no está configurado o contiene PENDIENTE. "
                "Configura un token válido de Notion antes de ejecutar el setup."
            ),
        )

    try:
        result = await run_setup(token, payload.parent_page_id)
        return {
            "mensaje": "Bases de datos creadas exitosamente en Notion.",
            **result,
        }
    except Exception as exc:
        logger.error("Error en setup de Notion: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear las bases de datos en Notion.",
        ) from exc


# ---------------------------------------------------------------------------
# Tasks — query from Notion
# ---------------------------------------------------------------------------
@router.get("/tasks")
async def list_tasks(
    task_status: Optional[str] = Query(
        None, alias="status", description="Filtrar por estado"
    ),
    notion: NotionClient = Depends(get_notion_client),
    auth: dict = Depends(require_auth),
) -> dict:
    """Consultar tareas desde la base de datos de Notion.

    El ``session_id`` se toma siempre del token autenticado para evitar que un
    usuario consulte tareas de otra sesión (IDOR).
    """
    session_id = auth["session_id"]
    try:
        tasks = await notion.query_tasks(
            session_id=session_id, status=task_status
        )
        return {
            "tasks": [t.model_dump() for t in tasks],
            "total": len(tasks),
        }
    except Exception as exc:
        logger.error("Error al consultar tareas: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al consultar tareas en Notion.",
        ) from exc


# ---------------------------------------------------------------------------
# Agent Log — recent activity
# ---------------------------------------------------------------------------
@router.get("/agent-log")
async def agent_log(
    limit: int = Query(20, ge=1, le=100, description="Cantidad máxima de registros"),
    manager: AgentManager = Depends(get_agent_manager),
    auth: dict = Depends(require_auth),
) -> dict:
    """Obtener la actividad reciente de los agentes."""
    try:
        logs = await manager.get_agent_activity(limit=limit)
        return {"logs": logs, "total": len(logs)}
    except Exception as exc:
        logger.error("Error al consultar log de agentes: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el log de actividad.",
        ) from exc


# ---------------------------------------------------------------------------
# Agents Status
# ---------------------------------------------------------------------------
@router.get("/agents-status")
async def agents_status(
    manager: AgentManager = Depends(get_agent_manager),
    auth: dict = Depends(require_auth),
) -> dict:
    """Obtener el estado actual de los agentes."""
    try:
        return await manager.get_agents_status()
    except Exception as exc:
        logger.error("Error al obtener estado de agentes: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener estado de los agentes.",
        ) from exc


# ---------------------------------------------------------------------------
# Task Actions
# ---------------------------------------------------------------------------
@router.post("/tasks/{task_page_id}/execute")
async def execute_task(
    task_page_id: str,
    notion: NotionClient = Depends(get_notion_client),
    manager: AgentManager = Depends(get_agent_manager),
    auth: dict = Depends(require_auth),
) -> dict:
    """Ejecutar una tarea — generar propuesta de resolución vía el agente Ejecutor."""
    await _verify_task_ownership(notion, task_page_id, auth["session_id"])
    try:
        result = await manager.execute_task(task_page_id)
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"],
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error al ejecutar tarea %s: %s", task_page_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al ejecutar la tarea.",
        ) from exc


@router.post("/tasks/{task_page_id}/complete")
async def complete_task(
    task_page_id: str,
    body: Optional[NotesBody] = None,
    notion: NotionClient = Depends(get_notion_client),
    manager: AgentManager = Depends(get_agent_manager),
    auth: dict = Depends(require_auth),
) -> dict:
    """Marcar una tarea como completada (Done)."""
    await _verify_task_ownership(notion, task_page_id, auth["session_id"])
    notes = body.notes if body else ""
    try:
        result = await manager.complete_task(task_page_id, notes)
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"],
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error al completar tarea %s: %s", task_page_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al completar la tarea.",
        ) from exc


@router.post("/tasks/{task_page_id}/review")
async def review_task(
    task_page_id: str,
    body: Optional[NotesBody] = None,
    notion: NotionClient = Depends(get_notion_client),
    manager: AgentManager = Depends(get_agent_manager),
    auth: dict = Depends(require_auth),
) -> dict:
    """Solicitar revisión para una tarea (En Revisión)."""
    await _verify_task_ownership(notion, task_page_id, auth["session_id"])
    notes = body.notes if body else ""
    try:
        result = await manager.request_review(task_page_id, notes)
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"],
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Error al solicitar revisión para %s: %s", task_page_id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al solicitar revisión.",
        ) from exc


@router.post("/tasks/{task_page_id}/move")
async def move_task(
    task_page_id: str,
    body: MoveTaskRequest,
    notion: NotionClient = Depends(get_notion_client),
    auth: dict = Depends(require_auth),
) -> dict:
    """Mover una tarea a un nuevo estado (columna del Kanban)."""
    await _verify_task_ownership(notion, task_page_id, auth["session_id"])
    try:
        updated = await notion.move_task_status(task_page_id, body.status)
        return {"task": updated.model_dump(), "status": body.status}
    except Exception as exc:
        logger.error(
            "Error al mover tarea %s a '%s': %s",
            task_page_id,
            body.status,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al mover la tarea.",
        ) from exc
