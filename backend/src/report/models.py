"""Report output models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class OutputFormat(str, Enum):
    """Supported report output formats."""

    PDF = "pdf"
    PLOTLY_HTML = "plotly_html"
    CSV = "csv"
    PARQUET = "parquet"
    JSON = "json"


@dataclass
class ReportArtifact:
    """A single generated report file."""

    format: OutputFormat
    path: Path
    filename: str
    size_bytes: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportOutput:
    """Collection of all generated report artifacts."""

    report_id: str
    output_dir: Path
    artifacts: list[ReportArtifact] = field(default_factory=list)

    def get_artifact(self, fmt: OutputFormat) -> ReportArtifact | None:
        """Get artifact by format."""
        for artifact in self.artifacts:
            if artifact.format == fmt:
                return artifact
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API response."""
        return {
            "report_id": self.report_id,
            "output_dir": str(self.output_dir),
            "artifacts": [
                {
                    "format": artifact.format.value,
                    "path": str(artifact.path),
                    "filename": artifact.filename,
                    "size_bytes": artifact.size_bytes,
                    "metadata": artifact.metadata,
                }
                for artifact in self.artifacts
            ],
        }
