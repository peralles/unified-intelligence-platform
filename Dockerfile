# syntax=docker/dockerfile:1
# Multi-stage build: keeps the final image slim (~1 GB with faster-whisper model).

# ─── Stage 1: build main venv ────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# System build deps (neonize pulls libstdc++ at runtime; faster-whisper needs nothing at build)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy

# Cache deps layer: copy lockfiles first
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy source and do final install
COPY integrator/ ./integrator/
RUN uv sync --frozen --no-dev

# ─── Stage 2: build bridge venv ──────────────────────────────────────────────
FROM python:3.12-slim AS bridge-builder

WORKDIR /bridge

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy

COPY bridges/whatsapp-neonize/pyproject.toml bridges/whatsapp-neonize/uv.lock ./
RUN uv sync --frozen --no-install-project

COPY bridges/whatsapp-neonize/ ./
RUN uv sync --frozen

# ─── Stage 3: final runtime image ────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Unified Intelligence Platform — Integrator"
LABEL org.opencontainers.image.description="MCP server + WhatsApp bridge + admin console"

# Runtime system deps:
#   ffmpeg        — audio decoding for faster-whisper transcription
#   libsndfile1   — libsndfile used by soundfile (faster-whisper dep)
#   ca-certificates — TLS for outbound Google/WhatsApp connections
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy built venvs from builders
COPY --from=builder /app/.venv ./.venv
COPY --from=bridge-builder /bridge/.venv ./bridges/whatsapp-neonize/.venv

# Copy all source
COPY --from=builder /app/integrator ./integrator
COPY . .

# Persistent data dirs — mount these as a Docker volume in production
RUN mkdir -p \
    /app/data/logs \
    /app/data/admin \
    /app/data/tokens \
    /app/data/whatsapp \
    /app/credentials

# ─── Environment defaults ────────────────────────────────────────────────────
# Override INTEGRATOR_SERVICE_HOST via env for local dev (default stays 0.0.0.0 in container)
ENV INTEGRATOR_SERVICE_HOST=0.0.0.0
ENV INTEGRATOR_SERVICE_PORT=17320
# Disable macOS LaunchAgent-related codepaths on Linux
ENV INTEGRATOR_SKIP_MACOS_SERVICE=1
# Path used by the bridge process to locate the runtime config
ENV INTEGRATOR_ADMIN_RUNTIME_FILE=/app/data/admin/runtime.json

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 17320

VOLUME ["/app/data", "/app/credentials"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:17320/health').read()"

ENTRYPOINT ["uv", "run", "integrator", "serve-http", "--host", "0.0.0.0", "--port", "17320"]
