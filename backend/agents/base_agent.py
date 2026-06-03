"""
FlowStep AI — Base Agent
Abstract base class for all agents in the multi-agent system.
Provides shared infrastructure: LLM reasoning via OpenClaw, action logging
via Notion, and common lifecycle patterns.
"""

from __future__ import annotations

import abc
import logging
from typing import Optional

from agent.openclaw_client import OpenClawClient
from notion.client import NotionClient

logger = logging.getLogger("flowstep.agents.base")


class BaseAgent(abc.ABC):
    """Abstract base agent with OpenClaw reasoning and Notion logging."""

    name: str = "BaseAgent"

    def __init__(
        self,
        notion_client: NotionClient,
        openclaw_client: OpenClawClient,
    ) -> None:
        self.notion_client = notion_client
        self.openclaw_client = openclaw_client

    # ------------------------------------------------------------------
    # Abstract entry point
    # ------------------------------------------------------------------
    @abc.abstractmethod
    async def run(self, input_data: dict) -> dict:
        """Execute the agent's main task.  Subclasses must implement."""
        ...

    # ------------------------------------------------------------------
    # Shared: log an action to the Notion Agent Log DB
    # ------------------------------------------------------------------
    async def log_action(
        self,
        action: str,
        task_page_id: Optional[str] = None,
        status: str = "Success",
        details: str = "",
    ) -> None:
        """Persist an action record in the Notion Agent Log database."""
        try:
            await self.notion_client.log_agent_action(
                agent=self.name,
                action=action,
                task_page_id=task_page_id,
                status=status,
                details=details,
            )
        except Exception as exc:
            logger.error(
                "Error al registrar acción del agente '%s': %s",
                self.name,
                exc,
            )

    # ------------------------------------------------------------------
    # Shared: LLM reasoning via OpenClaw
    # ------------------------------------------------------------------
    async def think(self, prompt: str) -> str:
        """Send *prompt* to the LLM via OpenClaw and return the response.

        In mock mode the OpenClaw client itself returns simulated data,
        so this method works transparently in both modes.
        """
        if self.openclaw_client.is_mock_mode:
            return self._mock_think(prompt)

        try:
            payload = {
                "model": "default",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Eres un agente inteligente de FlowStep AI. "
                            "Responde siempre en español de forma concisa y útil."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            }

            import httpx

            headers = {"Content-Type": "application/json"}
            if self.openclaw_client.gateway_token:
                headers["Authorization"] = (
                    f"Bearer {self.openclaw_client.gateway_token}"
                )

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.openclaw_client.gateway_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code != 200:
                    logger.warning(
                        "OpenClaw devolvió %s — usando respuesta mock",
                        resp.status_code,
                    )
                    return self._mock_think(prompt)

                data = resp.json()
                return data["choices"][0]["message"]["content"]

        except Exception as exc:
            logger.warning(
                "Error en think() — fallback a mock: %s", exc
            )
            return self._mock_think(prompt)

    def _mock_think(self, prompt: str) -> str:
        """Return a deterministic mock reasoning response."""
        return (
            f"[Mock — {self.name}] He analizado la solicitud. "
            "Basado en el contexto proporcionado, procedo con la acción correspondiente."
        )
