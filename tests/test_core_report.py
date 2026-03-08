"""Tests for core/report/models.py and core/report/service.py."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from r2-db2.core.report.models import OutputFormat, ReportArtifact, ReportOutput
from r2-db2.core.report.service import ReportOutputService


class TestOutputFormat:
    """Tests for OutputFormat enum."""

    def test_output_format_values(self) -> None:
        """Test that all expected formats are defined."""
        assert OutputFormat.PDF.value == "pdf"
        assert OutputFormat.PLOTLY_HTML.value == "plotly_html"
        assert OutputFormat.CSV.value == "csv"
        assert OutputFormat.PARQUET.value == "parquet"
        assert OutputFormat.JSON.value == "json"


class TestReportArtifact:
    """Tests for ReportArtifact dataclass."""

    def test_instantiation_with_all_fields(self, tmp_path: Path) -> None:
        """Test ReportArtifact creation with all fields."""
        artifact = ReportArtifact(
            format=OutputFormat.JSON,
            path=tmp_path / "test.json",
            filename="test.json",
            size_bytes=1024,
            metadata={"key": "value"},
        )

        assert artifact.format == OutputFormat.JSON
        assert artifact.path == tmp_path / "test.json"
        assert artifact.filename == "test.json"
        assert artifact.size_bytes == 1024
        assert artifact.metadata == {"key": "value"}

    def test_instantiation_with_defaults(self, tmp_path: Path) -> None:
        """Test ReportArtifact creation with default metadata."""
        artifact = ReportArtifact(
            format=OutputFormat.CSV,
            path=tmp_path / "test.csv",
            filename="test.csv",
            size_bytes=512,
        )

        assert artifact.format == OutputFormat.CSV
        assert artifact.metadata == {}

    def test_metadata_default_is_empty_dict(self, tmp_path: Path) -> None:
        """Test that metadata defaults to empty dict, not mutable default."""
        artifact1 = ReportArtifact(
            format=OutputFormat.JSON,
            path=tmp_path / "test1.json",
            filename="test1.json",
            size_bytes=100,
        )
        artifact2 = ReportArtifact(
            format=OutputFormat.CSV,
            path=tmp_path / "test2.csv",
            filename="test2.csv",
            size_bytes=200,
        )

        # Modifying one should not affect the other
        artifact1.metadata["key1"] = "value1"
        assert artifact1.metadata == {"key1": "value1"}
        assert artifact2.metadata == {}


class TestReportOutput:
    """Tests for ReportOutput dataclass."""

    def test_instantiation(self, tmp_path: Path) -> None:
        """Test ReportOutput creation."""
        output = ReportOutput(
            report_id="test-report-123",
            output_dir=tmp_path / "reports" / "test-report-123",
            artifacts=[],
        )

        assert output.report_id == "test-report-123"
        assert output.output_dir == tmp_path / "reports" / "test-report-123"
        assert output.artifacts == []

    def test_get_artifact_found(self, tmp_path: Path) -> None:
        """Test get_artifact returns matching artifact."""
        artifact = ReportArtifact(
            format=OutputFormat.JSON,
            path=tmp_path / "test.json",
            filename="test.json",
            size_bytes=100,
        )
        output = ReportOutput(
            report_id="test-report",
            output_dir=tmp_path,
            artifacts=[artifact],
        )

        result = output.get_artifact(OutputFormat.JSON)
        assert result is artifact

    def test_get_artifact_not_found(self, tmp_path: Path) -> None:
        """Test get_artifact returns None for non-existent format."""
        artifact = ReportArtifact(
            format=OutputFormat.CSV,
            path=tmp_path / "test.csv",
            filename="test.csv",
            size_bytes=100,
        )
        output = ReportOutput(
            report_id="test-report",
            output_dir=tmp_path,
            artifacts=[artifact],
        )

        result = output.get_artifact(OutputFormat.JSON)
        assert result is None

    def test_get_artifact_empty_list(self, tmp_path: Path) -> None:
        """Test get_artifact with empty artifacts list."""
        output = ReportOutput(
            report_id="test-report",
            output_dir=tmp_path,
            artifacts=[],
        )

        result = output.get_artifact(OutputFormat.JSON)
        assert result is None

    def test_to_dict(self, tmp_path: Path) -> None:
        """Test ReportOutput serialization to dict."""
        artifact = ReportArtifact(
            format=OutputFormat.JSON,
            path=tmp_path / "test.json",
            filename="test.json",
            size_bytes=1024,
            metadata={"key": "value"},
        )
        output = ReportOutput(
            report_id="test-report-123",
            output_dir=tmp_path / "reports" / "test-report-123",
            artifacts=[artifact],
        )

        result = output.to_dict()

        assert result["report_id"] == "test-report-123"
        assert result["output_dir"] == str(tmp_path / "reports" / "test-report-123")
        assert len(result["artifacts"]) == 1
        assert result["artifacts"][0]["format"] == "json"
        assert result["artifacts"][0]["path"] == str(tmp_path / "test.json")
        assert result["artifacts"][0]["filename"] == "test.json"
        assert result["artifacts"][0]["size_bytes"] == 1024
        assert result["artifacts"][0]["metadata"] == {"key": "value"}

    def test_to_dict_empty_artifacts(self, tmp_path: Path) -> None:
        """Test ReportOutput serialization with no artifacts."""
        output = ReportOutput(
            report_id="test-report",
            output_dir=tmp_path,
            artifacts=[],
        )

        result = output.to_dict()

        assert result["report_id"] == "test-report"
        assert result["output_dir"] == str(tmp_path)
        assert result["artifacts"] == []


class TestReportOutputServiceInit:
    """Tests for ReportOutputService initialization."""

    def test_init_with_default_dir(self, tmp_path: Path) -> None:
        """Test service initialization with default output directory."""
        service = ReportOutputService()

        assert service.base_output_dir == Path("./reports")

    def test_init_with_custom_dir_string(self, tmp_path: Path) -> None:
        """Test service initialization with custom directory as string."""
        custom_dir = str(tmp_path / "custom_reports")
        service = ReportOutputService(base_output_dir=custom_dir)

        assert service.base_output_dir == Path(custom_dir)
        assert service.base_output_dir.exists()

    def test_init_with_custom_dir_path(self, tmp_path: Path) -> None:
        """Test service initialization with custom directory as Path."""
        custom_dir = tmp_path / "custom_reports"
        service = ReportOutputService(base_output_dir=custom_dir)

        assert service.base_output_dir == custom_dir
        assert service.base_output_dir.exists()

    def test_init_creates_directory(self, tmp_path: Path) -> None:
        """Test that service creates output directory if it doesn't exist."""
        new_dir = tmp_path / "new_reports"
        service = ReportOutputService(base_output_dir=new_dir)

        assert new_dir.exists()
        assert service.base_output_dir == new_dir


class TestReportOutputServiceGenerateReport:
    """Tests for ReportOutputService.generate_report method."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ReportOutputService:
        """Create a service instance with temp directory."""
        return ReportOutputService(base_output_dir=tmp_path / "reports")

    @pytest.mark.asyncio
    async def test_generate_report_with_all_formats(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test report generation with all output formats."""
        query_result = {
            "columns": ["id", "name", "value"],
            "rows": [[1, "alpha", 100], [2, "beta", 200]],
        }
        analysis_text = "This is a test analysis."
        plotly_figures = [{"data": [{"type": "bar"}]}]
        metadata = {"query": "SELECT * FROM test", "user_id": "user123"}

        result = await service.generate_report(
            report_id="test-report",
            query_result=query_result,
            analysis_text=analysis_text,
            plotly_figures=plotly_figures,
            output_formats=list(OutputFormat),
            metadata=metadata,
        )

        assert result.report_id == "test-report"
        assert result.output_dir == tmp_path / "reports" / "test-report"

        # Verify each format was generated (some may fail due to missing dependencies)
        formats = {a.format for a in result.artifacts}
        assert OutputFormat.JSON in formats
        assert OutputFormat.CSV in formats
        assert OutputFormat.PLOTLY_HTML in formats
        # PDF may not be generated if weasyprint is not available
        # PARQUET may not be generated if pyarrow is not available

    @pytest.mark.asyncio
    async def test_generate_report_auto_generates_report_id(
        self, service: ReportOutputService
    ) -> None:
        """Test that report_id is auto-generated if not provided."""
        result = await service.generate_report()

        # Should be a valid UUID string
        assert result.report_id is not None
        assert len(result.report_id) == 36  # UUID4 format

    @pytest.mark.asyncio
    async def test_generate_report_default_formats(self, service: ReportOutputService) -> None:
        """Test that all formats are generated by default."""
        result = await service.generate_report()

        formats = {a.format for a in result.artifacts}
        # At minimum, JSON should be generated
        assert OutputFormat.JSON in formats

    @pytest.mark.asyncio
    async def test_generate_report_with_custom_formats(
        self, service: ReportOutputService
    ) -> None:
        """Test report generation with specific formats."""
        result = await service.generate_report(
            output_formats=[OutputFormat.JSON, OutputFormat.CSV]
        )

        formats = {a.format for a in result.artifacts}
        # At minimum, JSON should be generated
        assert OutputFormat.JSON in formats

    @pytest.mark.asyncio
    async def test_generate_report_empty_query_result(
        self, service: ReportOutputService
    ) -> None:
        """Test report generation with empty query result."""
        result = await service.generate_report(
            query_result=None,
            analysis_text="Analysis only",
            plotly_figures=[],
        )

        # Should still generate some artifacts
        assert len(result.artifacts) >= 1

    @pytest.mark.asyncio
    async def test_generate_report_no_analysis_or_figures(
        self, service: ReportOutputService
    ) -> None:
        """Test report generation without analysis or figures."""
        result = await service.generate_report(
            query_result=None,
            analysis_text="",
            plotly_figures=[],
        )

        # Should generate at least JSON
        assert len(result.artifacts) >= 1


class TestReportOutputServiceGenerateJSON:
    """Tests for ReportOutputService._generate_json method."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ReportOutputService:
        """Create a service instance."""
        return ReportOutputService(base_output_dir=tmp_path / "reports")

    @pytest.mark.asyncio
    async def test_generate_json_success(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test successful JSON generation."""
        # Create the report directory first
        report_dir = tmp_path / "reports" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)

        result = await service._generate_json(
            report_dir=report_dir,
            report_id="test-123",
            query_result={"columns": ["a"], "rows": [[1]]},
            analysis_text="Test analysis",
            plotly_figures=[],
            metadata={"key": "value"},
        )

        assert result is not None
        assert result.format == OutputFormat.JSON
        assert result.filename == "test-123.json"
        assert result.size_bytes > 0
        assert result.metadata["keys"] == ["report_id", "analysis", "query_result", "chart_count", "metadata"]

        # Verify file content
        content = result.path.read_text()
        import json
        data = json.loads(content)
        assert data["report_id"] == "test-123"
        assert data["analysis"] == "Test analysis"
        assert data["query_result"] == {"columns": ["a"], "rows": [[1]]}
        assert data["chart_count"] == 0
        assert data["metadata"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_generate_json_with_none_values(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test JSON generation with None values."""
        # Create the report directory first
        report_dir = tmp_path / "reports" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)

        result = await service._generate_json(
            report_dir=report_dir,
            report_id="test-456",
            query_result=None,
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is not None
        assert result.format == OutputFormat.JSON


class TestReportOutputServiceGenerateCSV:
    """Tests for ReportOutputService._generate_csv method."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ReportOutputService:
        """Create a service instance."""
        return ReportOutputService(base_output_dir=tmp_path / "reports")

    @pytest.mark.asyncio
    async def test_generate_csv_success(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test successful CSV generation."""
        # Create the report directory first
        report_dir = tmp_path / "reports" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)

        query_result = {
            "columns": ["id", "name", "value"],
            "rows": [[1, "alpha", 100], [2, "beta", 200]],
        }

        result = await service._generate_csv(
            report_dir=report_dir,
            report_id="test-123",
            query_result=query_result,
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is not None
        assert result.format == OutputFormat.CSV
        assert result.filename == "test-123.csv"
        assert result.metadata["row_count"] == 2
        assert result.metadata["column_count"] == 3

        # Verify file content
        content = result.path.read_text()
        assert "id,name,value" in content
        assert "1,alpha,100" in content
        assert "2,beta,200" in content

    @pytest.mark.asyncio
    async def test_generate_csv_with_dict_rows(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test CSV generation with dict rows."""
        # Create the report directory first
        report_dir = tmp_path / "reports" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)

        query_result = {
            "columns": ["id", "name"],
            "rows": [{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}],
        }

        result = await service._generate_csv(
            report_dir=report_dir,
            report_id="test-456",
            query_result=query_result,
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is not None
        assert result.format == OutputFormat.CSV

    @pytest.mark.asyncio
    async def test_generate_csv_no_columns(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test CSV generation without columns."""
        query_result = {"rows": [[1, 2, 3]]}

        result = await service._generate_csv(
            report_dir=tmp_path / "reports" / "test",
            report_id="test-789",
            query_result=query_result,
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_csv_no_rows(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test CSV generation without rows."""
        query_result = {"columns": ["a", "b"]}

        result = await service._generate_csv(
            report_dir=tmp_path / "reports" / "test",
            report_id="test-999",
            query_result=query_result,
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_csv_empty_query_result(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test CSV generation with empty query_result."""
        result = await service._generate_csv(
            report_dir=tmp_path / "reports" / "test",
            report_id="test-000",
            query_result={},
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is None


class TestReportOutputServiceGenerateParquet:
    """Tests for ReportOutputService._generate_parquet method."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ReportOutputService:
        """Create a service instance."""
        return ReportOutputService(base_output_dir=tmp_path / "reports")

    @pytest.mark.asyncio
    async def test_generate_parquet_success(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test successful Parquet generation."""
        # Skip if pyarrow is not available
        pytest.importorskip("pyarrow", reason="pyarrow not installed")

        # Create the report directory first
        report_dir = tmp_path / "reports" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)

        query_result = {
            "columns": ["id", "name", "value"],
            "rows": [[1, "alpha", 100], [2, "beta", 200]],
        }

        result = await service._generate_parquet(
            report_dir=report_dir,
            report_id="test-123",
            query_result=query_result,
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is not None
        assert result.format == OutputFormat.PARQUET
        assert result.filename == "test-123.parquet"
        assert result.metadata["row_count"] == 2
        assert result.metadata["column_count"] == 3

    @pytest.mark.asyncio
    async def test_generate_parquet_with_dict_rows(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test Parquet generation with dict rows."""
        # Skip if pyarrow is not available
        pytest.importorskip("pyarrow", reason="pyarrow not installed")

        # Create the report directory first
        report_dir = tmp_path / "reports" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)

        query_result = {
            "columns": ["id", "name"],
            "rows": [{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}],
        }

        result = await service._generate_parquet(
            report_dir=report_dir,
            report_id="test-456",
            query_result=query_result,
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is not None
        assert result.format == OutputFormat.PARQUET

    @pytest.mark.asyncio
    async def test_generate_parquet_no_data(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test Parquet generation without data."""
        result = await service._generate_parquet(
            report_dir=tmp_path / "reports" / "test",
            report_id="test-789",
            query_result=None,
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_parquet_missing_columns(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test Parquet generation without columns."""
        result = await service._generate_parquet(
            report_dir=tmp_path / "reports" / "test",
            report_id="test-999",
            query_result={"rows": [[1, 2, 3]]},
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_parquet_missing_rows(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test Parquet generation without rows."""
        result = await service._generate_parquet(
            report_dir=tmp_path / "reports" / "test",
            report_id="test-000",
            query_result={"columns": ["a", "b"]},
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is None


class TestReportOutputServiceGeneratePlotlyHTML:
    """Tests for ReportOutputService._generate_plotly_html method."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ReportOutputService:
        """Create a service instance."""
        return ReportOutputService(base_output_dir=tmp_path / "reports")

    @pytest.mark.asyncio
    async def test_generate_html_success(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test successful HTML generation."""
        # Create the report directory first
        report_dir = tmp_path / "reports" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)

        query_result = {
            "columns": ["id", "name"],
            "rows": [[1, "alpha"], [2, "beta"]],
        }
        analysis_text = "This is analysis text."
        plotly_figures = [{"data": [{"type": "bar"}]}]

        result = await service._generate_plotly_html(
            report_dir=report_dir,
            report_id="test-123",
            query_result=query_result,
            analysis_text=analysis_text,
            plotly_figures=plotly_figures,
            metadata={"query": "SELECT * FROM test"},
        )

        assert result is not None
        assert result.format == OutputFormat.PLOTLY_HTML
        assert result.filename == "test-123.html"
        assert result.metadata["chart_count"] == 1
        assert result.metadata["has_data_preview"] is True

        # Verify file content
        content = result.path.read_text()
        assert "<!DOCTYPE html>" in content
        assert "Analysis" in content
        assert "This is analysis text." in content
        assert "Report test-123" in content

    @pytest.mark.asyncio
    async def test_generate_html_with_analysis_only(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test HTML generation with analysis but no charts."""
        # Create the report directory first
        report_dir = tmp_path / "reports" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)

        result = await service._generate_plotly_html(
            report_dir=report_dir,
            report_id="test-456",
            query_result=None,
            analysis_text="Analysis only",
            plotly_figures=[],
            metadata={},
        )

        assert result is not None
        assert result.format == OutputFormat.PLOTLY_HTML
        assert result.metadata["chart_count"] == 0

    @pytest.mark.asyncio
    async def test_generate_html_no_content(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test HTML generation with no content."""
        result = await service._generate_plotly_html(
            report_dir=tmp_path / "reports" / "test",
            report_id="test-789",
            query_result=None,
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_html_with_metadata(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test HTML generation includes metadata."""
        result = await service._generate_plotly_html(
            report_dir=tmp_path / "reports" / "test",
            report_id="test-999",
            query_result=None,
            analysis_text="",
            plotly_figures=[],
            metadata={"query": "SELECT * FROM users", "user_id": "user123"},
        )

        assert result is None  # No content, so no artifact

    @pytest.mark.asyncio
    async def test_generate_html_multiple_charts(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test HTML generation with multiple charts."""
        # Create the report directory first
        report_dir = tmp_path / "reports" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)

        plotly_figures = [
            {"data": [{"type": "bar"}], "layout": {"title": "Bar Chart"}},
            {"data": [{"type": "scatter"}], "layout": {"title": "Scatter Plot"}},
        ]

        result = await service._generate_plotly_html(
            report_dir=report_dir,
            report_id="test-000",
            query_result=None,
            analysis_text="",
            plotly_figures=plotly_figures,
            metadata={},
        )

        assert result is not None
        assert result.metadata["chart_count"] == 2


class TestReportOutputServiceGeneratePDF:
    """Tests for ReportOutputService._generate_pdf method."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ReportOutputService:
        """Create a service instance."""
        return ReportOutputService(base_output_dir=tmp_path / "reports")

    @pytest.mark.asyncio
    async def test_generate_pdf_success(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test successful PDF generation (mocked)."""
        # Create the report directory first
        report_dir = tmp_path / "reports" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)

        # Mock weasyprint import and HTML generation
        mock_html_artifact = ReportArtifact(
            format=OutputFormat.PLOTLY_HTML,
            path=report_dir / "test-123.html",
            filename="test-123.html",
            size_bytes=1000,
            metadata={},
        )
        mock_html_artifact.path.write_text("<html><body>Test</body></html>")

        with patch.object(service, "_generate_plotly_html", return_value=mock_html_artifact):
            with patch("weasyprint.HTML") as mock_weasyprint:
                mock_pdf_artifact = ReportArtifact(
                    format=OutputFormat.PDF,
                    path=report_dir / "test-123.pdf",
                    filename="test-123.pdf",
                    size_bytes=2000,
                    metadata={"source": "weasyprint"},
                )
                mock_pdf_artifact.path.write_text("PDF content")
                mock_weasyprint.return_value.write_pdf = MagicMock()

                result = await service._generate_pdf(
                    report_dir=report_dir,
                    report_id="test-123",
                    query_result=None,
                    analysis_text="",
                    plotly_figures=[],
                    metadata={},
                )

                assert result is not None
                assert result.format == OutputFormat.PDF
                assert result.filename == "test-123.pdf"
                assert result.metadata["source"] == "weasyprint"

    @pytest.mark.asyncio
    async def test_generate_pdf_no_html_artifact(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test PDF generation when HTML generation fails."""
        with patch.object(service, "_generate_plotly_html", return_value=None):
            result = await service._generate_pdf(
                report_dir=tmp_path / "reports" / "test",
                report_id="test-456",
                query_result=None,
                analysis_text="",
                plotly_figures=[],
                metadata={},
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_generate_pdf_weasyprint_not_installed(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test PDF generation when weasyprint is not installed."""
        # Create the report directory first
        report_dir = tmp_path / "reports" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)

        mock_html_artifact = ReportArtifact(
            format=OutputFormat.PLOTLY_HTML,
            path=report_dir / "test-789.html",
            filename="test-789.html",
            size_bytes=1000,
            metadata={},
        )
        mock_html_artifact.path.write_text("<html><body>Test</body></html>")

        with patch.object(service, "_generate_plotly_html", return_value=mock_html_artifact):
            # Patch the weasyprint import at the module level where it's imported
            with patch("weasyprint.HTML") as mock_weasyprint:
                mock_weasyprint.side_effect = ImportError("weasyprint not found")

                result = await service._generate_pdf(
                    report_dir=report_dir,
                    report_id="test-789",
                    query_result=None,
                    analysis_text="",
                    plotly_figures=[],
                    metadata={},
                )

                assert result is None

    @pytest.mark.asyncio
    async def test_generate_pdf_generation_error(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test PDF generation when PDF writing fails."""
        # Create the report directory first
        report_dir = tmp_path / "reports" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)

        mock_html_artifact = ReportArtifact(
            format=OutputFormat.PLOTLY_HTML,
            path=report_dir / "test-999.html",
            filename="test-999.html",
            size_bytes=1000,
            metadata={},
        )
        mock_html_artifact.path.write_text("<html><body>Test</body></html>")

        with patch.object(service, "_generate_plotly_html", return_value=mock_html_artifact):
            with patch("weasyprint.HTML") as mock_weasyprint:
                mock_weasyprint.return_value.write_pdf.side_effect = Exception("PDF write failed")

                result = await service._generate_pdf(
                    report_dir=report_dir,
                    report_id="test-999",
                    query_result=None,
                    analysis_text="",
                    plotly_figures=[],
                    metadata={},
                )

                assert result is None


class TestReportOutputServiceGenerateFormat:
    """Tests for ReportOutputService._generate_format method."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ReportOutputService:
        """Create a service instance."""
        return ReportOutputService(base_output_dir=tmp_path / "reports")

    @pytest.mark.asyncio
    async def test_generate_format_dispatches_correctly(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test that format dispatch calls correct generator."""
        # Create the report directory first
        report_dir = tmp_path / "reports" / "test"
        report_dir.mkdir(parents=True, exist_ok=True)

        result = await service._generate_format(
            fmt=OutputFormat.JSON,
            report_dir=report_dir,
            report_id="test-123",
            query_result=None,
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is not None
        assert result.format == OutputFormat.JSON

    @pytest.mark.asyncio
    async def test_generate_format_unknown_format(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test that unknown format returns None."""
        # Create a mock format that's not in the generators
        class FakeFormat:
            value = "fake_format"

        result = await service._generate_format(
            fmt=FakeFormat(),  # type: ignore
            report_dir=tmp_path / "reports" / "test",
            report_id="test-456",
            query_result=None,
            analysis_text="",
            plotly_figures=[],
            metadata={},
        )

        assert result is None


class TestReportOutputServiceIntegration:
    """Integration tests for ReportOutputService."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ReportOutputService:
        """Create a service instance."""
        return ReportOutputService(base_output_dir=tmp_path / "reports")

    @pytest.mark.asyncio
    async def test_full_report_generation_workflow(
        self, service: ReportOutputService, tmp_path: Path
    ) -> None:
        """Test complete report generation workflow."""
        query_result = {
            "columns": ["id", "name", "value"],
            "rows": [
                [1, "alpha", 150],
                [2, "beta", 200],
                [3, "gamma", 300],
            ],
        }
        analysis_text = "This is a comprehensive analysis of the data."
        plotly_figures = [
            {
                "data": [{"type": "bar", "x": ["a", "b", "c"], "y": [1, 2, 3]}],
                "layout": {"title": "Bar Chart"},
            },
            {
                "data": [{"type": "scatter", "x": [1, 2, 3], "y": [4, 5, 6]}],
                "layout": {"title": "Scatter Plot"},
            },
        ]
        metadata = {
            "query": "SELECT id, name, value FROM test_table WHERE value > 100",
            "user_id": "user123",
            "conversation_id": "conv456",
        }

        result = await service.generate_report(
            report_id="integration-test",
            query_result=query_result,
            analysis_text=analysis_text,
            plotly_figures=plotly_figures,
            output_formats=[OutputFormat.JSON, OutputFormat.CSV, OutputFormat.PLOTLY_HTML],
            metadata=metadata,
        )

        # Verify report output structure
        assert result.report_id == "integration-test"
        assert result.output_dir == tmp_path / "reports" / "integration-test"
        assert len(result.artifacts) == 3

        # Verify each artifact exists and has correct format
        formats = {a.format for a in result.artifacts}
        assert formats == {OutputFormat.JSON, OutputFormat.CSV, OutputFormat.PLOTLY_HTML}

        # Verify files were created
        for artifact in result.artifacts:
            assert artifact.path.exists()
            assert artifact.size_bytes > 0

        # Verify JSON content
        json_artifact = result.get_artifact(OutputFormat.JSON)
        assert json_artifact is not None
        json_content = json_artifact.path.read_text()
        assert "integration-test" in json_content
        assert "This is a comprehensive analysis" in json_content

        # Verify CSV content
        csv_artifact = result.get_artifact(OutputFormat.CSV)
        assert csv_artifact is not None
        csv_content = csv_artifact.path.read_text()
        assert "id,name,value" in csv_content
        assert "1,alpha,150" in csv_content

        # Verify HTML content
        html_artifact = result.get_artifact(OutputFormat.PLOTLY_HTML)
        assert html_artifact is not None
        html_content = html_artifact.path.read_text()
        assert "<!DOCTYPE html>" in html_content
        assert "Analysis" in html_content
        assert "Bar Chart" in html_content
        assert "Scatter Plot" in html_content

    @pytest.mark.asyncio
    async def test_report_generation_with_error_handling(
        self, service: ReportOutputService
    ) -> None:
        """Test that errors in one format don't prevent others."""
        # This test verifies that the service continues generating other formats
        # even if one format fails
        result = await service.generate_report(
            report_id="error-test",
            query_result=None,
            analysis_text="Analysis",
            plotly_figures=[],
            output_formats=list(OutputFormat),
        )

        # Should still generate some artifacts despite potential errors
        assert result.report_id == "error-test"
        assert len(result.artifacts) >= 1
