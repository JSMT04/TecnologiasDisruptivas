"""
FlowStep AI — FastAPI Application Entrypoint
Assembles routers, middleware, CORS, and database initialisation.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env (before any config reads)
load_dotenv()

import asyncio

from agent.openclaw_client import OpenClawClient  # noqa: E402 — must come after load_dotenv
from agents.auto_verifier import start_auto_verifier  # noqa: E402
from agents.manager import AgentManager  # noqa: E402
from models.database import init_db  # noqa: E402
from notion.client import NotionClient  # noqa: E402
from routers import auth, health, tasks  # noqa: E402
from routers import notion_routes  # noqa: E402


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hooks
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise resources on startup, clean up on shutdown."""
    # Startup
    init_db()

    # Notion client
    notion_client = NotionClient(
        token=os.getenv("NOTION_API_TOKEN", ""),
        tasks_db_id=os.getenv("NOTION_TASKS_DB_ID", ""),
        log_db_id=os.getenv("NOTION_LOG_DB_ID", ""),
    )
    app.state.notion_client = notion_client

    # OpenClaw client
    openclaw_client = OpenClawClient()
    app.state.openclaw_client = openclaw_client

    # Agent manager
    agent_manager = AgentManager(notion_client, openclaw_client)
    app.state.agent_manager = agent_manager

    # Start auto-verifier background loop
    auto_verify_task = asyncio.create_task(start_auto_verifier(notion_client))

    yield

    # Shutdown — cancel the background auto-verifier
    auto_verify_task.cancel()
    try:
        await auto_verify_task
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FlowStep AI API",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow the React dev server
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(notion_routes.router)
