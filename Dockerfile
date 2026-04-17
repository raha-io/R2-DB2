# Build argument for the public image registry (e.g., ghcr.io, docker.io)
ARG PUBLIC_IMAGE_REGISTRY=docker.io
FROM ${PUBLIC_IMAGE_REGISTRY}/python:3.13.9-slim-bookworm

# Set environment variables to prevent Python from writing bytecode
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install minimal dependencies
ARG LOCAL_ARTIFACTORY_ADDRESS
ENV LOCAL_ARTIFACTORY_ADDRESS=$LOCAL_ARTIFACTORY_ADDRESS

# Configure apt to use local Artifactory
RUN rm -f /etc/apt/sources.list.d/* || true && \
    \
    linux_version_codename=$(cat /etc/os-release | grep -w VERSION_CODENAME | cut -d'=' -f2) && \
    linux_version_distro=$(cat /etc/os-release | grep -w ID | cut -d'=' -f2) && \
    \
    echo "deb https://${LOCAL_ARTIFACTORY_ADDRESS}/artifactory/${linux_version_distro}-remote ${linux_version_codename} main" > /etc/apt/sources.list && \
    echo "deb https://${LOCAL_ARTIFACTORY_ADDRESS}/artifactory/${linux_version_distro}-remote ${linux_version_codename}-updates main" >> /etc/apt/sources.list && \
    echo "deb https://${LOCAL_ARTIFACTORY_ADDRESS}/artifactory/${linux_version_distro}-security-remote ${linux_version_codename}-security main" >> /etc/apt/sources.list

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

# Install uv with custom PIP_REPO_URL
ARG PIP_REPO_URL
RUN pip install --no-cache-dir --index-url=${PIP_REPO_URL} uv

# Disable uv's managed Python downloads — use the system Python from the base image.
# This avoids any network calls to github.com/astral-sh/python-build-standalone.
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
