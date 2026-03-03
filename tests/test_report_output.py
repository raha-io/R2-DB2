"""Tests for report output service."""
from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# Sample query result data (simulating ClickHouse output)
SAMPLE_QUERY_RESULT = {
    "columns": ["date", "product", "revenue", "quantity"],
    "rows": [
        {"date": "2024-01-01", "product": "Widget A", "revenue": 15000.50, "quantity": 150},
        {"date": "2024-01-02", "product": "Widget B", "revenue": 22000.75, "quantity": 220},
        {"date": "2024-01-03", "product": "Widget A", "revenue": 18500.00, "quantity": 185},
        {"date": "2024-01-04", "product": "Widget C", "revenue": 9800.25, "quantity": 98},
        {"date": "2024-01-05", "product": "Widget B", "revenue": 31000.00, "quantity": 310},
        {"date": "2024-01-06", "product": "Widget A", "revenue": 12000.00, "quantity": 120},
        {"date": "2024-01-07", "product": "Widget C", "revenue": 8500.50, "quantity": 85},
    ],
}

SAMPLE_ANALYSIS = """## Revenue Analysis

Total revenue across all products: $116,802.00
Top performing product: Widget B ($53,000.75)
Average daily revenue: $16,685.71

### Key Findings
1. Widget B shows the highest revenue with strong growth
2. Widget A maintains consistent performance
3. Widget C has lower volume but steady demand
"""


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test outputs."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def report_service(temp_output_dir):
    """Create a ReportOutputService with a temp directory."""
    from r2-db2.core.report import ReportOutputService

    return ReportOutputService(base_output_dir=temp_output_dir)


def _make_plotly_figures():
    try:
        import pandas as pd
        import plotly.express as px
    except ImportError:
        pytest.skip("plotly or pandas not installed")

    df = pd.DataFrame(SAMPLE_QUERY_RESULT["rows"])
    fig1 = px.bar(df, x="product", y="revenue", title="Revenue by Product")
    fig2 = px.line(df, x="date", y="revenue", title="Revenue Over Time")
    return [fig1.to_dict(), fig2.to_dict()]


def _make_generator_figures():
    try:
        import pandas as pd
        import plotly
    except ImportError:
        pytest.skip("plotly or pandas not installed")

    from r2-db2.integrations.plotly.chart_generator import PlotlyChartGenerator

    df = pd.DataFrame(SAMPLE_QUERY_RESULT["rows"])
    generator = PlotlyChartGenerator()
    fig_dict = generator.generate_chart(df, title="Generated Chart")
    return [fig_dict]


def _assert_html_has_chart(content: str) -> None:
    assert "Analysis Report" in content
    assert "<div class='chart'>" in content
    assert "plotly" in content.lower()


async def _test_json_output(report_service):
    from r2-db2.core.report import OutputFormat

    output = await report_service.generate_report(
        report_id="test-json",
        query_result=SAMPLE_QUERY_RESULT,
        analysis_text=SAMPLE_ANALYSIS,
        output_formats=[OutputFormat.JSON],
    )

    json_artifact = output.get_artifact(OutputFormat.JSON)
    assert json_artifact is not None
    assert json_artifact.filename == "test-json.json"

    content = json.loads(json_artifact.path.read_text())
    assert content["report_id"] == "test-json"
    assert content["analysis"] == SAMPLE_ANALYSIS
    assert content["query_result"] == SAMPLE_QUERY_RESULT
    assert content["chart_count"] == 0


async def _test_csv_output(report_service):
    from r2-db2.core.report import OutputFormat

    output = await report_service.generate_report(
        report_id="test-csv",
        query_result=SAMPLE_QUERY_RESULT,
        output_formats=[OutputFormat.CSV],
    )

    csv_artifact = output.get_artifact(OutputFormat.CSV)
    assert csv_artifact is not None
    assert csv_artifact.filename == "test-csv.csv"

    content = csv_artifact.path.read_text()
    lines = content.strip().split("\n")
    assert len(lines) == 8
    assert lines[0] == "date,product,revenue,quantity"

    assert csv_artifact.metadata["row_count"] == 7
    assert csv_artifact.metadata["column_count"] == 4


async def _test_parquet_output(report_service):
    from r2-db2.core.report import OutputFormat

    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas not installed")

    try:
        import pyarrow  # noqa: F401
    except ImportError:
        try:
            import fastparquet  # noqa: F401
        except ImportError:
            pytest.skip("pyarrow/fastparquet not installed")

    output = await report_service.generate_report(
        report_id="test-parquet",
        query_result=SAMPLE_QUERY_RESULT,
        output_formats=[OutputFormat.PARQUET],
    )

    parquet_artifact = output.get_artifact(OutputFormat.PARQUET)
    assert parquet_artifact is not None
    assert parquet_artifact.filename == "test-parquet.parquet"

    df = pd.read_parquet(parquet_artifact.path)
    assert len(df) == 7
    assert list(df.columns) == ["date", "product", "revenue", "quantity"]


async def _test_plotly_html_output(report_service):
    from r2-db2.core.report import OutputFormat

    plotly_figures = _make_plotly_figures()

    output = await report_service.generate_report(
        report_id="test-plotly",
        query_result=SAMPLE_QUERY_RESULT,
        analysis_text=SAMPLE_ANALYSIS,
        plotly_figures=plotly_figures,
        output_formats=[OutputFormat.PLOTLY_HTML],
    )

    html_artifact = output.get_artifact(OutputFormat.PLOTLY_HTML)
    assert html_artifact is not None
    assert html_artifact.filename == "test-plotly.html"

    content = html_artifact.path.read_text()
    assert "<!DOCTYPE html>" in content
    assert "Analysis Report" in content
    assert "Charts" in content
    _assert_html_has_chart(content)


async def _test_all_formats_together(report_service):
    from r2-db2.core.report import OutputFormat

    plotly_figures = []
    try:
        plotly_figures = _make_plotly_figures()
    except pytest.skip.Exception:
        plotly_figures = []

    output = await report_service.generate_report(
        report_id="test-all",
        query_result=SAMPLE_QUERY_RESULT,
        analysis_text=SAMPLE_ANALYSIS,
        plotly_figures=plotly_figures,
        output_formats=list(OutputFormat),
        metadata={"query": "SELECT * FROM sales LIMIT 10"},
    )

    assert output.get_artifact(OutputFormat.JSON) is not None
    assert output.get_artifact(OutputFormat.CSV) is not None

    if output.get_artifact(OutputFormat.PARQUET):
        assert (output.output_dir / "test-all.parquet").exists()

    if output.get_artifact(OutputFormat.PLOTLY_HTML):
        html_content = (output.output_dir / "test-all.html").read_text()
        assert "Analysis Report" in html_content

    if output.get_artifact(OutputFormat.PDF):
        assert (output.output_dir / "test-all.pdf").exists()


async def _test_plotly_chart_generator(report_service):
    from r2-db2.core.report import OutputFormat

    plotly_figures = _make_generator_figures()

    output = await report_service.generate_report(
        report_id="test-generator",
        query_result=SAMPLE_QUERY_RESULT,
        analysis_text=SAMPLE_ANALYSIS,
        plotly_figures=plotly_figures,
        output_formats=[OutputFormat.PLOTLY_HTML, OutputFormat.JSON],
    )

    html_artifact = output.get_artifact(OutputFormat.PLOTLY_HTML)
    assert html_artifact is not None
    content = html_artifact.path.read_text()
    _assert_html_has_chart(content)


@pytest.mark.asyncio
async def test_json_output(report_service):
    await _test_json_output(report_service)


@pytest.mark.asyncio
async def test_csv_output(report_service):
    await _test_csv_output(report_service)


@pytest.mark.asyncio
async def test_parquet_output(report_service):
    await _test_parquet_output(report_service)


@pytest.mark.asyncio
async def test_plotly_html_output(report_service):
    await _test_plotly_html_output(report_service)


@pytest.mark.asyncio
async def test_all_formats_together(report_service):
    await _test_all_formats_together(report_service)


@pytest.mark.asyncio
async def test_plotly_chart_generator(report_service):
    await _test_plotly_chart_generator(report_service)
