"""
FlowStep AI — Notion Pydantic Schemas
Maps between Notion API page properties and our internal data models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Notion Task — mirrors the Tasks database in Notion
# ---------------------------------------------------------------------------
class NotionTask(BaseModel):
    """Internal representation of a task stored in the Notion Kanban board."""

    page_id: str = ""
    name: str = ""
    status: str = Field(
        default="Backlog",
        pattern=r"^(Backlog|To Do|In Progress|En Revisión|Done)$",
    )
    priority: str = Field(default="Media", pattern=r"^(Alta|Media|Baja)$")
    effort: str = Field(default="Medio", pattern=r"^(Bajo|Medio|Alto)$")
    type: str = Field(
        default="Otro",
        pattern=r"^(Código|Archivo|Web|Comunicación|Otro)$",
    )
    agent: str = Field(
        default="Usuario",
        pattern=r"^(Organizador|Ejecutor|Usuario)$",
    )
    session_id: str = ""
    order: int = 0
    notes: str = ""
    created_time: Optional[str] = None
    last_edited_time: Optional[str] = None
    verificado: bool = False

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Notion Agent Log — mirrors the Agent Log database in Notion
# ---------------------------------------------------------------------------
class NotionAgentLog(BaseModel):
    """Internal representation of an agent activity log entry."""

    page_id: str = ""
    action: str = ""
    agent: str = ""
    task_relation: Optional[str] = None
    status: str = Field(default="Success", pattern=r"^(Success|Error|Pending)$")
    details: str = ""
    timestamp: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class CreateTaskRequest(BaseModel):
    """Payload for creating a new task in Notion."""

    name: str = Field(..., min_length=1, max_length=200)
    status: str = Field(default="To Do")
    priority: str = Field(default="Media")
    effort: str = Field(default="Medio")
    type: str = Field(default="Otro")
    agent: str = Field(default="Usuario")
    session_id: str = ""
    order: int = 0
    notes: str = ""


class UpdateTaskRequest(BaseModel):
    """Payload for partially updating a task in Notion."""

    name: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    effort: Optional[str] = None
    type: Optional[str] = None
    agent: Optional[str] = None
    order: Optional[int] = None
    notes: Optional[str] = None


class MoveTaskRequest(BaseModel):
    """Payload for moving a task to a new status column."""

    status: str = Field(..., pattern=r"^(Backlog|To Do|In Progress|En Revisión|Done)$")


# ---------------------------------------------------------------------------
# Helper: Notion page properties → NotionTask
# ---------------------------------------------------------------------------
def notion_properties_to_task(
    page: dict,
) -> NotionTask:
    """Convert a raw Notion API page response into a ``NotionTask``.

    Parameters
    ----------
    page:
        The full page object returned by the Notion API (``GET /v1/pages``
        or an item inside a database query result).

    Returns
    -------
    NotionTask
    """
    props = page.get("properties", {})

    def _rich_text(prop_name: str) -> str:
        prop = props.get(prop_name, {})
        texts = prop.get("rich_text", [])
        if texts:
            return texts[0].get("plain_text", "")
        return ""

    def _title(prop_name: str = "Name") -> str:
        prop = props.get(prop_name, {})
        titles = prop.get("title", [])
        if titles:
            return titles[0].get("plain_text", "")
        return ""

    def _select(prop_name: str) -> str:
        prop = props.get(prop_name, {})
        sel = prop.get("select")
        if sel:
            return sel.get("name", "")
        return ""

    def _number(prop_name: str) -> int:
        prop = props.get(prop_name, {})
        val = prop.get("number")
        return int(val) if val is not None else 0

    return NotionTask(
        page_id=page.get("id", ""),
        name=_title("Name"),
        status=_select("Status") or "Backlog",
        priority=_select("Priority") or "Media",
        effort=_select("Effort") or "Medio",
        type=_select("Type") or "Otro",
        agent=_select("Agent") or "Usuario",
        session_id=_rich_text("Session ID"),
        order=_number("Order"),
        notes=_rich_text("Notes"),
        created_time=page.get("created_time"),
        last_edited_time=page.get("last_edited_time"),
    )


# ---------------------------------------------------------------------------
# Helper: NotionTask → Notion API properties dict
# ---------------------------------------------------------------------------
def task_to_notion_properties(task: CreateTaskRequest | UpdateTaskRequest) -> dict:
    """Build the ``properties`` dict expected by the Notion API.

    Only non-``None`` fields are included so this works for both create
    (``CreateTaskRequest``) and partial update (``UpdateTaskRequest``).

    Returns
    -------
    dict
        A dict ready to be used as ``{"properties": <returned>}`` in a
        Notion ``POST /v1/pages`` or ``PATCH /v1/pages/{id}`` request.
    """
    props: dict = {}

    name = getattr(task, "name", None)
    if name is not None:
        props["Name"] = {"title": [{"text": {"content": name}}]}

    status = getattr(task, "status", None)
    if status is not None:
        props["Status"] = {"select": {"name": status}}

    priority = getattr(task, "priority", None)
    if priority is not None:
        props["Priority"] = {"select": {"name": priority}}

    effort = getattr(task, "effort", None)
    if effort is not None:
        props["Effort"] = {"select": {"name": effort}}

    task_type = getattr(task, "type", None)
    if task_type is not None:
        props["Type"] = {"select": {"name": task_type}}

    agent = getattr(task, "agent", None)
    if agent is not None:
        props["Agent"] = {"select": {"name": agent}}

    session_id = getattr(task, "session_id", None)
    if session_id is not None:
        props["Session ID"] = {"rich_text": [{"text": {"content": session_id}}]}

    order = getattr(task, "order", None)
    if order is not None:
        props["Order"] = {"number": order}

    notes = getattr(task, "notes", None)
    if notes is not None:
        props["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

    return props
