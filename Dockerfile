# ── Stage 1: build the Svelte frontend ──
FROM node:22-alpine AS frontend-builder

RUN corepack enable && corepack prepare pnpm@10.33.0 --activate

WORKDIR /frontend

# Install deps with cached store; only re-installs when manifests change.
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm run build


# ── Stage 2: Python runtime ──
FROM python:3.14.4-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libglib2.0-0 \
    libffi-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install uv from the official image (pinned for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /uvx /usr/local/bin/

# Disable uv's managed Python downloads — use the system Python from the base image.
ENV UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock /app/
RUN uv sync --frozen --no-dev --python $(which python3)

COPY backend/ /app/

# Copy the built frontend assets from the Node stage. The application mounts
# this directory at "/" via FastAPI StaticFiles.
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

ENV PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV="/app/.venv" \
    PYTHONPATH="/app/src:$PYTHONPATH"

RUN find /usr/local -type d -name '__pycache__' -exec rm -r {} + 2>/dev/null || true && \
    find /usr/local -type f -name '*.pyc' -delete && \
    find /usr/local -type f -name '*.pyo' -delete

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
