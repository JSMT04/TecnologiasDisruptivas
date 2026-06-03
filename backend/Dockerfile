# ──────────────────────────────────────────────────────────────
# FlowStep AI — Backend Dockerfile
# Base: Python 3.12 slim  •  Includes Node.js 22 for MCP server
# ──────────────────────────────────────────────────────────────

FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── System dependencies ─────────────────────────────────────
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg && \
    rm -rf /var/lib/apt/lists/*

# ── Install Node.js 22 (needed for MCP server in future phases) ──
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# ── Install MCP filesystem server globally ──────────────────
RUN npm install -g @modelcontextprotocol/server-filesystem

# ── Create non-root user ────────────────────────────────────
RUN groupadd --gid 1000 appuser && \
    useradd  --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# ── Python dependencies ─────────────────────────────────────
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application source ──────────────────────────────────────
COPY --chown=appuser:appuser . .

# ── Data directory (SQLite lives here) ───────────────────────
RUN mkdir -p /app/data && chown appuser:appuser /app/data

# ── Runtime ──────────────────────────────────────────────────
USER appuser
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
