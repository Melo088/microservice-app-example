# syntax=docker/dockerfile:1

FROM maven:3.9-eclipse-temurin-8 AS builder
WORKDIR /build
COPY pom.xml .
RUN mvn -B dependency:resolve dependency:resolve-plugins
COPY src ./src
RUN mvn -B clean package -DskipTests

FROM eclipse-temurin:8-jre-alpine
RUN apk add --no-cache curl && \
    addgroup -S app && adduser -S app -G app
WORKDIR /app
COPY --from=builder /build/target/users-api-0.0.1-SNAPSHOT.jar ./users-api.jar
USER app
EXPOSE 8083
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=4 \
  CMD curl -f "http://localhost:${SERVER_PORT:-8083}/health" || exit 1
ENTRYPOINT ["java", "-jar", "users-api.jar"]