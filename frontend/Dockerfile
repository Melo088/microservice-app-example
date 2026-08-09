# syntax=docker/dockerfile:1

FROM node:8-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:8-alpine
RUN apk add --no-cache curl
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY . .
USER node
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -fsS "http://localhost:${PORT:-8080}/" || exit 1
CMD ["npm", "start"]