"""
R2-DB2 UI Components.

This package provides all component classes used by the agent runtime,
tools, and workflow engine.
"""

# Re-export base types from core
from r2-db2.core.components import UiComponent
from r2-db2.core.simple_component import SimpleComponent, SimpleComponentType
from r2-db2.core.rich_component import RichComponent, ComponentType, ComponentLifecycle

# Simple components
from .simple import (
    SimpleTextComponent,
    SimpleImageComponent,
    SimpleLinkComponent,
)

# Rich components
from .rich import (
    ArtifactComponent,
    BadgeComponent,
    ButtonComponent,
    ButtonGroupComponent,
    CardComponent,
    ChartComponent,
    DataFrameComponent,
    IconTextComponent,
    LogViewerComponent,
    NotificationComponent,
    ProgressBarComponent,
    ProgressDisplayComponent,
    RichTextComponent,
    StatusCardComponent,
    TaskListComponent,
)

# UI state components
from .ui import (
    ChatInputUpdateComponent,
    StatusBarUpdateComponent,
    Task,
    TaskTrackerUpdateComponent,
)

__all__ = [
    # Base types
    "UiComponent",
    "SimpleComponent",
    "SimpleComponentType",
    "RichComponent",
    "ComponentType",
    "ComponentLifecycle",
    # Simple components
    "SimpleTextComponent",
    "SimpleImageComponent",
    "SimpleLinkComponent",
    # Rich components
    "ArtifactComponent",
    "BadgeComponent",
    "ButtonComponent",
    "ButtonGroupComponent",
    "CardComponent",
    "ChartComponent",
    "DataFrameComponent",
    "IconTextComponent",
    "LogViewerComponent",
    "NotificationComponent",
    "ProgressBarComponent",
    "ProgressDisplayComponent",
    "RichTextComponent",
    "StatusCardComponent",
    "TaskListComponent",
    # UI state components
    "ChatInputUpdateComponent",
    "StatusBarUpdateComponent",
    "Task",
    "TaskTrackerUpdateComponent",
]
