# ── Stage 1: Build ──
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Install dependencies first (cache layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --extra fastapi

# Copy source and install project
COPY src/ src/
COPY AGENTS.md README.md* ./
RUN uv sync --frozen --no-dev --extra fastapi

# ── Stage 2: Runtime ──
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS runtime

WORKDIR /app

# Install runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY src/ src/
COPY .env.example .env.example

# Set PATH to use venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Default command — run the FastAPI server via uvicorn
CMD ["python", "-m", "uvicorn", "r2-db2.main:app", "--host", "0.0.0.0", "--port", "8000"]
