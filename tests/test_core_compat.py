"""Tests for src/r2-db2/core/_compat.py compatibility shims."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest
from unittest.mock import patch


class TestStrEnum:
    """Tests for StrEnum compatibility shim."""

    def test_strenum_importable(self):
        """Test that StrEnum can be imported from _compat."""
        from r2-db2.core._compat import StrEnum
        assert StrEnum is not None

    def test_strenum_is_enum_subclass(self):
        """Test that StrEnum is a subclass of Enum."""
        from r2-db2.core._compat import StrEnum

        class TestEnum(StrEnum):
            VALUE1 = "value1"
            VALUE2 = "value2"

        from enum import Enum
        assert issubclass(TestEnum, Enum)

    def test_strenum_is_str_subclass(self):
        """Test that StrEnum is a subclass of str."""
        from r2-db2.core._compat import StrEnum

        class TestEnum(StrEnum):
            VALUE1 = "value1"
            VALUE2 = "value2"

        assert issubclass(TestEnum, str)

    def test_strenum_values_are_strings(self):
        """Test that StrEnum values are strings."""
        from r2-db2.core._compat import StrEnum

        class TestEnum(StrEnum):
            VALUE1 = "value1"
            VALUE2 = "value2"

        assert TestEnum.VALUE1 == "value1"
        assert TestEnum.VALUE2 == "value2"

    def test_strenum_can_be_used_in_switch(self):
        """Test that StrEnum can be used in switch-like comparisons."""
        from r2-db2.core._compat import StrEnum

        class Status(StrEnum):
            ACTIVE = "active"
            INACTIVE = "inactive"

        status = Status.ACTIVE
        assert status == "active"
        assert status != "inactive"

    def test_strenum_string_operations(self):
        """Test that StrEnum supports string operations."""
        from r2-db2.core._compat import StrEnum

        class Color(StrEnum):
            RED = "red"
            GREEN = "green"

        color = Color.RED
        assert str(color) == "red"
        assert len(color) == 3
        assert color.upper() == "RED"

    def test_strenum_iteration(self):
        """Test that StrEnum can be iterated."""
        from r2-db2.core._compat import StrEnum

        class Mode(StrEnum):
            READ = "read"
            WRITE = "write"
            EXECUTE = "execute"

        values = [m.value for m in Mode]
        assert values == ["read", "write", "execute"]

    def test_strenum_membership(self):
        """Test that StrEnum supports membership checks."""
        from r2-db2.core._compat import StrEnum

        class Permission(StrEnum):
            READ = "read"
            WRITE = "write"

        assert "read" in Permission._value2member_map_
        assert "write" in Permission._value2member_map_

    def test_strenum_repr(self):
        """Test that StrEnum has proper repr."""
        from r2-db2.core._compat import StrEnum

        class TestEnum(StrEnum):
            VALUE = "value"

        enum_value = TestEnum.VALUE
        repr_str = repr(enum_value)
        assert "TestEnum.VALUE" in repr_str or "value" in repr_str

    def test_strenum_str(self):
        """Test that StrEnum str() returns value."""
        from r2-db2.core._compat import StrEnum

        class TestEnum(StrEnum):
            VALUE = "value"

        assert str(TestEnum.VALUE) == "value"


class TestPythonVersionCompatibility:
    """Tests for Python version-specific behavior."""

    def test_strenum_uses_native_when_available(self):
        """Test that native StrEnum is used when available (Python 3.11+)."""
        # This test verifies the import logic
        from r2-db2.core._compat import StrEnum

        # Check if it's the native StrEnum or our backport
        import enum
        if sys.version_info >= (3, 11):
            # Should be native StrEnum
            assert StrEnum is enum.StrEnum or issubclass(StrEnum, enum.StrEnum)
        else:
            # Should be our backport
            assert StrEnum.__module__ == "r2-db2.core._compat"

    def test_strenum_backport_works_on_all_versions(self):
        """Test that the backport works regardless of Python version."""
        from r2-db2.core._compat import StrEnum

        class TestEnum(StrEnum):
            A = "a"
            B = "b"

        # Should work the same regardless of version
        assert TestEnum.A == "a"
        assert TestEnum.B == "b"
        assert isinstance(TestEnum.A, str)


class TestAllExport:
    """Tests for __all__ export."""

    def test_strenum_in_all(self):
        """Test that StrEnum is in __all__."""
        from r2-db2.core import _compat
        assert "StrEnum" in _compat.__all__
