# Open WebUI Local Setup

## 1. Overview

- Open WebUI v0.8.5 is running locally via Docker
- Accessible at http://localhost:3000
- Part of the R2-DB2 analytical agent stack

## 2. Architecture

- Open WebUI container image: `ghcr.io/open-webui/open-webui:v0.8.5`
- Host-to-container port mapping: `3000:8080`
- Persistent volume mapping: `open-webui:/app/backend/data`
- Connected to the `r2-db2-net` bridge network shared by R2-DB2 services

## 3. Docker Compose Configuration

Service definition added to `docker-compose.yml`:

```yaml
openwebui:
  image: ghcr.io/open-webui/open-webui:v0.8.5
  ports:
    - "3000:8080"
  volumes:
    - open-webui:/app/backend/data
  networks:
    - r2-db2-net
  restart: unless-stopped
```

## 4. Quick Start Commands

```bash
# Pull the image
docker pull ghcr.io/open-webui/open-webui:v0.8.5

# Start only Open WebUI without affecting other services
docker compose up -d --no-deps --no-build openwebui

# Check status
docker ps --filter "name=openwebui"

# View logs
docker compose logs --tail=50 openwebui

# Stop Open WebUI only
docker compose stop openwebui

# Remove Open WebUI container data persists in volume
docker compose rm -f openwebui
```

## 5. Verification Steps

```bash
# Port check
ss -tlnp | grep :3000

# HTTP health check
curl -s -o /dev/null -w "HTTP_STATUS: %{http_code}\n" http://localhost:3000/

# Browser access
# Navigate to http://localhost:3000
```

## 6. First-Time Setup

- On first access, Open WebUI prompts for admin account creation
- No external LLM API key is required to start; add one later in Settings if needed
- Data persists in the `open-webui` Docker volume

## 7. Troubleshooting

- **Port 3000 occupied**: Change the host port in `docker-compose.yml`, for example `"3001:8080"`
- **Container starts but port not published**: Recreate with:
  ```bash
  docker compose up -d --no-deps --no-build --force-recreate openwebui
  ```
- **DNS issues during pull**: Docker must be able to reach `ghcr.io`; if behind a proxy, configure Docker daemon proxy settings
- **Data reset**: Remove the volume with:
  ```bash
  docker volume rm open-webui
  ```
  Caution: this destroys all Open WebUI data

## 8. Service Ports Summary R2-DB2 Stack

| Service | Port(s) | Purpose |
|---------|---------|---------|
| app | 8000 | R2-DB2 FastAPI backend |
| clickhouse | 8123, 9000 | Analytics database |
| postgres | 5432 | Schema and metadata catalog |
| redis | 6379 | Caching layer |
| qdrant | 6333, 6334 | Vector search |
| **openwebui** | **3000** | **Web UI frontend** |
