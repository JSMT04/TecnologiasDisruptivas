"""
FlowStep AI — Auto-Verifier Background Service
Runs every 5 seconds scanning tasks in "In Progress" that have an expected_path
but haven't been successfully verified yet. Automatically performs the file
verification (existence, non-empty, syntax) and logs the result.
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.database import MCPAuditLog, SessionLocal, TaskModel
from notion.client import NotionClient
from notion.schemas import UpdateTaskRequest

logger = logging.getLogger("flowstep.agents.auto_verifier")

AUTO_VERIFY_INTERVAL_SECONDS = 5
SEARCH_BASES = ["/app", "/app/project", "/app/data", "/app/desktop"]


def _get_unverified_in_progress_tasks(db: Session) -> list[TaskModel]:
    """Find all local tasks that have an expected_path but no successful audit."""
    # Get all tasks with expected_path
    tasks_with_path = db.scalars(
        select(TaskModel).where(
            TaskModel.expected_path.isnot(None),
            TaskModel.expected_path != "",
        )
    ).all()

    if not tasks_with_path:
        return []

    # Get task_ids that already have a successful verification
    verified_ids = set(
        db.scalars(
            select(MCPAuditLog.task_id).where(
                MCPAuditLog.result == "OK",
                MCPAuditLog.operation == "READ",
            )
        ).all()
    )

    # Return only unverified tasks
    return [t for t in tasks_with_path if t.id not in verified_ids]


def _verify_file(expected_path: str) -> dict:
    """Perform file verification: existence, non-empty, syntax.

    Searches across multiple base directories to find the file.
    Returns dict with keys: verificado (bool), detalle (str), result_code (str).
    """
    # Try to find the file in any of the search bases
    resolved_path = None
    for base in SEARCH_BASES:
        candidate = os.path.abspath(os.path.join(base, expected_path))
        if os.path.exists(candidate):
            resolved_path = candidate
            break

    # If not found in any base, use the first base for error reporting
    if resolved_path is None:
        resolved_path = os.path.abspath(os.path.join(SEARCH_BASES[0], expected_path))

    # Check path allowance
    allow_list = os.getenv("MCP_ALLOW_LIST", "").strip()
    allowed = False
    if not allow_list:
        allowed = resolved_path.startswith(os.path.abspath(BASE_DIR))
    else:
        allowed_dirs = [
            os.path.abspath(d.strip())
            for d in allow_list.split(",")
            if d.strip()
        ]
        for d in allowed_dirs:
            if resolved_path.startswith(d):
                allowed = True
                break

    if not allowed:
        return {
            "verificado": False,
            "detalle": f"Acceso denegado: '{expected_path}' no pertenece a una ruta permitida.",
            "result_code": "DENIED",
        }

    if not os.path.exists(resolved_path):
        return {
            "verificado": False,
            "detalle": f"El archivo '{expected_path}' no existe en el sistema.",
            "result_code": "NOT_FOUND",
        }

    size = os.path.getsize(resolved_path)
    if size == 0:
        return {
            "verificado": False,
            "detalle": f"El archivo '{expected_path}' existe pero está vacío (0 bytes).",
            "result_code": "EMPTY",
        }

    # Syntax check for code files
    ext = os.path.splitext(resolved_path)[1].lower()
    syntax_detail = "El archivo existe y contiene datos."

    if ext == ".py":
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                ast.parse(f.read())
            syntax_detail = "El archivo Python compila correctamente."
        except SyntaxError as e:
            return {
                "verificado": False,
                "detalle": f"Error de sintaxis Python: {e.msg} en línea {e.lineno}",
                "result_code": "ERROR",
            }
        except Exception as e:
            return {
                "verificado": False,
                "detalle": f"Error leyendo archivo Python: {e}",
                "result_code": "ERROR",
            }
    elif ext == ".json":
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                json.load(f)
            syntax_detail = "El archivo JSON es parseable y válido."
        except json.JSONDecodeError as e:
            return {
                "verificado": False,
                "detalle": f"Error de sintaxis JSON: {e.msg} en línea {e.lineno}",
                "result_code": "ERROR",
            }
        except Exception as e:
            return {
                "verificado": False,
                "detalle": f"Error leyendo archivo JSON: {e}",
                "result_code": "ERROR",
            }

    return {
        "verificado": True,
        "detalle": f"¡Auto-verificación exitosa! {syntax_detail}",
        "result_code": "OK",
    }


async def _run_auto_verify_cycle(notion_client: NotionClient) -> None:
    """Execute one cycle of auto-verification for unverified tasks."""
    db: Session = SessionLocal()
    try:
        unverified = _get_unverified_in_progress_tasks(db)
        if not unverified:
            return

        for task in unverified:
            expected_path = task.expected_path
            if not expected_path:
                continue

            result = _verify_file(expected_path)
            # Resolve path for audit logging (same multi-base logic)
            resolved_path = None
            for base in SEARCH_BASES:
                candidate = os.path.abspath(os.path.join(base, expected_path))
                if os.path.exists(candidate):
                    resolved_path = candidate
                    break
            if resolved_path is None:
                resolved_path = os.path.abspath(
                    os.path.join(SEARCH_BASES[0], expected_path)
                )

            # Write audit log entry
            audit = MCPAuditLog(
                session_id=task.session_id,
                task_id=task.id,
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
                operation="READ",
                path=resolved_path,
                result=result["result_code"],
                detail=f"[Auto-verificación] {result['detalle']}",
            )
            db.add(audit)

            if result["verificado"]:
                logger.info(
                    "✅ Auto-verificación exitosa para tarea '%s' (%s) — moviendo a Done",
                    task.title,
                    expected_path,
                )
                # Update Notion notes and move to Done
                try:
                    time_str = datetime.now(tz=timezone.utc).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    existing_notes = task.notes or ""
                    verification_label = (
                        f"\n\n[MCP Auto-Verify] Verificación automática exitosa ({time_str})\n"
                        f"- Archivo: {expected_path}\n"
                        f"- Detalle: {result['detalle']}\n"
                        f"- Acción: Tarea completada automáticamente ✅"
                    )
                    updated_notes = (
                        f"{existing_notes}{verification_label}"
                        if existing_notes
                        else verification_label
                    )
                    await notion_client.update_task(
                        task.id,
                        UpdateTaskRequest(notes=updated_notes),
                    )
                except Exception as e:
                    logger.error(
                        "Error al actualizar notas de Notion (auto-verify): %s",
                        e,
                    )

                # Auto-complete: move task to Done in Notion
                try:
                    await notion_client.move_task_status(task.id, "Done")
                    logger.info(
                        "✅ Tarea '%s' movida a Done automáticamente",
                        task.title,
                    )
                except Exception as e:
                    logger.error(
                        "Error al mover tarea '%s' a Done (auto-verify): %s",
                        task.title,
                        e,
                    )

        try:
            db.commit()
        except Exception as e:
            logger.error("Error al guardar auditoría de auto-verificación: %s", e)
            db.rollback()

    except Exception as exc:
        logger.error("Error en ciclo de auto-verificación: %s", exc)
    finally:
        db.close()


async def start_auto_verifier(notion_client: NotionClient) -> None:
    """Background loop that auto-verifies tasks every 5 seconds.

    This coroutine runs indefinitely until the application shuts down.
    """
    logger.info(
        "🔄 Auto-verificador iniciado (intervalo: %ds)",
        AUTO_VERIFY_INTERVAL_SECONDS,
    )
    while True:
        try:
            await _run_auto_verify_cycle(notion_client)
        except Exception as exc:
            logger.error("Error inesperado en auto-verificador: %s", exc)
        await asyncio.sleep(AUTO_VERIFY_INTERVAL_SECONDS)
