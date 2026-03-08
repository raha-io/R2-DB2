"""Important tests for Plotly chart generator.

Tests cover:
- Empty DataFrame handling (ValueError)
- Heuristic selection sanity checks (table, histogram, scatter)
- Explicit chart type override (valid/invalid)
- save_html() file writing
- save_image() kaleido-missing graceful handling
- R2-DB2 theme application (colorway/font color)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Add src to path for imports (project uses src/r2-db2 structure)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from r2-db2.integrations.plotly.chart_generator import PlotlyChartGenerator


class TestPlotlyChartGeneratorEmptyDataFrame:
    """Test empty DataFrame handling."""

    def test_generate_chart_empty_dataframe_raises_value_error(self):
        """generate_chart raises ValueError for empty DataFrame."""
        generator = PlotlyChartGenerator()
        df = pd.DataFrame()

        with pytest.raises(ValueError, match="Cannot visualize empty DataFrame"):
            generator.generate_chart(df)

    def test_generate_figure_empty_dataframe_raises_value_error(self):
        """generate_figure raises ValueError for empty DataFrame."""
        generator = PlotlyChartGenerator()
        df = pd.DataFrame()

        with pytest.raises(ValueError, match="Cannot visualize empty DataFrame"):
            generator.generate_figure(df)


class TestPlotlyChartGeneratorHeuristics:
    """Test automatic chart type selection heuristics."""

    def test_four_plus_columns_returns_table_like_figure(self):
        """4+ columns returns table-like figure/dict path."""
        generator = PlotlyChartGenerator()
        df = pd.DataFrame({
            "col1": [1, 2, 3],
            "col2": ["a", "b", "c"],
            "col3": [1.1, 2.2, 3.3],
            "col4": ["x", "y", "z"],
        })

        result = generator.generate_chart(df)

        # Table returns dict with 'data' containing 'type': 'table'
        assert isinstance(result, dict)
        assert "data" in result
        assert result["data"][0]["type"] == "table"

    def test_one_numeric_column_returns_histogram(self):
        """One numeric column -> histogram path."""
        generator = PlotlyChartGenerator()
        df = pd.DataFrame({"value": [1, 2, 3, 4, 5]})

        result = generator.generate_chart(df)

        assert isinstance(result, dict)
        assert "data" in result
        # Histogram has type 'histogram'
        assert result["data"][0]["type"] == "histogram"

    def test_two_numeric_columns_returns_scatter(self):
        """Two numeric columns -> scatter path."""
        generator = PlotlyChartGenerator()
        df = pd.DataFrame({
            "x": [1, 2, 3, 4, 5],
            "y": [2, 4, 6, 8, 10],
        })

        result = generator.generate_chart(df)

        assert isinstance(result, dict)
        assert "data" in result
        # Scatter has type 'scatter' with mode 'markers' or 'lines'
        assert result["data"][0]["type"] == "scatter"
        assert result["data"][0]["mode"] in ("markers", "lines")


class TestPlotlyChartGeneratorExplicitChartType:
    """Test explicit chart_type override in generate_figure."""

    def test_valid_chart_type_override_works(self):
        """Valid chart type (e.g., scatter) on suitable data works."""
        generator = PlotlyChartGenerator()
        df = pd.DataFrame({
            "x": [1, 2, 3, 4, 5],
            "y": [2, 4, 6, 8, 10],
            "cat": ["a", "b", "c", "d", "e"],
        })

        fig = generator.generate_figure(df, chart_type="scatter")

        assert fig is not None
        # Check it's actually a scatter plot
        assert fig.data[0].type == "scatter"

    def test_invalid_chart_type_raises_value_error(self):
        """Invalid chart type raises ValueError."""
        generator = PlotlyChartGenerator()
        df = pd.DataFrame({
            "x": [1, 2, 3],
            "y": [4, 5, 6],
        })

        with pytest.raises(ValueError, match="Unknown chart type"):
            generator.generate_figure(df, chart_type="invalid_type")


class TestPlotlyChartGeneratorSaveHtml:
    """Test save_html() file writing."""

    def test_save_html_writes_to_nested_directory_and_returns_absolute_path(self, tmp_path):
        """save_html writes file to nested directory and returns absolute path."""
        generator = PlotlyChartGenerator()
        df = pd.DataFrame({
            "x": [1, 2, 3],
            "y": [4, 5, 6],
        })

        fig = generator.generate_figure(df)
        nested_path = tmp_path / "charts" / "subdir" / "chart.html"
        result_path = generator.save_html(fig, str(nested_path))

        # Verify file was created
        assert Path(result_path).exists()
        # Verify it's an absolute path
        assert Path(result_path).is_absolute()
        # Verify nested directory was created
        assert Path(result_path).parent.name == "subdir"


class TestPlotlyChartGeneratorSaveImage:
    """Test save_image() kaleido-missing graceful handling."""

    def test_save_image_handles_kaleido_missing_gracefully(self, tmp_path):
        """save_image returns None when kaleido is missing (mocked error)."""
        generator = PlotlyChartGenerator()
        df = pd.DataFrame({
            "x": [1, 2, 3],
            "y": [4, 5, 6],
        })

        fig = generator.generate_figure(df)
        image_path = tmp_path / "chart.png"

        # Mock write_image to raise an exception containing 'kaleido'
        with patch.object(fig, "write_image") as mock_write:
            mock_write.side_effect = Exception("kaleido is not installed")

            result = generator.save_image(fig, str(image_path))

        assert result is None


class TestPlotlyChartGeneratorTheme:
    """Test R2-DB2 theme application."""

    def test_r2_db2_theme_applied_colorway_and_font_color(self):
        """R2-DB2 theme is applied (colorway/font color) on generated figure."""
        generator = PlotlyChartGenerator()
        df = pd.DataFrame({
            "x": [1, 2, 3],
            "y": [4, 5, 6],
        })

        fig = generator.generate_figure(df)

        # Check colorway is set to R2-DB2 palette
        layout = fig.layout
        assert hasattr(layout, "colorway")
        colorway = list(layout.colorway)
        assert len(colorway) > 0
        # R2-DB2 palette colors
        assert generator.COLOR_PALETTE[0] in colorway

        # Check font color is set to navy
        assert hasattr(layout, "font")
        assert layout.font.color == generator.THEME_COLORS["navy"]
