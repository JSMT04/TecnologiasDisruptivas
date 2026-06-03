"""
FlowStep AI — Notion API Client
Async client for the Notion API with automatic mock fallback for development
without a Notion connection (mirrors the OpenClawClient mock pattern).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from notion.schemas import (
    CreateTaskRequest,
    NotionAgentLog,
    NotionTask,
    UpdateTaskRequest,
    notion_properties_to_task,
    task_to_notion_properties,
)

logger = logging.getLogger("flowstep.notion")

_NOTION_BASE_URL = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


class NotionClient:
    """Async client for the Notion API.

    If *token* is empty or contains ``PENDIENTE`` the client operates in
    **mock mode** — every method returns realistic fake data so the rest of
    the application can be developed and tested without a live Notion
    connection.
    """

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    def __init__(
        self,
        token: str,
        tasks_db_id: str = "",
        log_db_id: str = "",
    ) -> None:
        self.token = token
        self.tasks_db_id = tasks_db_id
        self.log_db_id = log_db_id

        self.is_mock_mode = (
            not token
            or "PENDIENTE" in token
        )

        self._headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }

        # In-memory stores used only in mock mode
        self._mock_tasks: dict[str, NotionTask] = {}
        self._mock_logs: list[NotionAgentLog] = []

        if self.is_mock_mode:
            logger.info(
                "NotionClient en MODO MOCK automático "
                "(no se detectó un token válido de Notion)."
            )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    async def health_check(self) -> dict:
        """Check Notion API connectivity."""
        if self.is_mock_mode:
            return {
                "status": "ok",
                "mode": "mock",
                "notion_connected": False,
                "tasks_db": self.tasks_db_id or "(no configurado)",
                "log_db": self.log_db_id or "(no configurado)",
            }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{_NOTION_BASE_URL}/users/me",
                    headers=self._headers,
                )
                if resp.status_code == 200:
                    user_data = resp.json()
                    return {
                        "status": "ok",
                        "mode": "real",
                        "notion_connected": True,
                        "bot_name": user_data.get("name", ""),
                        "tasks_db": self.tasks_db_id,
                        "log_db": self.log_db_id,
                    }
                return {
                    "status": "error",
                    "mode": "real",
                    "notion_connected": False,
                    "detail": f"HTTP {resp.status_code}",
                }
        except Exception as exc:
            logger.warning("Fallo al conectar con la API de Notion: %s", exc)
            return {
                "status": "error",
                "mode": "real",
                "notion_connected": False,
                "detail": str(exc),
            }

    # ------------------------------------------------------------------
    # Task CRUD
    # ------------------------------------------------------------------
    async def create_task(self, task: CreateTaskRequest) -> NotionTask:
        """Create a new task page in the Notion Tasks database."""
        if self.is_mock_mode:
            return self._mock_create_task(task)

        properties = task_to_notion_properties(task)
        payload = {
            "parent": {"database_id": self.tasks_db_id},
            "properties": properties,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_NOTION_BASE_URL}/pages",
                headers=self._headers,
                json=payload,
            )
            if resp.status_code not in (200, 201):
                logger.error(
                    "Error al crear tarea en Notion: %s — %s",
                    resp.status_code,
                    resp.text,
                )
                raise RuntimeError(
                    f"Notion API error {resp.status_code}: {resp.text}"
                )

            page = resp.json()
            return notion_properties_to_task(page)

    async def update_task(
        self, page_id: str, updates: UpdateTaskRequest
    ) -> NotionTask:
        """Partially update a task page in Notion."""
        if self.is_mock_mode:
            return self._mock_update_task(page_id, updates)

        properties = task_to_notion_properties(updates)
        payload = {"properties": properties}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{_NOTION_BASE_URL}/pages/{page_id}",
                headers=self._headers,
                json=payload,
            )
            if resp.status_code != 200:
                logger.error(
                    "Error al actualizar tarea %s: %s — %s",
                    page_id,
                    resp.status_code,
                    resp.text,
                )
                raise RuntimeError(
                    f"Notion API error {resp.status_code}: {resp.text}"
                )

            page = resp.json()
            return notion_properties_to_task(page)

    async def move_task_status(
        self, page_id: str, new_status: str
    ) -> NotionTask:
        """Convenience: move a task to a new Kanban status column."""
        return await self.update_task(
            page_id, UpdateTaskRequest(status=new_status)
        )

    async def get_task(self, page_id: str) -> NotionTask:
        """Retrieve a single task by its Notion page ID."""
        if self.is_mock_mode:
            return self._mock_get_task(page_id)

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_NOTION_BASE_URL}/pages/{page_id}",
                headers=self._headers,
            )
            if resp.status_code != 200:
                logger.error(
                    "Error al obtener tarea %s: %s — %s",
                    page_id,
                    resp.status_code,
                    resp.text,
                )
                raise RuntimeError(
                    f"Notion API error {resp.status_code}: {resp.text}"
                )

            page = resp.json()
            return notion_properties_to_task(page)

    async def query_tasks(
        self,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[NotionTask]:
        """Query the Tasks database with optional filters."""
        if self.is_mock_mode:
            return self._mock_query_tasks(session_id, status)

        filters: list[dict] = []
        if session_id:
            filters.append(
                {
                    "property": "Session ID",
                    "rich_text": {"equals": session_id},
                }
            )
        if status:
            filters.append(
                {
                    "property": "Status",
                    "select": {"equals": status},
                }
            )

        body: dict = {
            "sorts": [{"property": "Order", "direction": "ascending"}],
        }
        if len(filters) == 1:
            body["filter"] = filters[0]
        elif len(filters) > 1:
            body["filter"] = {"and": filters}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_NOTION_BASE_URL}/databases/{self.tasks_db_id}/query",
                headers=self._headers,
                json=body,
            )
            if resp.status_code != 200:
                logger.error(
                    "Error al consultar tareas: %s — %s",
                    resp.status_code,
                    resp.text,
                )
                raise RuntimeError(
                    f"Notion API error {resp.status_code}: {resp.text}"
                )

            data = resp.json()
            return [
                notion_properties_to_task(page)
                for page in data.get("results", [])
            ]

    # ------------------------------------------------------------------
    # Agent Log
    # ------------------------------------------------------------------
    async def log_agent_action(
        self,
        agent: str,
        action: str,
        task_page_id: Optional[str] = None,
        status: str = "Success",
        details: str = "",
    ) -> dict:
        """Create an entry in the Agent Log database."""
        if self.is_mock_mode:
            return self._mock_log_action(agent, action, task_page_id, status, details)

        now = datetime.now(tz=timezone.utc).isoformat()
        properties: dict = {
            "Action": {"title": [{"text": {"content": action}}]},
            "Agent": {"select": {"name": agent}},
            "Status": {"select": {"name": status}},
            "Details": {"rich_text": [{"text": {"content": details}}]},
            "Timestamp": {"rich_text": [{"text": {"content": now}}]},
        }

        if task_page_id:
            properties["Task"] = {
                "relation": [{"id": task_page_id}],
            }

        payload = {
            "parent": {"database_id": self.log_db_id},
            "properties": properties,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_NOTION_BASE_URL}/pages",
                headers=self._headers,
                json=payload,
            )
            # Self-healing fallback: if the "Task" relation doesn't exist, retry without it
            if resp.status_code == 400 and "Task" in resp.text and ("property" in resp.text or "validation" in resp.text):
                logger.warning("Propiedad 'Task' no encontrada en la base de datos de logs de Notion. Reintentando sin la relación.")
                properties.pop("Task", None)
                payload["properties"] = properties
                resp = await client.post(
                    f"{_NOTION_BASE_URL}/pages",
                    headers=self._headers,
                    json=payload,
                )

            if resp.status_code not in (200, 201):
                logger.error(
                    "Error al registrar acción del agente: %s — %s",
                    resp.status_code,
                    resp.text,
                )
                raise RuntimeError(
                    f"Notion API error {resp.status_code}: {resp.text}"
                )

            return resp.json()

    async def query_agent_log(self, limit: int = 20) -> list[NotionAgentLog]:
        """Query recent agent activity from the Agent Log database."""
        if self.is_mock_mode:
            return self._mock_query_log(limit)

        body = {
            "sorts": [
                {"property": "Timestamp", "direction": "descending"},
            ],
            "page_size": min(limit, 100),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_NOTION_BASE_URL}/databases/{self.log_db_id}/query",
                headers=self._headers,
                json=body,
            )
            if resp.status_code != 200:
                logger.error(
                    "Error al consultar log de agentes: %s — %s",
                    resp.status_code,
                    resp.text,
                )
                raise RuntimeError(
                    f"Notion API error {resp.status_code}: {resp.text}"
                )

            data = resp.json()
            results: list[NotionAgentLog] = []
            for page in data.get("results", []):
                results.append(self._parse_agent_log_page(page))
            return results

    # ------------------------------------------------------------------
    # Internal: parse Agent Log page
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_agent_log_page(page: dict) -> NotionAgentLog:
        """Convert a raw Notion page from the Agent Log DB into a model."""
        props = page.get("properties", {})

        def _title(name: str) -> str:
            titles = props.get(name, {}).get("title", [])
            return titles[0].get("plain_text", "") if titles else ""

        def _rich(name: str) -> str:
            texts = props.get(name, {}).get("rich_text", [])
            return texts[0].get("plain_text", "") if texts else ""

        def _select(name: str) -> str:
            sel = props.get(name, {}).get("select")
            return sel.get("name", "") if sel else ""

        def _relation_first(name: str) -> Optional[str]:
            rels = props.get(name, {}).get("relation", [])
            return rels[0].get("id") if rels else None

        return NotionAgentLog(
            page_id=page.get("id", ""),
            action=_title("Action"),
            agent=_select("Agent"),
            task_relation=_relation_first("Task"),
            status=_select("Status") or "Success",
            details=_rich("Details"),
            timestamp=_rich("Timestamp") or page.get("created_time"),
        )

    # ------------------------------------------------------------------
    # Mock helpers — realistic fake data for development
    # ------------------------------------------------------------------
    def _mock_create_task(self, task: CreateTaskRequest) -> NotionTask:
        now = datetime.now(tz=timezone.utc).isoformat()
        page_id = str(uuid.uuid4())
        notion_task = NotionTask(
            page_id=page_id,
            name=task.name,
            status=task.status,
            priority=task.priority,
            effort=task.effort,
            type=task.type,
            agent=task.agent,
            session_id=task.session_id,
            order=task.order,
            notes=task.notes,
            created_time=now,
            last_edited_time=now,
        )
        self._mock_tasks[page_id] = notion_task
        logger.debug("Mock: tarea creada '%s' (id=%s)", task.name, page_id)
        return notion_task

    def _mock_update_task(
        self, page_id: str, updates: UpdateTaskRequest
    ) -> NotionTask:
        existing = self._mock_tasks.get(page_id)
        if not existing:
            raise RuntimeError(f"Mock: tarea no encontrada — {page_id}")

        update_data = updates.model_dump(exclude_none=True)
        updated = existing.model_copy(update=update_data)
        updated.last_edited_time = datetime.now(tz=timezone.utc).isoformat()
        self._mock_tasks[page_id] = updated
        logger.debug("Mock: tarea actualizada '%s'", page_id)
        return updated

    def _mock_get_task(self, page_id: str) -> NotionTask:
        existing = self._mock_tasks.get(page_id)
        if not existing:
            raise RuntimeError(f"Mock: tarea no encontrada — {page_id}")
        return existing

    def _mock_query_tasks(
        self,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[NotionTask]:
        results = list(self._mock_tasks.values())
        if session_id:
            results = [t for t in results if t.session_id == session_id]
        if status:
            results = [t for t in results if t.status == status]
        results.sort(key=lambda t: t.order)
        return results

    def _mock_log_action(
        self,
        agent: str,
        action: str,
        task_page_id: Optional[str],
        status: str,
        details: str,
    ) -> dict:
        now = datetime.now(tz=timezone.utc).isoformat()
        log_id = str(uuid.uuid4())
        entry = NotionAgentLog(
            page_id=log_id,
            action=action,
            agent=agent,
            task_relation=task_page_id,
            status=status,
            details=details,
            timestamp=now,
        )
        self._mock_logs.append(entry)
        logger.debug(
            "Mock: acción registrada — %s / %s / %s", agent, action, status
        )
        return {"id": log_id, "agent": agent, "action": action, "status": status}

    def _mock_query_log(self, limit: int = 20) -> list[NotionAgentLog]:
        # Return most recent first
        return list(reversed(self._mock_logs[-limit:]))
