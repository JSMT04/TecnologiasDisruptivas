"""
FlowStep AI — Agent Manager
Orchestrates the multi-agent system by delegating work to the Organizador
and Ejecutor agents and exposing a unified API for the rest of the app.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from agent.openclaw_client import OpenClawClient
from agents.executor import ExecutorAgent
from agents.organizer import OrganizerAgent
from notion.client import NotionClient

logger = logging.getLogger("flowstep.agents.manager")


class AgentManager:
    """High-level orchestrator for the FlowStep AI agent system."""

    def __init__(
        self,
        notion_client: NotionClient,
        openclaw_client: OpenClawClient,
    ) -> None:
        self.notion_client = notion_client
        self.openclaw_client = openclaw_client

        self.organizer = OrganizerAgent(notion_client, openclaw_client)
        self.executor = ExecutorAgent(notion_client, openclaw_client)

        # Simple status tracking per agent
        self._agent_status: dict[str, dict] = {
            "Organizador": {"state": "idle", "last_action": None, "last_error": None},
            "Ejecutor": {"state": "idle", "last_action": None, "last_error": None},
        }

        logger.info(
            "AgentManager inicializado (mock_mode=%s)",
            notion_client.is_mock_mode,
        )

    # ------------------------------------------------------------------
    # Delegate to Organizador
    # ------------------------------------------------------------------
    async def process_new_tasks(
        self, raw_tasks: list[str], session_id: str
    ) -> dict:
        """Triage and create tasks via the Organizador agent.

        Parameters
        ----------
        raw_tasks:
            Raw task strings from user input.
        session_id:
            Current session identifier.

        Returns
        -------
        dict
            Result from ``OrganizerAgent.run()``.
        """
        self._set_status("Organizador", "working")
        try:
            result = await self.organizer.run(
                {"raw_tasks": raw_tasks, "session_id": session_id}
            )
            self._set_status(
                "Organizador",
                "idle",
                last_action=f"Triaje: {len(raw_tasks)} tareas",
            )
            return result
        except Exception as exc:
            self._set_status("Organizador", "error", last_error=str(exc))
            logger.error("Error en process_new_tasks: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Delegate to Ejecutor
    # ------------------------------------------------------------------
    async def execute_task(self, task_page_id: str) -> dict:
        """Generate a resolution proposal via the Ejecutor agent.

        Parameters
        ----------
        task_page_id:
            Notion page ID of the task to execute.

        Returns
        -------
        dict
            Result from ``ExecutorAgent.run()``.
        """
        self._set_status("Ejecutor", "working")
        try:
            result = await self.executor.run({"task_page_id": task_page_id})
            self._set_status(
                "Ejecutor",
                "idle",
                last_action=f"Ejecutado: {task_page_id[:8]}…",
            )
            return result
        except Exception as exc:
            self._set_status("Ejecutor", "error", last_error=str(exc))
            logger.error("Error en execute_task: %s", exc)
            raise

    async def complete_task(
        self, task_page_id: str, notes: str = ""
    ) -> dict:
        """Mark a task as Done via the Ejecutor agent."""
        self._set_status("Ejecutor", "working")
        try:
            result = await self.executor.complete_task(task_page_id, notes)
            self._set_status(
                "Ejecutor",
                "idle",
                last_action=f"Completada: {task_page_id[:8]}…",
            )
            return result
        except Exception as exc:
            self._set_status("Ejecutor", "error", last_error=str(exc))
            logger.error("Error en complete_task: %s", exc)
            raise

    async def request_review(
        self, task_page_id: str, notes: str = ""
    ) -> dict:
        """Request review for a task via the Ejecutor agent."""
        self._set_status("Ejecutor", "working")
        try:
            result = await self.executor.request_review(task_page_id, notes)
            self._set_status(
                "Ejecutor",
                "idle",
                last_action=f"En revisión: {task_page_id[:8]}…",
            )
            return result
        except Exception as exc:
            self._set_status("Ejecutor", "error", last_error=str(exc))
            logger.error("Error en request_review: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Kanban board state
    # ------------------------------------------------------------------
    async def get_kanban_state(
        self, session_id: Optional[str] = None
    ) -> dict:
        """Query Notion for the current board state, grouped by status.

        Returns
        -------
        dict
            ``{"columns": {"Backlog": [...], "To Do": [...], ...}, "total": N}``
        """
        tasks = await self.notion_client.query_tasks(session_id=session_id)

        columns: dict[str, list[dict]] = {
            "Backlog": [],
            "To Do": [],
            "In Progress": [],
            "En Revisión": [],
            "Done": [],
        }

        for task in tasks:
            col = columns.get(task.status, columns["Backlog"])
            col.append(task.model_dump())

        return {"columns": columns, "total": len(tasks)}

    # ------------------------------------------------------------------
    # Agent activity log
    # ------------------------------------------------------------------
    async def get_agent_activity(self, limit: int = 20) -> list[dict]:
        """Get recent agent log entries from Notion."""
        logs = await self.notion_client.query_agent_log(limit=limit)
        return [log.model_dump() for log in logs]

    # ------------------------------------------------------------------
    # Agent statuses
    # ------------------------------------------------------------------
    async def get_agents_status(self) -> dict:
        """Return the current status of each agent."""
        return {
            "agents": self._agent_status,
            "notion_mode": "mock" if self.notion_client.is_mock_mode else "real",
            "openclaw_mode": "mock" if self.openclaw_client.is_mock_mode else "real",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _set_status(
        self,
        agent_name: str,
        state: str,
        last_action: Optional[str] = None,
        last_error: Optional[str] = None,
    ) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        entry = self._agent_status.setdefault(
            agent_name, {"state": "idle", "last_action": None, "last_error": None}
        )
        entry["state"] = state
        entry["updated_at"] = now
        if last_action is not None:
            entry["last_action"] = last_action
            entry["last_action_at"] = now
        if last_error is not None:
            entry["last_error"] = last_error
            entry["last_error_at"] = now
