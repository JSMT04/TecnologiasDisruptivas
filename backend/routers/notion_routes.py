"""
FlowStep AI — Notion & Agent Routes
REST endpoints for Notion integration, task management, and agent orchestration.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.manager import AgentManager
from middleware.jwt_auth import require_auth
from models.database import get_db, TaskModel, MCPAuditLog
from notion.client import NotionClient
from notion.schemas import MoveTaskRequest, UpdateTaskRequest
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
            detail=f"Error al verificar la conexión con Notion: {exc}",
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
            detail=f"Error al crear las bases de datos: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Tasks — query from Notion
# ---------------------------------------------------------------------------
@router.get("/tasks")
async def list_tasks(
    session_id: Optional[str] = Query(None, description="Filtrar por ID de sesión"),
    task_status: Optional[str] = Query(
        None, alias="status", description="Filtrar por estado"
    ),
    notion: NotionClient = Depends(get_notion_client),
    db: Session = Depends(get_db),
    auth: dict = Depends(require_auth),
) -> dict:
    """Consultar tareas desde la base de datos de Notion."""
    try:
        tasks = await notion.query_tasks(
            session_id=session_id, status=task_status
        )
        
        # Merge expected_path and verificado from SQLite local DB
        path_map = {}
        verified_tasks = set()
        if session_id:
            local_tasks = db.scalars(
                select(TaskModel).where(TaskModel.session_id == session_id)
            ).all()
            path_map = {t.id: t.expected_path for t in local_tasks if t.expected_path}
            
            audits = db.scalars(
                select(MCPAuditLog.task_id).where(
                    MCPAuditLog.session_id == session_id,
                    MCPAuditLog.result == "OK",
                )
            ).all()
            verified_tasks = {a for a in audits if a}
            
        tasks_data = []
        for t in tasks:
            td = t.model_dump()
            td["expected_path"] = path_map.get(t.page_id)
            td["verificado"] = t.page_id in verified_tasks
            tasks_data.append(td)
            
        return {
            "tasks": tasks_data,
            "total": len(tasks),
        }
    except Exception as exc:
        logger.error("Error al consultar tareas: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar tareas en Notion: {exc}",
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
            detail=f"Error al obtener el log de actividad: {exc}",
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
            detail=f"Error al obtener estado de los agentes: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Task Actions
# ---------------------------------------------------------------------------
@router.post("/tasks/{task_page_id}/execute")
async def execute_task(
    task_page_id: str,
    manager: AgentManager = Depends(get_agent_manager),
    auth: dict = Depends(require_auth),
) -> dict:
    """Ejecutar una tarea — generar propuesta de resolución vía el agente Ejecutor."""
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
            detail=f"Error al ejecutar la tarea: {exc}",
        ) from exc


@router.post("/tasks/{task_page_id}/complete")
async def complete_task(
    task_page_id: str,
    body: Optional[NotesBody] = None,
    manager: AgentManager = Depends(get_agent_manager),
    db: Session = Depends(get_db),
    auth: dict = Depends(require_auth),
) -> dict:
    """Marcar una tarea como completada (Done)."""
    # Guard: block completing if task has expected_path without verification
    local_task = db.scalar(
        select(TaskModel).where(TaskModel.id == task_page_id)
    )
    if local_task and local_task.expected_path:
        # Check if a successful verification exists in audit log
        audit = db.scalar(
            select(MCPAuditLog).where(
                MCPAuditLog.task_id == task_page_id,
                MCPAuditLog.result == "OK",
            )
        )
        if not audit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No se puede completar: la tarea requiere verificación "
                    "de archivo local. Usa el botón 🔍 Verificar primero."
                ),
            )
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
            detail=f"Error al completar la tarea: {exc}",
        ) from exc


@router.post("/tasks/{task_page_id}/review")
async def review_task(
    task_page_id: str,
    body: Optional[NotesBody] = None,
    manager: AgentManager = Depends(get_agent_manager),
    auth: dict = Depends(require_auth),
) -> dict:
    """Solicitar revisión para una tarea (En Revisión)."""
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
            detail=f"Error al solicitar revisión: {exc}",
        ) from exc


@router.post("/tasks/{task_page_id}/move")
async def move_task(
    task_page_id: str,
    body: MoveTaskRequest,
    notion: NotionClient = Depends(get_notion_client),
    db: Session = Depends(get_db),
    auth: dict = Depends(require_auth),
) -> dict:
    """Mover una tarea a un nuevo estado (columna del Kanban)."""
    # Guard: block moving to Done if task has expected_path without verification
    if body.status == "Done":
        local_task = db.scalar(
            select(TaskModel).where(TaskModel.id == task_page_id)
        )
        if local_task and local_task.expected_path:
            # Check if a successful verification exists in audit log
            audit = db.scalar(
                select(MCPAuditLog).where(
                    MCPAuditLog.task_id == task_page_id,
                    MCPAuditLog.result == "OK",
                )
            )
            if not audit:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "No se puede mover a Done: la tarea requiere verificación "
                        "de archivo local. Usa el botón 🔍 Verificar primero."
                    ),
                )

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
            detail=f"Error al mover la tarea: {exc}",
        ) from exc


class VerifyResponse(BaseModel):
    verificado: bool
    detalle: str
    timestamp: str


async def update_notion_task_notes_async(
    notion_client: NotionClient,
    task_page_id: str,
    existing_notes: Optional[str],
    expected_path: str,
    syntax_detail: str,
):
    try:
        time_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        verification_label = (
            f"\n\n[MCP] Verificación de archivo local exitosa ({time_str})\n"
            f"- Archivo: {expected_path}\n"
            f"- Detalle: {syntax_detail}"
        )
        updated_notes = (
            f"{existing_notes}{verification_label}"
            if existing_notes
            else verification_label
        )
        await notion_client.update_task(
            task_page_id, UpdateTaskRequest(notes=updated_notes)
        )
    except Exception as e:
        logger.error("Error al actualizar notas de Notion en background: %s", e)


@router.post("/tasks/{task_page_id}/verify", response_model=VerifyResponse)
async def verify_task_file(
    task_page_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    notion: NotionClient = Depends(get_notion_client),
    auth: dict = Depends(require_auth),
) -> dict:
    """Verificar si el archivo esperado para la tarea cumple con los criterios locales."""
    import ast

    # 1. Fetch task from local SQLite to get expected_path
    task = db.scalar(select(TaskModel).where(TaskModel.id == task_page_id))
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarea no encontrada en la base de datos local.",
        )

    expected_path = task.expected_path
    if not expected_path:
        return {
            "verificado": True,
            "detalle": "Esta tarea no requiere verificación de archivos locales.",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    # Resolve path inside the container workspace — search multiple bases
    search_bases = ["/app", "/app/project", "/app/data", "/app/desktop"]
    resolved_path = None
    for base in search_bases:
        candidate = os.path.abspath(os.path.join(base, expected_path))
        if os.path.exists(candidate):
            resolved_path = candidate
            break
    if resolved_path is None:
        resolved_path = os.path.abspath(os.path.join(search_bases[0], expected_path))

    # Audit log entry helper
    def log_audit(operation: str, result: str, detail: str = ""):
        audit = MCPAuditLog(
            session_id=task.session_id,
            task_id=task.id,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            operation=operation,
            path=resolved_path,
            result=result,
            detail=detail,
        )
        db.add(audit)
        try:
            db.commit()
        except Exception as e:
            logger.error("Error al escribir log de auditoría MCP: %s", e)
            db.rollback()

    # Check path allowance
    allow_list = os.getenv("MCP_ALLOW_LIST", "").strip()
    allowed = False
    if not allow_list:
        allowed = resolved_path.startswith(os.path.abspath(search_bases[0]))
    else:
        allowed_dirs = [os.path.abspath(d.strip()) for d in allow_list.split(",") if d.strip()]
        for d in allowed_dirs:
            if resolved_path.startswith(d):
                allowed = True
                break

    if not allowed:
        log_audit("READ", "DENIED", f"Acceso denegado a la ruta: {resolved_path}")
        return {
            "verificado": False,
            "detalle": f"Acceso denegado: el archivo '{expected_path}' no pertenece a una ruta permitida.",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    # Verify existence
    if not os.path.exists(resolved_path):
        log_audit("READ", "NOT_FOUND", f"Archivo no encontrado: {resolved_path}")
        return {
            "verificado": False,
            "detalle": f"El archivo esperado '{expected_path}' no existe en el sistema.",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    # Verify content (no_vacío)
    size = os.path.getsize(resolved_path)
    if size == 0:
        log_audit("READ", "OK", f"Archivo vacío: {resolved_path}")
        return {
            "verificado": False,
            "detalle": f"El archivo '{expected_path}' existe pero está vacío (0 bytes).",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    # Verify syntax for code
    ext = os.path.splitext(resolved_path)[1].lower()
    syntax_ok = True
    syntax_detail = "El archivo existe y contiene datos."

    if ext == ".py":
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                ast.parse(f.read())
            syntax_detail = "El archivo Python compila correctamente y no tiene errores de sintaxis."
        except SyntaxError as e:
            syntax_ok = False
            syntax_detail = f"Error de sintaxis Python: {e.msg} en línea {e.lineno}"
        except Exception as e:
            syntax_ok = False
            syntax_detail = f"Error leyendo archivo Python: {e}"
    elif ext == ".json":
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                json.load(f)
            syntax_detail = "El archivo JSON es parseable y válido."
        except json.JSONDecodeError as e:
            syntax_ok = False
            syntax_detail = f"Error de sintaxis JSON: {e.msg} en línea {e.lineno}"
        except Exception as e:
            syntax_ok = False
            syntax_detail = f"Error leyendo archivo JSON: {e}"

    if not syntax_ok:
        log_audit("READ", "ERROR", f"Error de validación sintáctica: {syntax_detail}")
        return {
            "verificado": False,
            "detalle": syntax_detail,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    # Everything is fine!
    log_audit("READ", "OK", f"Verificación exitosa: {syntax_detail}")

    # Log in Notion in the background to avoid blocking the response
    background_tasks.add_task(
        update_notion_task_notes_async,
        notion,
        task_page_id,
        task.notes or "",
        expected_path,
        syntax_detail,
    )

    return {
        "verificado": True,
        "detalle": f"¡Verificación exitosa! {syntax_detail}",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
