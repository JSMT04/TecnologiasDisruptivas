"""
FlowStep AI — Notion Database Setup Script
Creates the Tasks and Agent Log databases in a Notion workspace.

Can be run standalone:
    python -m notion.setup_databases

Or imported:
    from notion.setup_databases import run_setup
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import httpx
from dotenv import load_dotenv

logger = logging.getLogger("flowstep.notion.setup")

_NOTION_BASE_URL = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


def _headers(token: str) -> dict:
    """Build standard Notion API request headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Tasks database
# ---------------------------------------------------------------------------
async def create_tasks_database(token: str, parent_page_id: str) -> str:
    """Create the *Tasks* database in Notion.

    Parameters
    ----------
    token:
        Notion integration bearer token.
    parent_page_id:
        The Notion page that will contain the new database.

    Returns
    -------
    str
        The ``database_id`` of the newly created database.
    """
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": "FlowStep Tasks"}}],
        "is_inline": True,
        "properties": {
            "Name": {"title": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "Backlog", "color": "default"},
                        {"name": "To Do", "color": "blue"},
                        {"name": "In Progress", "color": "yellow"},
                        {"name": "En Revisión", "color": "orange"},
                        {"name": "Done", "color": "green"},
                    ]
                }
            },
            "Priority": {
                "select": {
                    "options": [
                        {"name": "Alta", "color": "red"},
                        {"name": "Media", "color": "yellow"},
                        {"name": "Baja", "color": "gray"},
                    ]
                }
            },
            "Effort": {
                "select": {
                    "options": [
                        {"name": "Bajo", "color": "green"},
                        {"name": "Medio", "color": "yellow"},
                        {"name": "Alto", "color": "red"},
                    ]
                }
            },
            "Type": {
                "select": {
                    "options": [
                        {"name": "Código", "color": "purple"},
                        {"name": "Archivo", "color": "blue"},
                        {"name": "Web", "color": "pink"},
                        {"name": "Comunicación", "color": "orange"},
                        {"name": "Otro", "color": "default"},
                    ]
                }
            },
            "Agent": {
                "select": {
                    "options": [
                        {"name": "Organizador", "color": "blue"},
                        {"name": "Ejecutor", "color": "green"},
                        {"name": "Usuario", "color": "default"},
                    ]
                }
            },
            "Session ID": {"rich_text": {}},
            "Order": {"number": {"format": "number"}},
            "Notes": {"rich_text": {}},
        },
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{_NOTION_BASE_URL}/databases",
            headers=_headers(token),
            json=payload,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Error al crear la base de datos Tasks: "
                f"HTTP {resp.status_code} — {resp.text}"
            )

        db_id: str = resp.json()["id"]
        logger.info("Base de datos Tasks creada: %s", db_id)
        return db_id


# ---------------------------------------------------------------------------
# Agent Log database
# ---------------------------------------------------------------------------
async def create_agent_log_database(token: str, parent_page_id: str) -> str:
    """Create the *Agent Log* database in Notion.

    Parameters
    ----------
    token:
        Notion integration bearer token.
    parent_page_id:
        The Notion page that will contain the new database.

    Returns
    -------
    str
        The ``database_id`` of the newly created database.
    """
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [
            {"type": "text", "text": {"content": "FlowStep Agent Log"}}
        ],
        "is_inline": True,
        "properties": {
            "Action": {"title": {}},
            "Agent": {
                "select": {
                    "options": [
                        {"name": "Organizador", "color": "blue"},
                        {"name": "Ejecutor", "color": "green"},
                        {"name": "Usuario", "color": "default"},
                    ]
                }
            },
            "Status": {
                "select": {
                    "options": [
                        {"name": "Success", "color": "green"},
                        {"name": "Error", "color": "red"},
                        {"name": "Pending", "color": "yellow"},
                    ]
                }
            },
            "Details": {"rich_text": {}},
            "Timestamp": {"rich_text": {}},
            "Task": {"relation": {"database_id": "placeholder"}},
        },
    }

    # NOTE: The Task relation property requires a valid database_id to point
    # to.  When running setup, we create the Tasks DB first and then replace
    # the placeholder.  If the Tasks DB id is not yet known we omit the
    # relation property and add it later manually.
    # For a first-time standalone run we simply skip the relation.
    payload["properties"].pop("Task", None)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{_NOTION_BASE_URL}/databases",
            headers=_headers(token),
            json=payload,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Error al crear la base de datos Agent Log: "
                f"HTTP {resp.status_code} — {resp.text}"
            )

        db_id: str = resp.json()["id"]
        logger.info("Base de datos Agent Log creada: %s", db_id)
        return db_id


# ---------------------------------------------------------------------------
# Full setup
# ---------------------------------------------------------------------------
async def run_setup(token: str, parent_page_id: str) -> dict:
    """Create both databases and return their IDs.

    Returns
    -------
    dict
        ``{"tasks_db_id": "...", "log_db_id": "..."}``
    """
    logger.info("Iniciando setup de bases de datos en Notion…")

    tasks_db_id = await create_tasks_database(token, parent_page_id)
    log_db_id = await create_agent_log_database(token, parent_page_id)

    logger.info(
        "Setup completado — Tasks DB: %s | Log DB: %s",
        tasks_db_id,
        log_db_id,
    )
    return {"tasks_db_id": tasks_db_id, "log_db_id": log_db_id}


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    load_dotenv()

    notion_token = os.getenv("NOTION_API_TOKEN", "")
    parent_id = os.getenv("NOTION_PARENT_PAGE_ID", "")

    if not notion_token or "PENDIENTE" in notion_token:
        print(
            "❌  NOTION_API_TOKEN no configurado o contiene PENDIENTE.\n"
            "   Configura la variable de entorno antes de ejecutar el setup."
        )
        sys.exit(1)

    if not parent_id:
        print(
            "❌  NOTION_PARENT_PAGE_ID no configurado.\n"
            "   Indica el ID de la página padre donde se crearán las bases de datos."
        )
        sys.exit(1)

    result = asyncio.run(run_setup(notion_token, parent_id))
    print(f"\n✅  Setup completado exitosamente:")
    print(f"   NOTION_TASKS_DB_ID  = {result['tasks_db_id']}")
    print(f"   NOTION_LOG_DB_ID    = {result['log_db_id']}")
    print("\n   Agrega estas variables a tu archivo .env")
