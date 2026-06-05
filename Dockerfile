# syntax=docker/dockerfile:1.7
# ─────────────────────────────────────────────────────────────────────────────
# Smallest viable base: python:3.12-slim-bookworm (Debian Bookworm minimal).
# Alpine is NOT viable — neonize and CTranslate2 require glibc (not musl).
# ─────────────────────────────────────────────────────────────────────────────

ARG UV_VERSION=0.8.17
ARG PYTHON_IMAGE=python:3.12-slim-bookworm

# Pinned uv stage — never use ${UV_VERSION} in COPY --from image refs.
# Coolify injects bare ARG lines without values; empty UV_VERSION breaks BuildKit.
FROM ghcr.io/astral-sh/uv:0.8.17 AS uv-bin

# ─── Stage 1: build main venv ────────────────────────────────────────────────
FROM ${PYTHON_IMAGE} AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv-bin /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_NO_CACHE=1

# Dependency layer — only invalidated when lockfiles change
# README.md required by hatchling when installing the project (pyproject readme field)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

# Source layer
COPY integrator/ ./integrator/
RUN uv sync --frozen --no-dev

# ─── Stage 2: build bridge venv (isolated protobuf 7.x) ──────────────────────
FROM ${PYTHON_IMAGE} AS bridge-builder

WORKDIR /bridge

COPY --from=uv-bin /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_NO_CACHE=1

COPY bridges/whatsapp-neonize/pyproject.toml bridges/whatsapp-neonize/uv.lock ./
RUN uv sync --frozen --no-install-project

COPY bridges/whatsapp-neonize/ ./
RUN uv sync --frozen

# ─── Stage 3: minimal runtime image ─────────────────────────────────────────
FROM ${PYTHON_IMAGE}

LABEL org.opencontainers.image.title="Unified Intelligence Platform — Integrator"
LABEL org.opencontainers.image.description="MCP server + WhatsApp bridge + admin console"
LABEL org.opencontainers.image.source="https://github.com/peralles/unified-intelligence-platform"

# Runtime deps only — no build tools in final image:
#   ffmpeg        — audio decoding for faster-whisper transcription
#   libsndfile1   — soundfile dependency of faster-whisper
#   ca-certificates — TLS for outbound Google API / WhatsApp connections
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# uv kept for local dev fallback; Docker bridge uses bridges/whatsapp-neonize/.venv/bin/python
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

WORKDIR /app

# Copy pre-built venvs
COPY --from=builder        /app/.venv                              ./.venv
COPY --from=bridge-builder /bridge/.venv                           ./bridges/whatsapp-neonize/.venv

# Copy application source
COPY --from=builder /app/integrator ./integrator
COPY . .

# Non-root user — reduces attack surface if a dependency is compromised
RUN groupadd --gid 1000 app && \
    useradd  --uid 1000 --gid app --no-create-home --shell /sbin/nologin app

# Pre-create data dirs and assign ownership so Docker seeds named volumes
# with the correct permissions on first mount
RUN mkdir -p \
        /app/data/logs \
        /app/data/admin \
        /app/data/tokens \
        /app/data/whatsapp \
        /app/credentials \
    && chown -R app:app /app

USER app

# ─── Runtime environment ─────────────────────────────────────────────────────
ENV INTEGRATOR_SERVICE_HOST=0.0.0.0 \
    INTEGRATOR_SERVICE_PORT=17320 \
    INTEGRATOR_SKIP_MACOS_SERVICE=1 \
    INTEGRATOR_ADMIN_RUNTIME_FILE=/app/data/admin/runtime.json \
    PATH="/app/.venv/bin:$PATH" \
    # uv: don't sync at runtime (venv already built), no cache writes
    UV_FROZEN=1 \
    UV_NO_CACHE=1 \
    # Python: no .pyc files (read-only filesystem safe), unbuffered stdout
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 17320

VOLUME ["/app/data", "/app/credentials"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:17320/health').read()"

# Call the venv binary directly — avoids uv resolver overhead at startup
ENTRYPOINT ["/app/.venv/bin/integrator", "serve-http", \
            "--host", "0.0.0.0", "--port", "17320"]
