"""
FlowStep AI — Database Models & Engine Setup
SQLAlchemy 2.x declarative style (mapped_column).
Database: SQLite at /app/data/flowstep.db
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

# ---------------------------------------------------------------------------
# Database path — configurable via env, defaults to /app/data/flowstep.db
# ---------------------------------------------------------------------------
DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/data/flowstep.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite + FastAPI
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Shared declarative base for all FlowStep AI models."""
    pass


# ---------------------------------------------------------------------------
# Session table
# ---------------------------------------------------------------------------
class SessionModel(Base):
    """Represents a user work session."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, doc="UUID v4")
    created_at: Mapped[str] = mapped_column(String, nullable=False, doc="ISO8601")
    ended_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="NULL si activa")
    status: Mapped[str] = mapped_column(
        String, nullable=False, doc="'active' | 'completed' | 'abandoned'"
    )
    total_tasks: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    report_path: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, doc="Ruta al .md exportado"
    )

    # Relationship — one session has many tasks
    tasks: Mapped[list["TaskModel"]] = relationship(
        "TaskModel", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Session id={self.id!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# Task table
# ---------------------------------------------------------------------------
class TaskModel(Base):
    """Represents a single actionable task inside a session."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, doc="UUID v4")
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.id"), nullable=False
    )
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    urgency: Mapped[str] = mapped_column(
        String, nullable=False, doc="'alta' | 'media' | 'baja'"
    )
    effort: Mapped[str] = mapped_column(
        String, nullable=False, doc="'bajo' | 'medio' | 'alto'"
    )
    type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc="'archivo' | 'código' | 'web' | 'comunicación' | 'otro'",
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc="'pendiente' | 'activa' | 'completada' | 'pospuesta' | 'bloqueada'",
    )
    expected_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship back to session
    session: Mapped["SessionModel"] = relationship(
        "SessionModel", back_populates="tasks"
    )

    @property
    def tipo(self) -> str:
        """Map the 'type' DB field to the Spanish 'tipo' contract for Pydantic."""
        return self.type

    @tipo.setter
    def tipo(self, value: str) -> None:
        self.type = value

    def __repr__(self) -> str:
        return f"<Task id={self.id!r} title={self.title!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# MCP Audit Log table
# ---------------------------------------------------------------------------
class MCPAuditLog(Base):
    """Audit trail for every MCP file-system operation."""

    __tablename__ = "mcp_audit_log"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    task_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timestamp: Mapped[str] = mapped_column(String, nullable=False, doc="ISO8601")
    operation: Mapped[str] = mapped_column(
        String, nullable=False, doc="'READ' | 'WRITE' | 'LIST' | 'DENIED'"
    )
    path: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[str] = mapped_column(
        String, nullable=False, doc="'OK' | 'NOT_FOUND' | 'DENIED' | 'ERROR'"
    )
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<MCPAuditLog id={self.id} op={self.operation!r} result={self.result!r}>"


# ---------------------------------------------------------------------------
# Initialization & dependency helpers
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Create all tables if they don't exist yet."""
    # Ensure the data directory exists
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a SQLAlchemy session, auto-closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
