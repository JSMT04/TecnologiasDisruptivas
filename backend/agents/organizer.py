"""
FlowStep AI — Organizador Agent
Receives raw task strings, analyses/prioritises them via LLM, and persists
the structured tasks into the Notion Kanban board.
"""

from __future__ import annotations

import json
import logging
import uuid

from agent.openclaw_client import OpenClawClient
from agents.base_agent import BaseAgent
from notion.client import NotionClient
from notion.schemas import CreateTaskRequest

logger = logging.getLogger("flowstep.agents.organizer")


class OrganizerAgent(BaseAgent):
    """Agent responsible for triaging and organising incoming tasks."""

    name: str = "Organizador"

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
        """Triage *raw_tasks* and persist them in Notion.

        Parameters
        ----------
        input_data:
            Must contain ``raw_tasks`` (list[str]) and ``session_id`` (str).

        Returns
        -------
        dict
            ``{"tasks": [...], "stats": {...}}``
        """
        raw_tasks: list[str] = input_data.get("raw_tasks", [])
        session_id: str = input_data.get("session_id", "")

        if not raw_tasks:
            return {"tasks": [], "stats": {"total": 0}}

        await self.log_action(
            action="Inicio de triaje",
            details=f"{len(raw_tasks)} tareas recibidas para la sesión {session_id}",
        )

        # 1. Query existing tasks to avoid duplicates
        existing = await self.notion_client.query_tasks(session_id=session_id)
        existing_names = {t.name.lower().strip() for t in existing}

        # 2. Analyse tasks via LLM (or mock)
        triage_result = await self._triage_tasks(raw_tasks)
        triaged = triage_result.get("tasks", [])
        tiempo_total_estimado_min = triage_result.get("tiempo_total_estimado_min", 60)
        advertencia = triage_result.get("advertencia")

        # 3. Create tasks in Notion
        created_tasks = []
        start_order = len(existing) + 1

        for idx, item in enumerate(triaged):
            name = item.get("title", item.get("name", f"Tarea {idx + 1}"))

            # Skip duplicates
            if name.lower().strip() in existing_names:
                logger.info("Tarea duplicada omitida: '%s'", name)
                continue

            task_req = CreateTaskRequest(
                name=name,
                status="To Do",
                priority=self._map_priority(item.get("urgency", "media")),
                effort=self._map_effort(item.get("effort", "medio")),
                type=self._map_type(item.get("tipo", "otro")),
                agent="Organizador",
                session_id=session_id,
                order=start_order + idx,
                notes=item.get("instrucciones", ""),
            )

            try:
                notion_task = await self.notion_client.create_task(task_req)
                created_tasks.append(notion_task.model_dump())
            except Exception as exc:
                logger.error("Error al crear tarea '%s': %s", name, exc)
                await self.log_action(
                    action=f"Error creando tarea: {name}",
                    status="Error",
                    details=str(exc),
                )

        # 4. Log completion
        await self.log_action(
            action="Triaje completado",
            details=(
                f"Se crearon {len(created_tasks)} tareas nuevas de "
                f"{len(raw_tasks)} recibidas en sesión {session_id}"
            ),
        )

        return {
            "tasks": created_tasks,
            "stats": {
                "total_received": len(raw_tasks),
                "created": len(created_tasks),
                "duplicates_skipped": len(raw_tasks) - len(created_tasks),
                "session_id": session_id,
            },
            "tiempo_total_estimado_min": tiempo_total_estimado_min,
            "advertencia": advertencia,
        }

    # ------------------------------------------------------------------
    # Triage via LLM or mock
    # ------------------------------------------------------------------
    async def _triage_tasks(self, raw_tasks: list[str]) -> dict:
        """Analyse raw tasks and return the full triage result dictionary."""
        if self.openclaw_client.is_mock_mode:
            return self._mock_triage(raw_tasks)

        # Use the OpenClaw triage (same prompt pattern as openclaw_client.py)
        try:
            result = await self.openclaw_client.run_triage(raw_tasks)
            return result
        except Exception as exc:
            logger.warning("Fallo en triaje LLM — usando mock: %s", exc)
            return self._mock_triage(raw_tasks)

    # ------------------------------------------------------------------
    # Mock triage — reuses logic from OpenClawClient._generate_mock_triage
    # ------------------------------------------------------------------
    def _mock_triage(self, raw_tasks: list[str]) -> dict:
        """Smart mock triage mirroring ``OpenClawClient._generate_mock_triage``."""
        return self.openclaw_client._generate_mock_triage(raw_tasks)

    # ------------------------------------------------------------------
    # Value mappers (OpenClaw uses lowercase, Notion uses capitalised)
    # ------------------------------------------------------------------
    @staticmethod
    def _map_priority(value: str) -> str:
        mapping = {"alta": "Alta", "media": "Media", "baja": "Baja"}
        return mapping.get(value.lower(), "Media")

    @staticmethod
    def _map_effort(value: str) -> str:
        mapping = {"bajo": "Bajo", "medio": "Medio", "alto": "Alto"}
        return mapping.get(value.lower(), "Medio")

    @staticmethod
    def _map_type(value: str) -> str:
        mapping = {
            "código": "Código",
            "codigo": "Código",
            "archivo": "Archivo",
            "web": "Web",
            "comunicación": "Comunicación",
            "comunicacion": "Comunicación",
            "otro": "Otro",
        }
        return mapping.get(value.lower(), "Otro")
