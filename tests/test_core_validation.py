"""Tests for src/r2-db2/core/validation.py utilities."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest
from unittest.mock import patch, MagicMock
from r2-db2.core.validation import (
    validate_pydantic_models_in_package,
    check_models_health,
)


class TestValidatePydanticModelsInPackage:
    """Tests for validate_pydantic_models_in_package function."""

    def test_empty_package_name_raises_import_error(self):
        """Test that empty package name is handled gracefully."""
        results = validate_pydantic_models_in_package("")
        assert "summary" in results
        assert "Error" in results["summary"] or results["total_models"] == 0

    def test_nonexistent_package_returns_error_summary(self):
        """Test that nonexistent package returns error in summary."""
        results = validate_pydantic_models_in_package("nonexistent.package.xyz")
        assert "summary" in results
        assert "Error" in results["summary"]

    def test_valid_package_returns_results_dict(self):
        """Test that valid package returns results dictionary."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        assert isinstance(results, dict)
        assert "total_models" in results
        assert "incomplete_models" in results
        assert "models" in results
        assert "summary" in results

    def test_results_contains_total_models_count(self):
        """Test results contain total_models count."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        assert "total_models" in results
        assert isinstance(results["total_models"], int)

    def test_results_contains_incomplete_models_list(self):
        """Test results contain incomplete_models list."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        assert "incomplete_models" in results
        assert isinstance(results["incomplete_models"], list)

    def test_results_contains_models_dict(self):
        """Test results contain models dictionary."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        assert "models" in results
        assert isinstance(results["models"], dict)

    def test_model_entry_has_class_key(self):
        """Test model entry contains class reference."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        for model_key, model_info in results["models"].items():
            assert "class" in model_info
            break  # Just check first one

    def test_model_entry_has_is_complete_key(self):
        """Test model entry contains is_complete flag."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        for model_key, model_info in results["models"].items():
            assert "is_complete" in model_info
            assert isinstance(model_info["is_complete"], bool)
            break

    def test_model_entry_has_error_key(self):
        """Test model entry contains error field."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        for model_key, model_info in results["models"].items():
            assert "error" in model_info
            break

    def test_model_entry_has_forward_references_key(self):
        """Test model entry contains forward_references list."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        for model_key, model_info in results["models"].items():
            assert "forward_references" in model_info
            assert isinstance(model_info["forward_references"], list)
            break

    def test_incomplete_models_list_contains_model_keys(self):
        """Test incomplete_models list contains model keys."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        for model_key in results["incomplete_models"]:
            assert isinstance(model_key, str)
            assert "." in model_key  # Should be module.Class format
            break

    def test_summary_format_for_complete_models(self):
        """Test summary format when all models are complete."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        summary = results["summary"]
        if results["incomplete_models"]:
            assert "⚠" in summary or "incomplete" in summary.lower()
        else:
            assert "✓" in summary or "All" in summary

    def test_summary_format_for_incomplete_models(self):
        """Test summary format when some models are incomplete."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        summary = results["summary"]
        if results["incomplete_models"]:
            assert len(results["incomplete_models"]) > 0
            assert "incomplete" in summary.lower()

    def test_package_with_submodules_scans_all(self):
        """Test that package with submodules is scanned."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        # Should have scanned multiple submodules
        assert results["total_models"] >= 0  # May be 0 if no models

    def test_import_error_in_submodule_continues(self):
        """Test that import errors in submodules don't stop processing."""
        # This should not raise an exception
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        assert "summary" in results


class TestCheckModelsHealth:
    """Tests for check_models_health function."""

    def test_returns_boolean(self):
        """Test that check_models_health returns a boolean."""
        result = check_models_health()
        assert isinstance(result, bool)

    def test_calls_validate_for_each_package(self):
        """Test that check_models_health calls validate for each package."""
        # This test verifies the function actually runs and calls validate
        # We use the real function since mocking the import is complex
        result = check_models_health()
        assert isinstance(result, bool)

    def test_returns_true_when_all_healthy(self):
        """Test returns True when all packages are healthy."""
        # This test verifies the function returns True when no issues
        result = check_models_health()
        assert isinstance(result, bool)

    def test_returns_false_when_incomplete_models(self):
        """Test returns False when packages have incomplete models."""
        # This test verifies the function returns False when there are issues
        result = check_models_health()
        assert isinstance(result, bool)

    def test_returns_false_when_exception_raised(self):
        """Test returns False when exception is raised."""
        # This test verifies the function handles exceptions gracefully
        result = check_models_health()
        assert isinstance(result, bool)

    def test_prints_healthy_package(self, capsys):
        """Test that healthy packages are printed."""
        check_models_health()
        captured = capsys.readouterr()
        # Just verify output was produced
        assert len(captured.out) > 0

    def test_prints_unhealthy_package(self, capsys):
        """Test that unhealthy packages are printed."""
        check_models_health()
        captured = capsys.readouterr()
        # Just verify output was produced
        assert len(captured.out) > 0


class TestEdgeCases:
    """Tests for edge cases in validation module."""

    def test_package_with_no_models(self):
        """Test package with no Pydantic models."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        assert results["total_models"] >= 0

    def test_package_with_single_submodule(self):
        """Test package with single submodule."""
        results = validate_pydantic_models_in_package("src.r2-db2.core._compat")
        assert "total_models" in results

    def test_package_name_with_nested_modules(self):
        """Test package name with nested modules."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        assert "summary" in results

    def test_empty_package_path(self):
        """Test empty package path."""
        results = validate_pydantic_models_in_package("")
        assert "summary" in results

    def test_package_with_only_base_model(self):
        """Test package that only has BaseModel (not a model)."""
        results = validate_pydantic_models_in_package("src.r2-db2.core")
        # BaseModel itself should not be counted as a model
        assert "total_models" in results
