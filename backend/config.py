"""
FlowStep AI — Centralised configuration.

Reads all environment variables in one place, parses them safely, and exposes
a ``validate_production_config()`` helper used at startup to fail fast when the
service is deployed to production with insecure defaults.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("flowstep.config")

# ---------------------------------------------------------------------------
# Insecure placeholder values that MUST NOT be used in production
# ---------------------------------------------------------------------------
_INSECURE_JWT_SECRETS = {
    "change-me-in-production",
    "change-me-to-a-random-256-bit-string",
    "",
}
_INSECURE_GATEWAY_TOKENS = {"flowstep-secret-token-123", ""}


def _get_int(name: str, default: int) -> int:
    """Read an int env var, falling back to *default* on missing/invalid values."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Env var %s='%s' is not a valid int — using default %d", name, raw, default)
        return default


def _get_csv(name: str, default: list[str]) -> list[str]:
    """Read a comma-separated env var into a list of trimmed strings."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION: bool = ENVIRONMENT == "production"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM: str = "HS256"
SESSION_TIMEOUT_MINUTES: int = _get_int("SESSION_TIMEOUT_MINUTES", 480)

# ---------------------------------------------------------------------------
# OpenClaw Gateway
# ---------------------------------------------------------------------------
OPENCLAW_GATEWAY_URL: str = os.getenv("OPENCLAW_GATEWAY_URL", "http://openclaw:18789")
OPENCLAW_GATEWAY_TOKEN: str = os.getenv("OPENCLAW_GATEWAY_TOKEN", "")

# ---------------------------------------------------------------------------
# Task limits
# ---------------------------------------------------------------------------
MAX_TASKS_PER_SESSION: int = _get_int("MAX_TASKS_PER_SESSION", 20)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ORIGINS: list[str] = _get_csv("CORS_ORIGINS", ["http://localhost:3000"])

# ---------------------------------------------------------------------------
# Behaviour flags
# ---------------------------------------------------------------------------
# When the real LLM/Gateway fails, should we silently fall back to the mock
# triage? Convenient in development, dangerous in production (users may believe
# the AI ran when it did not). Disabled automatically in production.
ALLOW_MOCK_FALLBACK: bool = (
    os.getenv("ALLOW_MOCK_FALLBACK", "true").lower() in {"1", "true", "yes"}
    and not IS_PRODUCTION
)


def validate_production_config() -> None:
    """Raise ``RuntimeError`` if production is configured with insecure defaults.

    Called once at application startup. In non-production environments the
    insecure defaults are tolerated but logged as warnings.
    """
    problems: list[str] = []

    if JWT_SECRET in _INSECURE_JWT_SECRETS:
        problems.append("JWT_SECRET is unset or uses an insecure default value")

    # The gateway token only matters when a real Anthropic key is present
    # (otherwise the client runs in mock mode and never calls the gateway).
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    real_llm = bool(api_key) and "PENDIENTE" not in api_key
    if real_llm and OPENCLAW_GATEWAY_TOKEN in _INSECURE_GATEWAY_TOKENS:
        problems.append("OPENCLAW_GATEWAY_TOKEN is unset or uses an insecure default value")

    if problems:
        message = "Insecure configuration detected: " + "; ".join(problems)
        if IS_PRODUCTION:
            raise RuntimeError(
                message
                + ". Set strong secrets via environment variables before running in production."
            )
        for problem in problems:
            logger.warning("INSECURE CONFIG (development only): %s", problem)
