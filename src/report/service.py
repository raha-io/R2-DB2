"""Report output service - generates file artifacts from analysis results."""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Callable, Coroutine

from report.models import OutputFormat, ReportArtifact, ReportOutput

logger = logging.getLogger(__name__)


class ReportOutputService:
    """Generates report file artifacts in multiple formats."""

    def __init__(self, base_output_dir: str | Path = "./reports") -> None:
        self.base_output_dir = Path(base_output_dir)
        self.base_output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_report(
        self,
        *,
        report_id: str | None = None,
        query_result: dict[str, Any] | None = None,
        analysis_text: str = "",
        plotly_figures: list[dict[str, Any]] | None = None,
        output_formats: list[OutputFormat] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReportOutput:
        """Generate report artifacts in requested formats.

        Args:
            report_id: Unique report identifier (auto-generated if None)
            query_result: SQL query result data (columns + rows)
            analysis_text: Text analysis/summary
            plotly_figures: List of Plotly figure JSON dicts
            output_formats: Which formats to generate (defaults to all)
            metadata: Additional metadata (query, user, etc.)

        Returns:
            ReportOutput with paths to all generated artifacts
        """
        report_id = report_id or str(uuid.uuid4())
        output_formats = output_formats or list(OutputFormat)
        plotly_figures = plotly_figures or []
        metadata = metadata or {}

        report_dir = self.base_output_dir / report_id
        report_dir.mkdir(parents=True, exist_ok=True)

        output = ReportOutput(report_id=report_id, output_dir=report_dir)

        for fmt in output_formats:
            try:
                artifact = await self._generate_format(
                    fmt=fmt,
                    report_dir=report_dir,
                    report_id=report_id,
                    query_result=query_result,
                    analysis_text=analysis_text,
                    plotly_figures=plotly_figures,
                    metadata=metadata,
                )
                if artifact:
                    output.artifacts.append(artifact)
            except Exception:
                logger.exception("Failed to generate %s output", fmt.value)

        return output

    async def _generate_format(
        self,
        *,
        fmt: OutputFormat,
        report_dir: Path,
        report_id: str,
        query_result: dict[str, Any] | None,
        analysis_text: str,
        plotly_figures: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> ReportArtifact | None:
        """Dispatch to format-specific generator."""
        generators: dict[
            OutputFormat,
            Callable[..., Coroutine[Any, Any, ReportArtifact | None]],
        ] = {
            OutputFormat.JSON: self._generate_json,
            OutputFormat.CSV: self._generate_csv,
            OutputFormat.PARQUET: self._generate_parquet,
            OutputFormat.PLOTLY_HTML: self._generate_plotly_html,
            OutputFormat.PDF: self._generate_pdf,
        }
        generator = generators.get(fmt)
        if generator is None:
            logger.warning("No generator for format: %s", fmt.value)
            return None
        return await generator(
            report_dir=report_dir,
            report_id=report_id,
            query_result=query_result,
            analysis_text=analysis_text,
            plotly_figures=plotly_figures,
            metadata=metadata,
        )

    async def _generate_json(
        self,
        *,
        report_dir: Path,
        report_id: str,
        query_result: dict[str, Any] | None,
        analysis_text: str,
        plotly_figures: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> ReportArtifact:
        """Generate JSON summary."""
        filename = f"{report_id}.json"
        path = report_dir / filename
        data = {
            "report_id": report_id,
            "analysis": analysis_text,
            "query_result": query_result,
            "chart_count": len(plotly_figures),
            "metadata": metadata,
        }
        content = json.dumps(data, indent=2, default=str)
        path.write_text(content, encoding="utf-8")
        return ReportArtifact(
            format=OutputFormat.JSON,
            path=path,
            filename=filename,
            size_bytes=path.stat().st_size,
            metadata={"keys": list(data.keys())},
        )

    async def _generate_csv(
        self,
        *,
        report_dir: Path,
        report_id: str,
        query_result: dict[str, Any] | None,
        analysis_text: str,
        plotly_figures: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> ReportArtifact | None:
        """Generate CSV from query results."""
        if not query_result or not query_result.get("columns") or not query_result.get(
            "rows"
        ):
            logger.info("No query result data for CSV export")
            return None

        import csv
        import io

        filename = f"{report_id}.csv"
        path = report_dir / filename

        columns = query_result["columns"]
        rows = query_result["rows"]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            if isinstance(row, dict):
                writer.writerow([row.get(c, "") for c in columns])
            else:
                writer.writerow(row)

        path.write_text(output.getvalue(), encoding="utf-8")
        return ReportArtifact(
            format=OutputFormat.CSV,
            path=path,
            filename=filename,
            size_bytes=path.stat().st_size,
            metadata={"row_count": len(rows), "column_count": len(columns)},
        )

    async def _generate_parquet(
        self,
        *,
        report_dir: Path,
        report_id: str,
        query_result: dict[str, Any] | None,
        analysis_text: str,
        plotly_figures: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> ReportArtifact | None:
        """Generate Parquet from query results."""
        if not query_result or not query_result.get("columns") or not query_result.get(
            "rows"
        ):
            logger.info("No query result data for Parquet export")
            return None

        try:
            import pandas as pd
        except ImportError:
            logger.warning("pandas not installed, skipping Parquet generation")
            return None

        filename = f"{report_id}.parquet"
        path = report_dir / filename

        columns = query_result["columns"]
        rows = query_result["rows"]

        if rows and isinstance(rows[0], dict):
            df = pd.DataFrame(rows)
        else:
            df = pd.DataFrame(rows, columns=columns)

        df.to_parquet(path, index=False)
        return ReportArtifact(
            format=OutputFormat.PARQUET,
            path=path,
            filename=filename,
            size_bytes=path.stat().st_size,
            metadata={"row_count": len(df), "column_count": len(df.columns)},
        )

    async def _generate_plotly_html(
        self,
        *,
        report_dir: Path,
        report_id: str,
        query_result: dict[str, Any] | None,
        analysis_text: str,
        plotly_figures: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> ReportArtifact | None:
        """Generate interactive HTML report with Plotly charts."""
        if not plotly_figures and not analysis_text:
            logger.info("No charts or analysis for HTML report")
            return None

        try:
            import plotly.io as pio
            from plotly.graph_objects import Figure
        except ImportError:
            logger.warning("plotly not installed, skipping HTML generation")
            return None

        filename = f"{report_id}.html"
        path = report_dir / filename

        chart_divs: list[str] = []
        for index, fig_json in enumerate(plotly_figures):
            try:
                fig = Figure(fig_json)
                chart_html = pio.to_html(
                    fig, full_html=False, include_plotlyjs=(index == 0)
                )
                chart_divs.append(chart_html)
            except Exception:
                logger.exception("Failed to render chart %d", index)

        html_parts = [
            "<!DOCTYPE html>",
            "<html><head>",
            "<meta charset='utf-8'>",
            f"<title>Report {report_id}</title>",
            "<style>",
            "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }",
            "h1 { color: #333; } h2 { color: #555; }",
            " .analysis { background: #f8f9fa; padding: 16px; border-radius: 8px; margin: 16px 0; white-space: pre-wrap; }",
            " .chart { margin: 24px 0; }",
            " .metadata { color: #888; font-size: 0.85em; margin-top: 32px; border-top: 1px solid #eee; padding-top: 12px; }",
            "</style>",
            "</head><body>",
            "<h1>Analysis Report</h1>",
        ]

        if analysis_text:
            html_parts.append(
                "<h2>Analysis</h2><div class='analysis'>"
                f"{analysis_text}</div>"
            )

        if chart_divs:
            html_parts.append("<h2>Charts</h2>")
            for div in chart_divs:
                html_parts.append(f"<div class='chart'>{div}</div>")

        if query_result and query_result.get("columns"):
            html_parts.append("<h2>Data Preview</h2>")
            html_parts.append(
                "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;'>"
            )
            html_parts.append(
                "<tr>"
                + "".join(f"<th>{c}</th>" for c in query_result["columns"])
                + "</tr>"
            )
            rows = query_result.get("rows", [])[:50]
            for row in rows:
                if isinstance(row, dict):
                    cells = [str(row.get(c, "")) for c in query_result["columns"]]
                else:
                    cells = [str(value) for value in row]
                html_parts.append(
                    "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
                )
            html_parts.append("</table>")

        query_str = metadata.get("query", "N/A")
        html_parts.append(
            "<div class='metadata'>"
            f"<p>Report ID: {report_id}</p>"
            f"<p>Query: {query_str}</p></div>"
        )
        html_parts.append("</body></html>")

        path.write_text("\n".join(html_parts), encoding="utf-8")
        return ReportArtifact(
            format=OutputFormat.PLOTLY_HTML,
            path=path,
            filename=filename,
            size_bytes=path.stat().st_size,
            metadata={
                "chart_count": len(chart_divs),
                "has_data_preview": bool(query_result),
            },
        )

    async def _generate_pdf(
        self,
        *,
        report_dir: Path,
        report_id: str,
        query_result: dict[str, Any] | None,
        analysis_text: str,
        plotly_figures: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> ReportArtifact | None:
        """Generate PDF report. Requires weasyprint."""
        html_artifact = await self._generate_plotly_html(
            report_dir=report_dir,
            report_id=report_id,
            query_result=query_result,
            analysis_text=analysis_text,
            plotly_figures=plotly_figures,
            metadata=metadata,
        )
        if not html_artifact:
            logger.info("No HTML content to convert to PDF")
            return None

        try:
            from weasyprint import HTML as WeasyprintHTML
        except ImportError:
            logger.warning(
                "weasyprint not installed, skipping PDF generation. Install with: uv add weasyprint"
            )
            return None

        filename = f"{report_id}.pdf"
        path = report_dir / filename

        try:
            html_content = html_artifact.path.read_text(encoding="utf-8")
            WeasyprintHTML(string=html_content).write_pdf(str(path))
            return ReportArtifact(
                format=OutputFormat.PDF,
                path=path,
                filename=filename,
                size_bytes=path.stat().st_size,
                metadata={"source": "weasyprint"},
            )
        except Exception:
            logger.exception("PDF generation failed")
            return None
