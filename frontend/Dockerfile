FROM node:20-alpine

RUN mkdir -p /app && chown -R node:node /app
WORKDIR /app

USER node

COPY --chown=node package*.json ./
RUN npm ci

COPY --chown=node . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]
