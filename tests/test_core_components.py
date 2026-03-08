"""Tests for src/r2-db2/core/components.py and related component classes."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from r2-db2.core.components import UiComponent
from r2-db2.core.rich_component import RichComponent, ComponentType, ComponentLifecycle
from r2-db2.core.simple_component import SimpleComponent, SimpleComponentType


class TestUiComponent:
    """Tests for UiComponent class."""

    def test_uicomponent_instantiation_with_rich_component(self):
        """Test UiComponent can be instantiated with a RichComponent."""
        rich_comp = RichComponent(type=ComponentType.TEXT)
        component = UiComponent(rich_component=rich_comp)
        assert component.rich_component == rich_comp

    def test_uicomponent_instantiation_with_simple_component(self):
        """Test UiComponent can be instantiated with a SimpleComponent."""
        rich_comp = RichComponent(type=ComponentType.TEXT)
        simple_comp = SimpleComponent(type=SimpleComponentType.TEXT)
        component = UiComponent(rich_component=rich_comp, simple_component=simple_comp)
        assert component.simple_component == simple_comp

    def test_uicomponent_default_timestamp(self):
        """Test UiComponent has default timestamp."""
        rich_comp = RichComponent(type=ComponentType.TEXT)
        component = UiComponent(rich_component=rich_comp)
        assert component.timestamp is not None
        assert isinstance(component.timestamp, str)

    def test_uicomponent_rich_component_required(self):
        """Test that rich_component is required (Ellipsis field)."""
        with pytest.raises(Exception):  # Pydantic validation error
            UiComponent()

    def test_uicomponent_simple_component_optional(self):
        """Test that simple_component is optional."""
        rich_comp = RichComponent(type=ComponentType.TEXT)
        component = UiComponent(rich_component=rich_comp)
        assert component.simple_component is None

    def test_uicomponent_validation_rejects_invalid_rich_component(self):
        """Test that invalid rich_component raises ValueError."""
        with pytest.raises(ValueError):
            UiComponent(rich_component="not a rich component")

    def test_uicomponent_validation_rejects_invalid_simple_component(self):
        """Test that invalid simple_component raises ValueError."""
        rich_comp = RichComponent(type=ComponentType.TEXT)
        with pytest.raises(ValueError):
            UiComponent(rich_component=rich_comp, simple_component="not a simple component")

    def test_uicomponent_with_valid_simple_component(self):
        """Test UiComponent with valid SimpleComponent."""
        rich_comp = RichComponent(type=ComponentType.TEXT)
        simple_comp = SimpleComponent(type=SimpleComponentType.TEXT)
        component = UiComponent(rich_component=rich_comp, simple_component=simple_comp)
        assert component.simple_component == simple_comp

    def test_uicomponent_timestamp_format(self):
        """Test that timestamp is in ISO format."""
        rich_comp = RichComponent(type=ComponentType.TEXT)
        component = UiComponent(rich_component=rich_comp)
        # Should be parseable as ISO datetime
        datetime.fromisoformat(component.timestamp.replace("Z", "+00:00"))


class TestRichComponent:
    """Tests for RichComponent class."""

    def test_richcomponent_instantiation(self):
        """Test RichComponent can be instantiated."""
        component = RichComponent(type=ComponentType.TEXT)
        assert component.type == ComponentType.TEXT

    def test_richcomponent_default_id(self):
        """Test RichComponent has default UUID id."""
        component = RichComponent(type=ComponentType.TEXT)
        assert component.id is not None
        assert len(component.id) > 0

    def test_richcomponent_default_data(self):
        """Test RichComponent has default empty data dict."""
        component = RichComponent(type=ComponentType.TEXT)
        assert component.data == {}

    def test_richcomponent_default_children(self):
        """Test RichComponent has default empty children list."""
        component = RichComponent(type=ComponentType.TEXT)
        assert component.children == []

    def test_richcomponent_default_visible(self):
        """Test RichComponent is visible by default."""
        component = RichComponent(type=ComponentType.TEXT)
        assert component.visible is True

    def test_richcomponent_default_interactive(self):
        """Test RichComponent is not interactive by default."""
        component = RichComponent(type=ComponentType.TEXT)
        assert component.interactive is False

    def test_richcomponent_update_method(self):
        """Test RichComponent.update() creates updated copy."""
        component = RichComponent(type=ComponentType.TEXT, visible=True)
        updated = component.update(visible=False)
        assert updated.visible is False
        assert updated.id == component.id  # Same ID
        assert updated.lifecycle == ComponentLifecycle.UPDATE

    def test_richcomponent_hide_method(self):
        """Test RichComponent.hide() creates hidden copy."""
        component = RichComponent(type=ComponentType.TEXT, visible=True)
        hidden = component.hide()
        assert hidden.visible is False

    def test_richcomponent_show_method(self):
        """Test RichComponent.show() creates visible copy."""
        component = RichComponent(type=ComponentType.TEXT, visible=False)
        shown = component.show()
        assert shown.visible is True

    def test_richcomponent_serialize_for_frontend(self):
        """Test RichComponent.serialize_for_frontend() returns correct structure."""
        component = RichComponent(type=ComponentType.TEXT, visible=True)
        serialized = component.serialize_for_frontend()
        assert "id" in serialized
        assert "type" in serialized
        assert "data" in serialized
        assert serialized["type"] == "text"

    def test_richcomponent_custom_data(self):
        """Test RichComponent with custom data."""
        component = RichComponent(
            type=ComponentType.TEXT,
            data={"text": "Hello, World!"}
        )
        assert component.data["text"] == "Hello, World!"


class TestComponentType:
    """Tests for ComponentType enum."""

    def test_component_type_text(self):
        """Test ComponentType.TEXT value."""
        assert ComponentType.TEXT.value == "text"

    def test_component_type_card(self):
        """Test ComponentType.CARD value."""
        assert ComponentType.CARD.value == "card"

    def test_component_type_table(self):
        """Test ComponentType.TABLE value."""
        assert ComponentType.TABLE.value == "table"

    def test_component_type_chart(self):
        """Test ComponentType.CHART value."""
        assert ComponentType.CHART.value == "chart"

    def test_component_type_all_values(self):
        """Test all ComponentType values."""
        expected_values = [
            "text", "card", "container",
            "status_card", "progress_display", "log_viewer", "badge", "icon_text",
            "task_list", "progress_bar", "button", "button_group",
            "table", "dataframe", "chart", "code_block",
            "status_indicator", "notification", "alert",
            "artifact",
            "status_bar_update", "task_tracker_update", "chat_input_update",
            "tool_execution",
        ]
        actual_values = [ct.value for ct in ComponentType]
        for expected in expected_values:
            assert expected in actual_values


class TestComponentLifecycle:
    """Tests for ComponentLifecycle enum."""

    def test_lifecycle_create(self):
        """Test ComponentLifecycle.CREATE value."""
        assert ComponentLifecycle.CREATE.value == "create"

    def test_lifecycle_update(self):
        """Test ComponentLifecycle.UPDATE value."""
        assert ComponentLifecycle.UPDATE.value == "update"

    def test_lifecycle_replace(self):
        """Test ComponentLifecycle.REPLACE value."""
        assert ComponentLifecycle.REPLACE.value == "replace"

    def test_lifecycle_remove(self):
        """Test ComponentLifecycle.REMOVE value."""
        assert ComponentLifecycle.REMOVE.value == "remove"


class TestSimpleComponent:
    """Tests for SimpleComponent class."""

    def test_simplecomponent_instantiation(self):
        """Test SimpleComponent can be instantiated."""
        component = SimpleComponent(type=SimpleComponentType.TEXT)
        assert component.type == SimpleComponentType.TEXT

    def test_simplecomponent_default_metadata(self):
        """Test SimpleComponent has default None metadata."""
        component = SimpleComponent(type=SimpleComponentType.TEXT)
        assert component.metadata is None

    def test_simplecomponent_with_metadata(self):
        """Test SimpleComponent with metadata."""
        component = SimpleComponent(
            type=SimpleComponentType.TEXT,
            metadata={"key": "value"}
        )
        assert component.metadata == {"key": "value"}

    def test_simplecomponent_serialize_for_frontend(self):
        """Test SimpleComponent.serialize_for_frontend()."""
        component = SimpleComponent(
            type=SimpleComponentType.TEXT,
            metadata={"key": "value"}
        )
        serialized = component.serialize_for_frontend()
        assert serialized["type"] == "text"
        assert serialized["metadata"] == {"key": "value"}


class TestSimpleComponentType:
    """Tests for SimpleComponentType enum."""

    def test_simple_type_text(self):
        """Test SimpleComponentType.TEXT value."""
        assert SimpleComponentType.TEXT.value == "text"

    def test_simple_type_image(self):
        """Test SimpleComponentType.IMAGE value."""
        assert SimpleComponentType.IMAGE.value == "image"

    def test_simple_type_link(self):
        """Test SimpleComponentType.LINK value."""
        assert SimpleComponentType.LINK.value == "link"


class TestComponentIntegration:
    """Integration tests for component classes."""

    def test_uicomponent_with_rich_and_simple(self):
        """Test UiComponent with both rich and simple components."""
        rich = RichComponent(type=ComponentType.TEXT, data={"text": "Rich"})
        simple = SimpleComponent(type=SimpleComponentType.TEXT, metadata={"source": "simple"})
        component = UiComponent(
            rich_component=rich,
            simple_component=simple
        )
        assert component.rich_component == rich
        assert component.simple_component == simple

    def test_component_lifecycle_update_propagates(self):
        """Test that update lifecycle is set correctly."""
        component = RichComponent(type=ComponentType.TEXT)
        updated = component.update(data={"new": "data"})
        assert updated.lifecycle == ComponentLifecycle.UPDATE

    def test_component_timestamp_updates_on_update(self):
        """Test that timestamp updates on update."""
        import time
        component = RichComponent(type=ComponentType.TEXT)
        original_timestamp = component.timestamp
        time.sleep(0.01)  # Small delay
        updated = component.update(data={"new": "data"})
        assert updated.timestamp != original_timestamp
