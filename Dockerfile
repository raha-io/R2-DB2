FROM python:3.14.4-slim-bookworm

# Set environment variables to prevent Python from writing bytecode
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

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock /app/

# Install project dependencies (this will create .venv)
RUN uv sync --frozen --no-dev --python $(which python3)

# Copy application code
COPY . /app

# Activate the virtual environment by adding it to PATH
ENV PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV="/app/.venv" \
    PYTHONPATH="/app/src:$PYTHONPATH"

# Cleanup
RUN find /usr/local -type d -name '__pycache__' -exec rm -r {} + 2>/dev/null || true && \
    find /usr/local -type f -name '*.pyc' -delete && \
    find /usr/local -type f -name '*.pyo' -delete

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application using the venv's uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
