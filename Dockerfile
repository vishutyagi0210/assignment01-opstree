# ========================
FROM maven:3.9.6-eclipse-temurin-21 AS builder

WORKDIR /app

COPY ./pom.xml .
RUN mvn dependency:go-offline

COPY ./src ./src
RUN mvn clean package -DskipTests

# ========================
FROM eclipse-temurin:21-jre-alpine AS base

WORKDIR /app

RUN addgroup -S appusers && \
    adduser -S -G appusers opstree && \
    chown -R opstree:appusers /app

USER opstree

EXPOSE 8080

# ========================
FROM base AS production

ARG GIT_SHA=unknown \
    APP_VERSION=unknown

LABEL org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.vendor="OpsTree"

COPY --from=builder --chown=opstree:appusers /app/target/orch-app-*-SNAPSHOT.jar app.jar

CMD ["java", "-Xms256m", "-Xmx512m", "-XX:+UseContainerSupport", "-jar", "app.jar"]