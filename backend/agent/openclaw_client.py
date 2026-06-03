"""
FlowStep AI — OpenClaw Agent Client
Robust client supporting httpx calls to OpenClaw Gateway and an intelligent mock fallback.
"""

from __future__ import annotations

import os
import uuid
import logging
import httpx
from datetime import datetime, timezone

logger = logging.getLogger("flowstep.openclaw")


class OpenClawClient:
    """Client for communicating with the OpenClaw Gateway."""

    def __init__(self, gateway_url: str = "http://openclaw:18789"):
        self.gateway_url = gateway_url
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.gateway_token = os.getenv("OPENCLAW_GATEWAY_TOKEN", "flowstep-secret-token-123")
        # Automatic mock mode enabled if the API key is missing, empty, or the default pending placeholder
        self.is_mock_mode = (
            not self.api_key
            or "PENDIENTE" in self.api_key
            or self.api_key.startswith("sk-ant-PENDIENTE")
        )

        if self.is_mock_mode:
            logger.info("OpenClawClient running in AUTOMATIC MOCK MODE (no valid Anthropic API key detected).")

    async def health_check(self) -> dict:
        """Check if OpenClaw Gateway is reachable."""
        if self.is_mock_mode:
            return {"status": "ok", "mode": "mock", "gateway_connected": False}

        headers = {}
        if self.gateway_token:
            headers["Authorization"] = f"Bearer {self.gateway_token}"

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.gateway_url}/api/status", headers=headers)
                if response.status_code == 200:
                    return {"status": "ok", "mode": "real", "gateway_connected": True}
                return {"status": "error", "mode": "real", "gateway_connected": False, "detail": f"Status {response.status_code}"}
        except Exception as exc:
            logger.warning(f"Failed to reach OpenClaw Gateway at {self.gateway_url}: {exc}")
            return {"status": "error", "mode": "real", "gateway_connected": False, "detail": str(exc)}

    async def run_triage(
        self, tasks: list[str], context: dict | None = None
    ) -> dict:
        """Send tasks to OpenClaw for triage analysis."""
        if self.is_mock_mode:
            return self._generate_mock_triage(tasks)

        # Build prompt payload for OpenClaw Gateway v1 chat completions
        system_prompt = (
            "Eres FlowStep AI. Analiza la lista de tareas del usuario y responde únicamente con un "
            "JSON que cumpla estrictamente el esquema dado. No incluyas comentarios ni marcas markdown adicionales."
        )

        input_tasks_str = "\n".join([f"- {task}" for task in tasks])
        user_content = (
            f"Analiza las siguientes tareas del usuario:\n\n{input_tasks_str}\n\n"
            "Esquema JSON esperado:\n"
            "{\n"
            '  "tasks": [\n'
            "    {\n"
            '      "id": "UUID",\n'
            '      "title": "string (máx 80 chars)",\n'
            '      "urgencia": "alta|media|baja",\n'
            '      "esfuerzo": "bajo|medio|alto",\n'
            '      "tipo": "archivo|código|web|comunicación|otro",\n'
            '      "dependencias": [],\n'
            '      "order_index": 1,\n'
            '      "expected_path": "string|null",\n'
            '      "instrucciones": "string (instrucciones concisas, máx 200 chars)"\n'
            "    }\n"
            "  ],\n"
            '  "tiempo_total_estimado_min": 120,\n'
            '  "advertencia": "string|null"\n'
            "}"
        )

        payload = {
            "model": "default",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1
        }

        headers = {"Content-Type": "application/json"}
        if self.gateway_token:
            headers["Authorization"] = f"Bearer {self.gateway_token}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.gateway_url}/v1/chat/completions",
                    json=payload,
                    headers=headers
                )
                if response.status_code != 200:
                    logger.error(f"OpenClaw returned error status: {response.status_code} - {response.text}")
                    # Fallback to mock if API returns error so user has robust UX
                    return self._generate_mock_triage(tasks, warning="Nota: Respuesta simulada por fallo del Gateway AI.")

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                # Parse content as JSON
                import json
                # Clean up potential markdown wrappers
                content_clean = content.strip().lstrip("```json").rstrip("```").strip()
                return json.loads(content_clean)
        except Exception as exc:
            logger.error(f"Exception during OpenClaw API call: {exc}")
            return self._generate_mock_triage(tasks, warning="Nota: Respuesta simulada por desconexión del Gateway AI.")

    def _generate_mock_triage(self, tasks: list[str], warning: str | None = None) -> dict:
        """Intelligently mock the LLM triage based on text analysis."""
        mock_tasks = []
        total_time = 0

        for idx, task_text in enumerate(tasks, start=1):
            task_id = str(uuid.uuid4())
            text_lower = task_text.lower()

            # Smart type inference
            if any(ext in text_lower for ext in [".py", ".js", ".html", ".css", "code", "código", "programar", "desarrollar", "función", "clase"]):
                task_type = "código"
                expected_path = "src/app.py" if ".py" in text_lower else "src/index.js"
                if ".html" in text_lower:
                    expected_path = "index.html"
                elif ".css" in text_lower:
                    expected_path = "src/index.css"
            elif any(kwd in text_lower for kwd in ["crear archivo", "escribir archivo", "documento", "archivo", "txt", "readme", "markdown", "crear carpeta"]):
                task_type = "archivo"
                expected_path = "README.md" if "readme" in text_lower else "documento.txt"
            elif any(kwd in text_lower for kwd in ["web", "buscar", "search", "url", "investigar", "página", "link", "google", "chrome"]):
                task_type = "web"
                expected_path = None
            elif any(kwd in text_lower for kwd in ["correo", "email", "escribir a", "slack", "discord", "mensajear", "llamar", "reunión", "avisar"]):
                task_type = "comunicación"
                expected_path = None
            else:
                task_type = "otro"
                expected_path = None

            # Urgent / Effort inference
            urgency = "alta" if any(kwd in text_lower for kwd in ["urgente", "ya", "rápido", "asap", "importante", "hoy", "primero"]) else "media"
            effort = "bajo"
            task_time = 15

            if any(kwd in text_lower for kwd in ["largo", "difícil", "complejo", "mucho", "horas", "grande"]):
                effort = "alto"
                task_time = 150
            elif any(kwd in text_lower for kwd in ["medio", "regular", "normal", "diseñar"]):
                effort = "medio"
                task_time = 60

            total_time += task_time

            # Generate instructions
            instructions = f"Pasos para: {task_text[:60]}... Identificado como {task_type}. "
            if task_type == "código":
                instructions += f"Crea/modifica el archivo de código en la ruta '{expected_path}'."
            elif task_type == "archivo":
                instructions += f"Crea y dale formato al archivo en '{expected_path}'."
            elif task_type == "web":
                instructions += "Consulta las fuentes necesarias en la web e integra tus hallazgos."
            elif task_type == "comunicación":
                instructions += "Redacta el mensaje correspondiente y envíalo a tu destinatario."
            else:
                instructions += "Realiza los pasos indicados y márcalo como completado en la interfaz."

            mock_tasks.append({
                "id": task_id,
                "title": task_text[:75] + ("..." if len(task_text) > 75 else ""),
                "urgency": urgency,
                "effort": effort,
                "tipo": task_type,
                "dependencias": [],
                "order_index": idx,
                "expected_path": expected_path,
                "instrucciones": instructions[:200]
            })

        return {
            "tasks": mock_tasks,
            "tiempo_total_estimado_min": total_time,
            "advertencia": warning
        }

    async def verify_file(self, path: str, check_type: str) -> dict:
        """Request file verification via MCP through OpenClaw."""
        # This will be fully implemented in Phase C
        now = datetime.now(tz=timezone.utc).isoformat()
        return {
            "verificado": True,
            "detalle": f"Mock de verificación exitoso para '{path}' del tipo '{check_type}'",
            "timestamp": now
        }

