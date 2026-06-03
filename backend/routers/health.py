"""
FlowStep AI — Health Check Router
Public endpoint for service liveness / readiness probes.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Public health endpoint — no authentication required."""
    return {
        "status": "ok",
        "service": "flowstep-ai",
        "version": "0.1.0",
    }
