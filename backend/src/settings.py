from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenRouterSettings(BaseSettings):
    api_key: str = ""
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "anthropic/claude-sonnet-4"
    fallback_model: str = "openai/gpt-4o-mini"
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: int = 60


class ClickHouseSettings(BaseSettings):
    host: str = "localhost"
    port: int = 8123
    database: str = "analytics"
    user: str = "default"
    password: str = ""
    secure: bool = False
    seed_on_startup: bool = True


class PostgresSettings(BaseSettings):
    host: str = "localhost"
    port: int = 5432
    database: str = "r2_db2_checkpoints"
    user: str = "r2-db2"
    password: str = "r2_db2_secret"

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}"
        )


class RedisSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    db: int = 0

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class QdrantSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6333
    collection: str = "r2_db2_memory"


class ServerSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1


class LangfuseSettings(BaseSettings):
    enabled: bool = False
    public_key: str = ""
    secret_key: str = ""
    host: str = "https://cloud.langfuse.com"


class GraphSettings(BaseSettings):
    hitl_enabled: bool = False
    max_sql_retries: int = 3


class ReportSettings(BaseModel):
    """Configuration for report output."""

    output_dir: str = "reports"
    default_formats: list[str] = ["pdf", "plotly_html", "csv", "json"]
    pdf_page_size: str = "A4"
    pdf_margin: str = "20mm"
    include_chart_in_pdf: bool = True
    max_chart_width: int = 1200
    max_chart_height: int = 800


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)
    clickhouse: ClickHouseSettings = Field(default_factory=ClickHouseSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    langfuse: LangfuseSettings = Field(default_factory=LangfuseSettings)
    graph: GraphSettings = Field(default_factory=GraphSettings)
    report: ReportSettings = Field(default_factory=ReportSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings()
