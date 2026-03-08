"""Tests for src/r2-db2/core/component_manager.py."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from r2-db2.core.rich_component import (
    RichComponent,
    ComponentType,
    ComponentLifecycle,
)
from r2-db2.core.component_manager import (
    ComponentManager,
    ComponentTree,
    ComponentNode,
    ComponentUpdate,
    UpdateOperation,
    Position,
)


# Fixtures
@pytest.fixture
def component_manager():
    """Create a fresh ComponentManager instance."""
    return ComponentManager()


@pytest.fixture
def sample_rich_component():
    """Create a sample RichComponent for testing."""
    return RichComponent(
        type=ComponentType.TEXT,
        data={"text": "Hello, World!"},
        visible=True,
    )


@pytest.fixture
def sample_rich_component_2():
    """Create a second sample RichComponent for testing."""
    return RichComponent(
        type=ComponentType.CARD,
        data={"title": "Test Card"},
        visible=True,
    )


# Tests for UpdateOperation enum
class TestUpdateOperation:
    """Tests for UpdateOperation enum."""

    def test_update_operation_create(self):
        """Test UpdateOperation.CREATE value."""
        assert UpdateOperation.CREATE.value == "create"

    def test_update_operation_update(self):
        """Test UpdateOperation.UPDATE value."""
        assert UpdateOperation.UPDATE.value == "update"

    def test_update_operation_replace(self):
        """Test UpdateOperation.REPLACE value."""
        assert UpdateOperation.REPLACE.value == "replace"

    def test_update_operation_remove(self):
        """Test UpdateOperation.REMOVE value."""
        assert UpdateOperation.REMOVE.value == "remove"

    def test_update_operation_reorder(self):
        """Test UpdateOperation.REORDER value."""
        assert UpdateOperation.REORDER.value == "reorder"

    def test_update_operation_bulk_update(self):
        """Test UpdateOperation.BULK_UPDATE value."""
        assert UpdateOperation.BULK_UPDATE.value == "bulk_update"


# Tests for Position class
class TestPosition:
    """Tests for Position class."""

    def test_position_with_index(self):
        """Test Position with index."""
        position = Position(index=5)
        assert position.index == 5
        assert position.anchor_id is None
        assert position.relation == "after"

    def test_position_with_anchor_id(self):
        """Test Position with anchor_id."""
        position = Position(anchor_id="test-id", relation="before")
        assert position.anchor_id == "test-id"
        assert position.relation == "before"
        assert position.index is None

    def test_position_default_relation(self):
        """Test Position default relation is 'after'."""
        position = Position(anchor_id="test-id")
        assert position.relation == "after"

    def test_position_all_fields(self):
        """Test Position with all fields."""
        position = Position(index=3, anchor_id="parent-id", relation="inside")
        assert position.index == 3
        assert position.anchor_id == "parent-id"
        assert position.relation == "inside"


# Tests for ComponentUpdate class
class TestComponentUpdate:
    """Tests for ComponentUpdate class."""

    def test_component_update_basic(self, sample_rich_component):
        """Test ComponentUpdate basic creation."""
        update = ComponentUpdate(
            operation=UpdateOperation.CREATE,
            target_id=sample_rich_component.id,
            component=sample_rich_component,
        )
        assert update.operation == UpdateOperation.CREATE
        assert update.target_id == sample_rich_component.id
        assert update.component == sample_rich_component
        assert update.timestamp is not None

    def test_component_update_with_updates_dict(self, sample_rich_component):
        """Test ComponentUpdate with updates dict."""
        update = ComponentUpdate(
            operation=UpdateOperation.UPDATE,
            target_id=sample_rich_component.id,
            updates={"visible": False, "data": {"new": "data"}},
        )
        assert update.operation == UpdateOperation.UPDATE
        assert update.updates == {"visible": False, "data": {"new": "data"}}

    def test_component_update_with_position(self, sample_rich_component):
        """Test ComponentUpdate with position."""
        position = Position(index=5, relation="after")
        update = ComponentUpdate(
            operation=UpdateOperation.CREATE,
            target_id=sample_rich_component.id,
            component=sample_rich_component,
            position=position,
        )
        assert update.position == position

    def test_component_update_batch_id(self, sample_rich_component):
        """Test ComponentUpdate with batch_id."""
        batch_id = "batch-123"
        update = ComponentUpdate(
            operation=UpdateOperation.CREATE,
            target_id=sample_rich_component.id,
            component=sample_rich_component,
            batch_id=batch_id,
        )
        assert update.batch_id == batch_id

    def test_component_update_serialize_for_frontend(self, sample_rich_component):
        """Test ComponentUpdate.serialize_for_frontend()."""
        update = ComponentUpdate(
            operation=UpdateOperation.CREATE,
            target_id=sample_rich_component.id,
            component=sample_rich_component,
        )
        serialized = update.serialize_for_frontend()
        assert serialized["operation"] == "create"
        assert serialized["target_id"] == sample_rich_component.id
        assert "component" in serialized
        assert serialized["component"]["type"] == "text"

    def test_component_update_serialize_preserves_operation_enum(self, sample_rich_component):
        """Test that operation enum is converted to string value."""
        update = ComponentUpdate(
            operation=UpdateOperation.UPDATE,
            target_id=sample_rich_component.id,
            updates={"visible": False},
        )
        serialized = update.serialize_for_frontend()
        assert serialized["operation"] == "update"
        assert isinstance(serialized["operation"], str)

    def test_component_update_serialize_with_none_component(self):
        """Test serialization with None component."""
        update = ComponentUpdate(
            operation=UpdateOperation.REMOVE,
            target_id="component-id",
        )
        serialized = update.serialize_for_frontend()
        assert serialized["operation"] == "remove"
        assert serialized["target_id"] == "component-id"
        assert serialized.get("component") is None


# Tests for ComponentNode class
class TestComponentNode:
    """Tests for ComponentNode class."""

    def test_component_node_basic(self, sample_rich_component):
        """Test ComponentNode basic creation."""
        node = ComponentNode(component=sample_rich_component)
        assert node.component == sample_rich_component
        assert node.children == []
        assert node.parent_id is None

    def test_component_node_with_children(self, sample_rich_component, sample_rich_component_2):
        """Test ComponentNode with children."""
        child_node = ComponentNode(component=sample_rich_component_2)
        node = ComponentNode(
            component=sample_rich_component,
            children=[child_node],
        )
        assert len(node.children) == 1
        assert node.children[0].component == sample_rich_component_2

    def test_component_node_find_child(self, sample_rich_component, sample_rich_component_2):
        """Test ComponentNode.find_child()."""
        child_node = ComponentNode(component=sample_rich_component_2)
        parent_node = ComponentNode(
            component=sample_rich_component,
            children=[child_node],
        )
        found = parent_node.find_child(sample_rich_component_2.id)
        assert found == child_node

    def test_component_node_find_child_not_found(self, sample_rich_component):
        """Test ComponentNode.find_child() returns None when not found."""
        node = ComponentNode(component=sample_rich_component)
        found = node.find_child("non-existent-id")
        assert found is None

    def test_component_node_find_child_nested(self, sample_rich_component, sample_rich_component_2):
        """Test ComponentNode.find_child() with nested structure."""
        grandchild = ComponentNode(component=sample_rich_component_2)
        child = ComponentNode(component=sample_rich_component, children=[grandchild])
        parent = ComponentNode(component=sample_rich_component, children=[child])

        found = parent.find_child(sample_rich_component_2.id)
        assert found == grandchild

    def test_component_node_remove_child(self, sample_rich_component, sample_rich_component_2):
        """Test ComponentNode.remove_child()."""
        child_node = ComponentNode(component=sample_rich_component_2)
        parent_node = ComponentNode(
            component=sample_rich_component,
            children=[child_node],
        )
        removed = parent_node.remove_child(sample_rich_component_2.id)
        assert removed is True
        assert len(parent_node.children) == 0

    def test_component_node_remove_child_not_found(self, sample_rich_component):
        """Test ComponentNode.remove_child() returns False when not found."""
        node = ComponentNode(component=sample_rich_component)
        removed = node.remove_child("non-existent-id")
        assert removed is False

    def test_component_node_get_all_ids(self, sample_rich_component, sample_rich_component_2):
        """Test ComponentNode.get_all_ids()."""
        child_node = ComponentNode(component=sample_rich_component_2)
        parent_node = ComponentNode(
            component=sample_rich_component,
            children=[child_node],
        )
        all_ids = parent_node.get_all_ids()
        assert sample_rich_component.id in all_ids
        assert sample_rich_component_2.id in all_ids
        assert len(all_ids) == 2

    def test_component_node_get_all_ids_nested(self, sample_rich_component, sample_rich_component_2):
        """Test ComponentNode.get_all_ids() with deep nesting."""
        grandchild = ComponentNode(component=sample_rich_component_2)
        child = ComponentNode(component=sample_rich_component, children=[grandchild])
        parent = ComponentNode(component=sample_rich_component, children=[child])

        all_ids = parent.get_all_ids()
        assert sample_rich_component.id in all_ids
        assert sample_rich_component_2.id in all_ids
        assert len(all_ids) == 2


# Tests for ComponentTree class
class TestComponentTree:
    """Tests for ComponentTree class."""

    def test_component_tree_basic(self):
        """Test ComponentTree basic creation."""
        tree = ComponentTree()
        assert tree.root is None
        assert tree.flat_index == {}

    def test_component_tree_add_component(self, sample_rich_component, component_manager):
        """Test ComponentTree.add_component()."""
        tree = ComponentTree()
        update = tree.add_component(sample_rich_component)

        assert tree.root is not None
        assert tree.root.component == sample_rich_component
        assert sample_rich_component.id in tree.flat_index
        assert update.operation == UpdateOperation.CREATE
        assert update.target_id == sample_rich_component.id
        assert update.component == sample_rich_component

    def test_component_tree_add_component_with_position(self, sample_rich_component, sample_rich_component_2):
        """Test ComponentTree.add_component() with position."""
        tree = ComponentTree()
        # Add parent first
        tree.add_component(sample_rich_component)
        # Add child with position
        position = Position(anchor_id=sample_rich_component.id, relation="inside")
        update = tree.add_component(sample_rich_component_2, position)

        assert tree.root is not None
        assert len(tree.root.children) == 1
        assert tree.root.children[0].component == sample_rich_component_2
        assert update.position == position

    def test_component_tree_update_component(self, sample_rich_component):
        """Test ComponentTree.update_component()."""
        tree = ComponentTree()
        tree.add_component(sample_rich_component)
        update = tree.update_component(sample_rich_component.id, {"visible": False})

        assert update is not None
        assert update.operation == UpdateOperation.UPDATE
        assert update.component.visible is False
        assert tree.flat_index[sample_rich_component.id].component.visible is False

    def test_component_tree_update_component_not_found(self, sample_rich_component):
        """Test ComponentTree.update_component() returns None when not found."""
        tree = ComponentTree()
        update = tree.update_component("non-existent-id", {"visible": False})
        assert update is None

    def test_component_tree_replace_component(self, sample_rich_component, sample_rich_component_2):
        """Test ComponentTree.replace_component()."""
        tree = ComponentTree()
        tree.add_component(sample_rich_component)
        update = tree.replace_component(sample_rich_component.id, sample_rich_component_2)

        assert update is not None
        assert update.operation == UpdateOperation.REPLACE
        assert tree.flat_index[sample_rich_component_2.id].component == sample_rich_component_2
        assert sample_rich_component.id not in tree.flat_index

    def test_component_tree_replace_component_not_found(self, sample_rich_component):
        """Test ComponentTree.replace_component() returns None when not found."""
        tree = ComponentTree()
        update = tree.replace_component("non-existent-id", sample_rich_component)
        assert update is None

    def test_component_tree_remove_component(self, sample_rich_component):
        """Test ComponentTree.remove_component()."""
        tree = ComponentTree()
        tree.add_component(sample_rich_component)
        update = tree.remove_component(sample_rich_component.id)

        assert update is not None
        assert update.operation == UpdateOperation.REMOVE
        assert sample_rich_component.id not in tree.flat_index
        assert tree.root is None

    def test_component_tree_remove_component_not_found(self):
        """Test ComponentTree.remove_component() returns None when not found."""
        tree = ComponentTree()
        update = tree.remove_component("non-existent-id")
        assert update is None

    def test_component_tree_remove_component_with_children(self, sample_rich_component, sample_rich_component_2):
        """Test ComponentTree.remove_component() removes children."""
        tree = ComponentTree()
        tree.add_component(sample_rich_component)
        position = Position(anchor_id=sample_rich_component.id, relation="inside")
        tree.add_component(sample_rich_component_2, position)

        update = tree.remove_component(sample_rich_component.id)
        assert update is not None
        assert sample_rich_component.id not in tree.flat_index
        assert sample_rich_component_2.id not in tree.flat_index

    def test_component_tree_get_component(self, sample_rich_component):
        """Test ComponentTree.get_component()."""
        tree = ComponentTree()
        tree.add_component(sample_rich_component)
        component = tree.get_component(sample_rich_component.id)

        assert component == sample_rich_component

    def test_component_tree_get_component_not_found(self):
        """Test ComponentTree.get_component() returns None when not found."""
        tree = ComponentTree()
        component = tree.get_component("non-existent-id")
        assert component is None

    def test_component_tree_find_parent_inside(self, sample_rich_component, sample_rich_component_2):
        """Test ComponentTree._find_parent() with inside relation."""
        tree = ComponentTree()
        tree.add_component(sample_rich_component)
        position = Position(anchor_id=sample_rich_component.id, relation="inside")
        parent = tree._find_parent(position)

        assert parent == tree.flat_index[sample_rich_component.id]

    def test_component_tree_find_parent_after(self, sample_rich_component, sample_rich_component_2):
        """Test ComponentTree._find_parent() with after relation."""
        tree = ComponentTree()
        tree.add_component(sample_rich_component)
        tree.add_component(sample_rich_component_2)
        position = Position(anchor_id=sample_rich_component.id, relation="after")
        parent = tree._find_parent(position)

        # Parent should be root since anchor has no parent
        assert parent == tree.root

    def test_component_tree_find_parent_no_anchor(self, sample_rich_component):
        """Test ComponentTree._find_parent() returns root when no anchor."""
        tree = ComponentTree()
        tree.add_component(sample_rich_component)
        position = Position(index=5)
        parent = tree._find_parent(position)

        assert parent == tree.root

    def test_component_tree_find_parent_invalid_anchor(self, sample_rich_component):
        """Test ComponentTree._find_parent() returns root when anchor not found."""
        tree = ComponentTree()
        tree.add_component(sample_rich_component)
        position = Position(anchor_id="non-existent-id", relation="inside")
        parent = tree._find_parent(position)

        assert parent == tree.root


# Tests for ComponentManager class
class TestComponentManager:
    """Tests for ComponentManager class."""

    def test_component_manager_init(self):
        """Test ComponentManager initialization."""
        manager = ComponentManager()
        assert manager.components == {}
        assert manager.component_tree is not None
        assert manager.update_history == []
        assert manager.active_batch is None

    def test_component_manager_emit_new_component(self, component_manager, sample_rich_component):
        """Test ComponentManager.emit() with new component."""
        update = component_manager.emit(sample_rich_component)

        assert update is not None
        assert update.operation == UpdateOperation.CREATE
        assert sample_rich_component.id in component_manager.components
        assert len(component_manager.update_history) == 1

    def test_component_manager_emit_update_component(self, component_manager, sample_rich_component):
        """Test ComponentManager.emit() with UPDATE lifecycle."""
        component_manager.emit(sample_rich_component)
        updated_component = sample_rich_component.update(visible=False)
        updated_component.lifecycle = ComponentLifecycle.UPDATE

        update = component_manager.emit(updated_component)

        assert update is not None
        assert update.operation == UpdateOperation.UPDATE
        assert component_manager.components[sample_rich_component.id].visible is False

    def test_component_manager_emit_replace_component(self, component_manager, sample_rich_component, sample_rich_component_2):
        """Test ComponentManager.emit() with REPLACE lifecycle."""
        component_manager.emit(sample_rich_component)
        sample_rich_component_2.lifecycle = ComponentLifecycle.REPLACE

        update = component_manager.emit(sample_rich_component_2)

        assert update is not None
        # REPLACE lifecycle in emit() is treated as a new component (CREATE)
        # because it has a different ID
        assert update.operation == UpdateOperation.CREATE
        assert sample_rich_component_2.id in component_manager.components
        assert sample_rich_component.id in component_manager.components  # Both exist since different IDs

    def test_component_manager_update_component(self, component_manager, sample_rich_component):
        """Test ComponentManager.update_component()."""
        component_manager.emit(sample_rich_component)
        update = component_manager.update_component(sample_rich_component.id, visible=False)

        assert update is not None
        assert update.operation == UpdateOperation.UPDATE
        assert component_manager.components[sample_rich_component.id].visible is False

    def test_component_manager_update_component_not_found(self, component_manager):
        """Test ComponentManager.update_component() returns None when not found."""
        update = component_manager.update_component("non-existent-id", visible=False)
        assert update is None

    def test_component_manager_replace_component(self, component_manager, sample_rich_component, sample_rich_component_2):
        """Test ComponentManager.replace_component()."""
        component_manager.emit(sample_rich_component)
        update = component_manager.replace_component(sample_rich_component.id, sample_rich_component_2)

        assert update is not None
        assert update.operation == UpdateOperation.REPLACE
        assert sample_rich_component_2.id in component_manager.components
        assert sample_rich_component.id not in component_manager.components

    def test_component_manager_replace_component_not_found(self, component_manager, sample_rich_component):
        """Test ComponentManager.replace_component() returns None when not found."""
        update = component_manager.replace_component("non-existent-id", sample_rich_component)
        assert update is None

    def test_component_manager_remove_component(self, component_manager, sample_rich_component):
        """Test ComponentManager.remove_component()."""
        component_manager.emit(sample_rich_component)
        update = component_manager.remove_component(sample_rich_component.id)

        assert update is not None
        assert update.operation == UpdateOperation.REMOVE
        assert sample_rich_component.id not in component_manager.components

    def test_component_manager_remove_component_not_found(self, component_manager):
        """Test ComponentManager.remove_component() returns None when not found."""
        update = component_manager.remove_component("non-existent-id")
        assert update is None

    def test_component_manager_get_component(self, component_manager, sample_rich_component):
        """Test ComponentManager.get_component()."""
        component_manager.emit(sample_rich_component)
        component = component_manager.get_component(sample_rich_component.id)

        assert component == sample_rich_component

    def test_component_manager_get_component_not_found(self, component_manager):
        """Test ComponentManager.get_component() returns None when not found."""
        component = component_manager.get_component("non-existent-id")
        assert component is None

    def test_component_manager_get_all_components(self, component_manager, sample_rich_component, sample_rich_component_2):
        """Test ComponentManager.get_all_components()."""
        component_manager.emit(sample_rich_component)
        component_manager.emit(sample_rich_component_2)

        components = component_manager.get_all_components()

        assert len(components) == 2
        assert sample_rich_component in components
        assert sample_rich_component_2 in components

    def test_component_manager_start_batch(self, component_manager):
        """Test ComponentManager.start_batch()."""
        batch_id = component_manager.start_batch()

        assert batch_id is not None
        assert component_manager.active_batch == batch_id
        assert len(batch_id) > 0  # UUID format

    def test_component_manager_end_batch(self, component_manager):
        """Test ComponentManager.end_batch()."""
        component_manager.start_batch()
        batch_id = component_manager.end_batch()

        assert batch_id is not None  # Returned the batch_id
        assert component_manager.active_batch is None  # Cleared after end

    def test_component_manager_batch_id_propagates(self, component_manager, sample_rich_component):
        """Test that batch_id propagates to updates."""
        batch_id = component_manager.start_batch()
        update = component_manager.emit(sample_rich_component)

        assert update.batch_id == batch_id

    def test_component_manager_get_updates_since_no_timestamp(self, component_manager, sample_rich_component):
        """Test ComponentManager.get_updates_since() with no timestamp."""
        component_manager.emit(sample_rich_component)
        updates = component_manager.get_updates_since()

        assert len(updates) == 1
        assert updates[0].target_id == sample_rich_component.id

    def test_component_manager_get_updates_since_with_timestamp(self, component_manager, sample_rich_component):
        """Test ComponentManager.get_updates_since() with timestamp."""
        component_manager.emit(sample_rich_component)
        # Get the timestamp of the first update
        first_timestamp = component_manager.update_history[0].timestamp

        # Add a small delay and emit another component
        import time
        time.sleep(0.01)
        component_manager.emit(sample_rich_component)

        # Get updates since the first timestamp
        updates = component_manager.get_updates_since(first_timestamp)

        # Should get the second update (and possibly the first depending on timing)
        assert len(updates) >= 1

    def test_component_manager_get_updates_since_invalid_timestamp(self, component_manager, sample_rich_component):
        """Test ComponentManager.get_updates_since() with invalid timestamp."""
        component_manager.emit(sample_rich_component)
        updates = component_manager.get_updates_since("invalid-timestamp")

        # Should return all updates on invalid timestamp
        assert len(updates) == 1

    def test_component_manager_clear_history(self, component_manager, sample_rich_component):
        """Test ComponentManager.clear_history()."""
        component_manager.emit(sample_rich_component)
        component_manager.clear_history()

        assert component_manager.update_history == []

    def test_component_manager_multiple_emits(self, component_manager, sample_rich_component):
        """Test ComponentManager with multiple emits."""
        for i in range(5):
            comp = sample_rich_component.update(data={"index": i})
            component_manager.emit(comp)

        assert len(component_manager.components) == 1  # Same ID, so replaced
        assert len(component_manager.update_history) == 5

    def test_component_manager_emit_with_batch(self, component_manager, sample_rich_component, sample_rich_component_2):
        """Test ComponentManager.emit() with active batch."""
        batch_id = component_manager.start_batch()
        update1 = component_manager.emit(sample_rich_component)
        update2 = component_manager.emit(sample_rich_component_2)

        assert update1.batch_id == batch_id
        assert update2.batch_id == batch_id
        assert component_manager.active_batch == batch_id


# Tests for ComponentManager lifecycle
class TestComponentManagerLifecycle:
    """Tests for ComponentManager lifecycle operations."""

    def test_component_manager_full_lifecycle(self, component_manager):
        """Test full component lifecycle: emit -> update -> remove."""
        component = RichComponent(type=ComponentType.TEXT, data={"text": "Initial"})
        update = component_manager.emit(component)
        assert update.operation == UpdateOperation.CREATE

        update = component_manager.update_component(component.id, data={"text": "Updated"})
        assert update.operation == UpdateOperation.UPDATE

        update = component_manager.remove_component(component.id)
        assert update.operation == UpdateOperation.REMOVE

        assert component.id not in component_manager.components

    def test_component_manager_tree_structure(self, component_manager):
        """Test component tree structure with parent-child relationships."""
        parent = RichComponent(type=ComponentType.CARD, data={"title": "Parent"})
        child1 = RichComponent(type=ComponentType.TEXT, data={"text": "Child 1"})
        child2 = RichComponent(type=ComponentType.TEXT, data={"text": "Child 2"})

        component_manager.emit(parent)
        component_manager.update_component(parent.id, children=[child1.id, child2.id])

        assert parent.id in component_manager.components
        assert component_manager.components[parent.id].children == [child1.id, child2.id]


# Tests for edge cases
class TestComponentManagerEdgeCases:
    """Tests for ComponentManager edge cases."""

    def test_component_manager_empty_manager(self, component_manager):
        """Test ComponentManager with no components."""
        assert component_manager.components == {}
        assert component_manager.get_all_components() == []
        assert component_manager.get_component("any-id") is None

    def test_component_manager_duplicate_component_id(self, component_manager, sample_rich_component):
        """Test ComponentManager with duplicate component IDs."""
        component_manager.emit(sample_rich_component)
        component_manager.emit(sample_rich_component)  # Same ID

        # Should have only one component (replaced)
        assert len(component_manager.components) == 1
        assert len(component_manager.update_history) == 2

    def test_component_manager_update_nonexistent(self, component_manager):
        """Test ComponentManager.update_component() with nonexistent ID."""
        update = component_manager.update_component("nonexistent", visible=False)
        assert update is None

    def test_component_manager_remove_nonexistent(self, component_manager):
        """Test ComponentManager.remove_component() with nonexistent ID."""
        update = component_manager.remove_component("nonexistent")
        assert update is None

    def test_component_manager_replace_nonexistent(self, component_manager, sample_rich_component):
        """Test ComponentManager.replace_component() with nonexistent ID."""
        update = component_manager.replace_component("nonexistent", sample_rich_component)
        assert update is None

    def test_component_manager_get_updates_empty_history(self, component_manager):
        """Test ComponentManager.get_updates_since() with empty history."""
        updates = component_manager.get_updates_since()
        assert updates == []

    def test_component_manager_clear_empty_history(self, component_manager):
        """Test ComponentManager.clear_history() with empty history."""
        component_manager.clear_history()  # Should not raise
        assert component_manager.update_history == []

    def test_component_manager_batch_without_start(self, component_manager, sample_rich_component):
        """Test ComponentManager.emit() without starting batch."""
        update = component_manager.emit(sample_rich_component)
        assert update.batch_id is None

    def test_component_manager_end_batch_without_start(self, component_manager):
        """Test ComponentManager.end_batch() without starting batch."""
        batch_id = component_manager.end_batch()
        assert batch_id is None

    def test_component_manager_nested_batch_operations(self, component_manager, sample_rich_component):
        """Test ComponentManager with nested batch operations."""
        batch1 = component_manager.start_batch()
        component_manager.emit(sample_rich_component)

        batch2 = component_manager.start_batch()  # Nested
        component_manager.emit(sample_rich_component)

        component_manager.end_batch()
        component_manager.end_batch()

        assert component_manager.active_batch is None
