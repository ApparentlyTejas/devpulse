# syntax=docker/dockerfile:1.7
# =============================================================================
# DevPulse backend — multi-stage build.
#
# Stage 1 (builder): install Python deps using uv into a virtualenv at /opt/venv.
# Stage 2 (runtime): copy the venv + app, run as non-root user, no build tools.
#
# Build:   docker build -t devpulse-backend .
# Run:     docker run --rm -p 8000:8000 --env-file ../.env devpulse-backend
# =============================================================================

ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.4.27

# -----------------------------------------------------------------------------
# Stage 1: builder
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

# uv installs into /usr/local/bin/uv. We use a pinned version copied from the
# official uv image — avoids running curl-to-shell at build time.
COPY --from=ghcr.io/astral-sh/uv:0.4.27 /uv /usr/local/bin/uv

# Build-time deps that some Python packages need for native extensions.
# Kept here, not in the runtime stage.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Copy only the manifests first so layer cache survives source changes.
COPY pyproject.toml ./
# If uv.lock exists, copy it too. Lockfile makes builds reproducible.
COPY uv.loc[k] ./

# Install runtime deps only (no --extra dev). Bind-mount uv cache for speed.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project --frozen 2>/dev/null \
    || uv sync --no-dev --no-install-project

# Now copy the source and install the project itself.
COPY app ./app
COPY alembic.in[i] ./
COPY alembi[c] ./alembic
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen 2>/dev/null \
    || uv sync --no-dev

# -----------------------------------------------------------------------------
# Stage 2: runtime
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

# Runtime-only system deps. libpq5 for asyncpg/Postgres; curl for HEALTHCHECK.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --home /app --shell /sbin/nologin app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV=/opt/venv

WORKDIR /app

# Copy the prepared virtualenv from the builder stage.
COPY --from=builder /opt/venv /opt/venv
# Copy app source. Owned by the non-root user.
COPY --chown=app:app app ./app
COPY --chown=app:app alembic.in[i] ./
COPY --chown=app:app alembi[c] ./alembic

USER app

EXPOSE 8000

# Liveness probe. Docker / Compose / ECS will use this.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

# Uvicorn workers: 1 here; in prod we set this via env or run gunicorn+uvicorn.
# --proxy-headers because we'll sit behind Nginx in prod.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
