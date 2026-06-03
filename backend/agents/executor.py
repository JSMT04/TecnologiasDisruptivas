"""
FlowStep AI — Ejecutor Agent
Reads a task from Notion, generates a step-by-step resolution proposal,
and manages the task through its lifecycle (In Progress → En Revisión → Done).
"""

from __future__ import annotations

import logging
from typing import Optional

from agent.openclaw_client import OpenClawClient
from agents.base_agent import BaseAgent
from notion.client import NotionClient
from notion.schemas import UpdateTaskRequest

logger = logging.getLogger("flowstep.agents.executor")


class ExecutorAgent(BaseAgent):
    """Agent that executes (proposes resolution for) individual tasks."""

    name: str = "Ejecutor"

    def __init__(
        self,
        notion_client: NotionClient,
        openclaw_client: OpenClawClient,
    ) -> None:
        super().__init__(notion_client, openclaw_client)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    async def run(self, input_data: dict) -> dict:
        """Generate a resolution proposal for the task.

        Parameters
        ----------
        input_data:
            Must contain ``task_page_id`` (str).

        Returns
        -------
        dict
            ``{"task": {...}, "proposal": "..."}``
        """
        task_page_id: str = input_data.get("task_page_id", "")
        if not task_page_id:
            return {"error": "No se proporcionó task_page_id"}

        # 1. Read the task from Notion
        try:
            task = await self.notion_client.get_task(task_page_id)
        except Exception as exc:
            logger.error("Error al leer tarea %s: %s", task_page_id, exc)
            await self.log_action(
                action="Error leyendo tarea",
                task_page_id=task_page_id,
                status="Error",
                details=str(exc),
            )
            return {"error": f"No se pudo leer la tarea: {exc}"}

        # 2. Generate a resolution proposal
        proposal = await self._generate_proposal(task)

        # 3. Update the task with the resolution notes
        try:
            existing_notes = task.notes or ""
            updated_notes = (
                f"{existing_notes}\n\n--- Propuesta del Ejecutor ---\n{proposal}"
                if existing_notes
                else f"--- Propuesta del Ejecutor ---\n{proposal}"
            )

            await self.notion_client.update_task(
                task_page_id,
                UpdateTaskRequest(
                    notes=updated_notes,
                    agent="Ejecutor",
                ),
            )
        except Exception as exc:
            logger.error(
                "Error al actualizar tarea %s con la propuesta: %s",
                task_page_id,
                exc,
            )

        # 4. Move to In Progress
        try:
            updated_task = await self.notion_client.move_task_status(
                task_page_id, "In Progress"
            )
        except Exception as exc:
            logger.error(
                "Error al mover tarea %s a In Progress: %s",
                task_page_id,
                exc,
            )
            updated_task = task

        # 5. Log the action
        await self.log_action(
            action="Propuesta de resolución generada",
            task_page_id=task_page_id,
            details=f"Tarea: {task.name}",
        )

        return {
            "task": updated_task.model_dump(),
            "proposal": proposal,
        }

    # ------------------------------------------------------------------
    # Complete a task
    # ------------------------------------------------------------------
    async def complete_task(
        self, task_page_id: str, notes: str = ""
    ) -> dict:
        """Move a task to *Done* in Notion.

        Parameters
        ----------
        task_page_id:
            Notion page ID of the task.
        notes:
            Optional completion notes to append.

        Returns
        -------
        dict
            Updated task data.
        """
        try:
            if notes:
                task = await self.notion_client.get_task(task_page_id)
                existing = task.notes or ""
                final_notes = (
                    f"{existing}\n\n--- Completada ---\n{notes}"
                    if existing
                    else f"--- Completada ---\n{notes}"
                )
                await self.notion_client.update_task(
                    task_page_id,
                    UpdateTaskRequest(notes=final_notes),
                )

            updated = await self.notion_client.move_task_status(
                task_page_id, "Done"
            )

            await self.log_action(
                action="Tarea completada",
                task_page_id=task_page_id,
                details=f"Tarea: {updated.name}",
            )

            return {"task": updated.model_dump(), "status": "Done"}

        except Exception as exc:
            logger.error(
                "Error al completar tarea %s: %s", task_page_id, exc
            )
            await self.log_action(
                action="Error al completar tarea",
                task_page_id=task_page_id,
                status="Error",
                details=str(exc),
            )
            return {"error": f"No se pudo completar la tarea: {exc}"}

    # ------------------------------------------------------------------
    # Request review
    # ------------------------------------------------------------------
    async def request_review(
        self, task_page_id: str, notes: str = ""
    ) -> dict:
        """Move a task to *En Revisión*.

        Parameters
        ----------
        task_page_id:
            Notion page ID of the task.
        notes:
            Optional review notes to append.

        Returns
        -------
        dict
            Updated task data.
        """
        try:
            if notes:
                task = await self.notion_client.get_task(task_page_id)
                existing = task.notes or ""
                final_notes = (
                    f"{existing}\n\n--- Solicitud de revisión ---\n{notes}"
                    if existing
                    else f"--- Solicitud de revisión ---\n{notes}"
                )
                await self.notion_client.update_task(
                    task_page_id,
                    UpdateTaskRequest(notes=final_notes),
                )

            updated = await self.notion_client.move_task_status(
                task_page_id, "En Revisión"
            )

            await self.log_action(
                action="Revisión solicitada",
                task_page_id=task_page_id,
                details=f"Tarea: {updated.name}",
            )

            return {"task": updated.model_dump(), "status": "En Revisión"}

        except Exception as exc:
            logger.error(
                "Error al solicitar revisión para %s: %s",
                task_page_id,
                exc,
            )
            await self.log_action(
                action="Error al solicitar revisión",
                task_page_id=task_page_id,
                status="Error",
                details=str(exc),
            )
            return {"error": f"No se pudo solicitar revisión: {exc}"}

    # ------------------------------------------------------------------
    # Resolution proposal generation
    # ------------------------------------------------------------------
    async def _generate_proposal(self, task) -> str:
        """Use LLM (or mock) to produce a step-by-step resolution."""
        prompt = (
            f"Genera una propuesta de resolución paso a paso para la siguiente tarea:\n\n"
            f"Nombre: {task.name}\n"
            f"Tipo: {task.type}\n"
            f"Prioridad: {task.priority}\n"
            f"Esfuerzo: {task.effort}\n"
            f"Notas actuales: {task.notes or '(ninguna)'}\n\n"
            "Responde con una lista numerada de pasos concretos y accionables."
        )

        if self.openclaw_client.is_mock_mode:
            return self._mock_proposal(task)

        try:
            return await self.think(prompt)
        except Exception as exc:
            logger.warning("Fallo al generar propuesta — usando mock: %s", exc)
            return self._mock_proposal(task)

    def _mock_proposal(self, task) -> str:
        """Generate a realistic mock resolution based on task type."""
        task_type = task.type if hasattr(task, "type") else "Otro"
        task_name = task.name if hasattr(task, "name") else "tarea"

        proposals = {
            "Código": (
                f"Propuesta de resolución para «{task_name}»:\n"
                "1. Revisar los requisitos y contexto del código existente\n"
                "2. Identificar los archivos afectados y crear rama de trabajo\n"
                "3. Implementar los cambios necesarios siguiendo las convenciones del proyecto\n"
                "4. Escribir pruebas unitarias para la nueva funcionalidad\n"
                "5. Ejecutar linter y formatear el código\n"
                "6. Crear pull request con descripción detallada"
            ),
            "Archivo": (
                f"Propuesta de resolución para «{task_name}»:\n"
                "1. Definir la estructura y formato del documento\n"
                "2. Recopilar la información necesaria de fuentes relevantes\n"
                "3. Redactar el contenido principal del archivo\n"
                "4. Revisar formato, ortografía y claridad\n"
                "5. Guardar en la ubicación correcta del proyecto"
            ),
            "Web": (
                f"Propuesta de resolución para «{task_name}»:\n"
                "1. Identificar las fuentes web relevantes para la investigación\n"
                "2. Recopilar y comparar información de múltiples fuentes\n"
                "3. Sintetizar los hallazgos principales\n"
                "4. Documentar las URLs de referencia\n"
                "5. Preparar un resumen ejecutivo con las conclusiones"
            ),
            "Comunicación": (
                f"Propuesta de resolución para «{task_name}»:\n"
                "1. Identificar destinatario(s) y canal de comunicación apropiado\n"
                "2. Redactar el mensaje con tono profesional y conciso\n"
                "3. Incluir contexto relevante y llamada a la acción\n"
                "4. Revisar antes de enviar\n"
                "5. Dar seguimiento si no hay respuesta en 24h"
            ),
        }

        return proposals.get(
            task_type,
            (
                f"Propuesta de resolución para «{task_name}»:\n"
                "1. Analizar los requisitos y el contexto de la tarea\n"
                "2. Planificar los pasos necesarios\n"
                "3. Ejecutar la acción principal\n"
                "4. Verificar el resultado\n"
                "5. Documentar lo realizado y marcar como completada"
            ),
        )
