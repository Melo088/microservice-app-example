# syntax=docker/dockerfile:1

FROM golang:1.24-alpine AS builder
WORKDIR /src
COPY . .
RUN go mod init github.com/bortizf/microservice-app-example/auth-api && \
    go mod tidy && \
    CGO_ENABLED=0 GOOS=linux go build -o /out/auth-api .

FROM alpine:3.20
RUN apk add --no-cache ca-certificates curl && \
    addgroup -S app && adduser -S app -G app
WORKDIR /app
COPY --from=builder /out/auth-api ./auth-api
USER app
EXPOSE 8081
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -fsS "http://localhost:${AUTH_API_PORT:-8081}/version" || exit 1
ENTRYPOINT ["./auth-api"]