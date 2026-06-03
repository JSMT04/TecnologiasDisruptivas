FROM node:22-alpine

WORKDIR /app

# Install OpenClaw globally
RUN npm install -g openclaw@latest

# Install MCP filesystem server
RUN npm install -g @modelcontextprotocol/server-filesystem

# Create state and data directories
RUN mkdir -p /home/node/.openclaw && chown -R node:node /home/node/.openclaw
RUN mkdir -p /app/data && chown -R node:node /app/data

COPY --chown=node openclaw.json /home/node/.openclaw/openclaw.json

USER node

EXPOSE 18789
CMD ["openclaw", "gateway", "run"]
