"""End-to-end API tests for the R2-DB2 analytical pipeline.

Tests the complete flow: question → LangGraph graph → report generation → PDF/CSV download.
Uses FastAPI TestClient with mocked graph to avoid external dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from r2-db2.core.report.models import OutputFormat
from r2-db2.core.report.service import ReportOutputService
from r2-db2.servers.fastapi.graph_routes import router as graph_router


@pytest.fixture
def report_dependency_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock optional plotly + weasyprint deps used by ReportOutputService."""
    plotly_module = ModuleType("plotly")
    plotly_io_module = ModuleType("plotly.io")
    plotly_graph_objects_module = ModuleType("plotly.graph_objects")

    class Figure:  # pragma: no cover - tiny test helper
        def __init__(self, fig_json: dict[str, Any]):
            self.fig_json = fig_json

    def to_html(fig: Figure, full_html: bool = False, include_plotlyjs: bool = False) -> str:  # noqa: ARG001
        _ = fig
        return "<div id='chart'>mock chart</div>"

    plotly_io_module.to_html = to_html  # type: ignore[attr-defined]
    plotly_graph_objects_module.Figure = Figure  # type: ignore[attr-defined]

    setattr(plotly_module, "io", plotly_io_module)
    setattr(plotly_module, "graph_objects", plotly_graph_objects_module)

    weasyprint_module = ModuleType("weasyprint")

    class MockWeasyHTML:  # pragma: no cover - tiny test helper
        def __init__(self, string: str):
            self.string = string

        def write_pdf(self, path: str) -> None:
            Path(path).write_bytes(b"%PDF-1.7\n%mock-pdf\n")

    weasyprint_module.HTML = MockWeasyHTML  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "plotly", plotly_module)
    monkeypatch.setitem(sys.modules, "plotly.io", plotly_io_module)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", plotly_graph_objects_module)
    monkeypatch.setitem(sys.modules, "weasyprint", weasyprint_module)


@pytest.fixture
def app_with_mock_graph() -> tuple[FastAPI, MagicMock]:
    """Create a real FastAPI app mounting graph routes with a mocked graph on state."""
    app = FastAPI()
    app.include_router(graph_router, prefix="/api/v1")

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock()
    mock_graph.aget_state = AsyncMock(return_value=SimpleNamespace(next=[]))

    app.state.graph = mock_graph
    return app, mock_graph


@pytest.fixture
def sample_query_result() -> dict[str, Any]:
    return {
        "columns": ["month", "revenue"],
        "rows": [["2024-01", 50000], ["2024-02", 60000]],
    }


class TestE2EAnalyzePipeline:
    """Tests the full analyze flow and report artifact APIs via FastAPI."""

    def test_analyze_returns_completed_with_report(
        self,
        app_with_mock_graph: tuple[FastAPI, MagicMock],
        sample_query_result: dict[str, Any],
    ) -> None:
        app, mock_graph = app_with_mock_graph

        mock_graph.ainvoke.return_value = {
            "status": "completed",
            "intent": "new_analysis",
            "generated_sql": "SELECT month, SUM(revenue) FROM sales GROUP BY month",
            "query_result": sample_query_result,
            "analysis_summary": "Revenue increased 20% from January to February",
            "report": {
                "report_id": "test-report-123",
                "artifacts": [
                    {"filename": "test-report-123.pdf", "format": "pdf"},
                    {"filename": "test-report-123.csv", "format": "csv"},
                ],
            },
            "messages": [
                {"role": "assistant", "content": "Revenue analysis complete"},
            ],
        }

        client = TestClient(app)
        response = client.post(
            "/api/v1/analyze",
            json={"question": "Show monthly revenue", "user_id": "test-user"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["report"]["report_id"] == "test-report-123"

    @pytest.mark.asyncio
    async def test_full_api_flow_question_to_report_downloads(
        self,
        tmp_path: Path,
        app_with_mock_graph: tuple[FastAPI, MagicMock],
        report_dependency_mocks: None,
        sample_query_result: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Exercise full API-only flow: analyze -> list artifacts -> download CSV/PDF."""
        _ = report_dependency_mocks
        app, mock_graph = app_with_mock_graph
        report_id = "test-report-123"

        # Arrange generated artifacts on disk (same output consumed by report routes)
        service = ReportOutputService(base_output_dir=tmp_path)
        await service.generate_report(
            report_id=report_id,
            query_result=sample_query_result,
            analysis_text="Revenue increased 20% from January to February",
            output_formats=[OutputFormat.PDF, OutputFormat.CSV],
            metadata={"query": "SELECT month, SUM(revenue) FROM sales GROUP BY month"},
        )

        # Point API report endpoints to temp output directory
        monkeypatch.setenv("REPORT__OUTPUT_DIR", str(tmp_path))

        # Arrange mocked graph result that references generated report
        mock_graph.ainvoke.return_value = {
            "status": "completed",
            "intent": "new_analysis",
            "generated_sql": "SELECT month, SUM(revenue) FROM sales GROUP BY month",
            "query_result": sample_query_result,
            "analysis_summary": "Revenue increased 20% from January to February",
            "report": {
                "report_id": report_id,
                "artifacts": [
                    {"filename": f"{report_id}.pdf", "format": "pdf"},
                    {"filename": f"{report_id}.csv", "format": "csv"},
                ],
            },
            "messages": [{"role": "assistant", "content": "Revenue analysis complete"}],
        }

        client = TestClient(app)

        # Step 1: analyze
        analyze_response = client.post(
            "/api/v1/analyze",
            json={"question": "Show monthly revenue", "user_id": "test-user"},
        )
        assert analyze_response.status_code == 200
        analyze_data = analyze_response.json()
        assert analyze_data["status"] == "completed"
        assert analyze_data["report"]["report_id"] == report_id

        # Step 2: list artifacts
        artifacts_response = client.get(f"/api/v1/reports/{report_id}")
        assert artifacts_response.status_code == 200
        artifacts_data = artifacts_response.json()
        filenames = {item["filename"] for item in artifacts_data["artifacts"]}
        assert f"{report_id}.pdf" in filenames
        assert f"{report_id}.csv" in filenames

        # Step 3: download CSV
        csv_response = client.get(f"/api/v1/reports/{report_id}/{report_id}.csv")
        assert csv_response.status_code == 200
        assert csv_response.headers["content-type"].startswith("text/csv")
        assert "month,revenue" in csv_response.text
        assert "2024-01,50000" in csv_response.text

        # Step 4: download PDF
        pdf_response = client.get(f"/api/v1/reports/{report_id}/{report_id}.pdf")
        assert pdf_response.status_code == 200
        assert pdf_response.headers["content-type"].startswith("application/pdf")
        assert pdf_response.content.startswith(b"%PDF")

    @pytest.mark.asyncio
    async def test_report_generation_creates_pdf_and_csv(
        self,
        tmp_path: Path,
        report_dependency_mocks: None,
        sample_query_result: dict[str, Any],
    ) -> None:
        _ = report_dependency_mocks
        service = ReportOutputService(base_output_dir=tmp_path)
        report_id = "test-report-123"

        output = await service.generate_report(
            report_id=report_id,
            query_result=sample_query_result,
            analysis_text="Revenue increased 20% from January to February",
            output_formats=[OutputFormat.PDF, OutputFormat.CSV],
            metadata={"query": "SELECT month, SUM(revenue) FROM sales GROUP BY month"},
        )

        pdf_artifact = output.get_artifact(OutputFormat.PDF)
        csv_artifact = output.get_artifact(OutputFormat.CSV)

        assert pdf_artifact is not None
        assert pdf_artifact.path.exists()
        assert pdf_artifact.path.stat().st_size > 0
        assert pdf_artifact.path.read_bytes().startswith(b"%PDF")

        assert csv_artifact is not None
        assert csv_artifact.path.exists()
        csv_text = csv_artifact.path.read_text(encoding="utf-8")
        assert "month,revenue" in csv_text
        assert "2024-01,50000" in csv_text
        assert "2024-02,60000" in csv_text

    @pytest.mark.asyncio
    async def test_report_list_artifacts_endpoint(
        self,
        tmp_path: Path,
        app_with_mock_graph: tuple[FastAPI, MagicMock],
        report_dependency_mocks: None,
        sample_query_result: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _ = report_dependency_mocks
        app, _mock_graph = app_with_mock_graph

        report_id = "test-report-123"
        service = ReportOutputService(base_output_dir=tmp_path)
        await service.generate_report(
            report_id=report_id,
            query_result=sample_query_result,
            analysis_text="Revenue analysis complete",
            output_formats=[OutputFormat.PDF, OutputFormat.CSV],
        )

        monkeypatch.setenv("REPORT__OUTPUT_DIR", str(tmp_path))

        client = TestClient(app)
        response = client.get(f"/api/v1/reports/{report_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["report_id"] == report_id
        filenames = {item["filename"] for item in data["artifacts"]}
        assert f"{report_id}.pdf" in filenames
        assert f"{report_id}.csv" in filenames

    @pytest.mark.asyncio
    async def test_report_download_csv_endpoint(
        self,
        tmp_path: Path,
        app_with_mock_graph: tuple[FastAPI, MagicMock],
        report_dependency_mocks: None,
        sample_query_result: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _ = report_dependency_mocks
        app, _mock_graph = app_with_mock_graph

        report_id = "test-report-123"
        service = ReportOutputService(base_output_dir=tmp_path)
        await service.generate_report(
            report_id=report_id,
            query_result=sample_query_result,
            analysis_text="Revenue analysis complete",
            output_formats=[OutputFormat.CSV],
        )

        monkeypatch.setenv("REPORT__OUTPUT_DIR", str(tmp_path))

        client = TestClient(app)
        response = client.get(f"/api/v1/reports/{report_id}/data.csv")

        # Service writes <report_id>.csv, so use real generated filename
        if response.status_code == 404:
            response = client.get(f"/api/v1/reports/{report_id}/{report_id}.csv")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "month,revenue" in response.text
        assert "2024-01,50000" in response.text

    @pytest.mark.asyncio
    async def test_report_download_pdf_endpoint(
        self,
        tmp_path: Path,
        app_with_mock_graph: tuple[FastAPI, MagicMock],
        report_dependency_mocks: None,
        sample_query_result: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _ = report_dependency_mocks
        app, _mock_graph = app_with_mock_graph

        report_id = "test-report-123"
        service = ReportOutputService(base_output_dir=tmp_path)
        await service.generate_report(
            report_id=report_id,
            query_result=sample_query_result,
            analysis_text="Revenue analysis complete",
            output_formats=[OutputFormat.PDF],
        )

        monkeypatch.setenv("REPORT__OUTPUT_DIR", str(tmp_path))

        client = TestClient(app)
        response = client.get(f"/api/v1/reports/{report_id}/report.pdf")

        # Service writes <report_id>.pdf, so use real generated filename
        if response.status_code == 404:
            response = client.get(f"/api/v1/reports/{report_id}/{report_id}.pdf")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        assert response.content.startswith(b"%PDF")
