# syntax=docker/dockerfile:1

FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM node:20-alpine
RUN apk add --no-cache curl
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY package.json server.js routes.js todoController.js ./
USER node
EXPOSE 8082
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -s -o /dev/null "http://localhost:${TODO_API_PORT:-8082}/todos" || exit 1
CMD ["node", "server.js"]