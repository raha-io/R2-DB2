"""Rich UI component implementations used by the agent runtime."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field

# Re-export ComponentLifecycle and ComponentType so other modules can import from here
from r2-db2.core.rich_component import (
    ComponentLifecycle,
    ComponentType,
    RichComponent,
)


class RichTextComponent(RichComponent):
    """Markdown-capable text component."""

    type: ComponentType = Field(default=ComponentType.TEXT)
    content: str = Field(..., description="Markdown or plain text content")
    markdown: bool = Field(default=True)


class StatusCardComponent(RichComponent):
    """Status card for displaying progress and errors."""

    type: ComponentType = Field(default=ComponentType.STATUS_CARD)
    title: str = Field(..., description="Card title")
    status: str = Field(..., description="Status label")
    description: str = Field(default="")
    icon: Optional[str] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default=None)

    def set_status(self, status: str, description: str) -> "StatusCardComponent":
        """Return a new status card with updated status/description."""
        return self.update(status=status, description=description)


class ProgressBarComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.PROGRESS_BAR)
    progress: float = Field(..., ge=0.0, le=1.0)
    label: Optional[str] = None


class ProgressDisplayComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.PROGRESS_DISPLAY)
    title: str = Field(...)
    current: int = Field(..., ge=0)
    total: int = Field(..., ge=0)


class LogViewerComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.LOG_VIEWER)
    lines: List[str] = Field(default_factory=list)


class NotificationComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.NOTIFICATION)
    title: str = Field(default="")
    message: str = Field(...)
    level: str = Field(default="info")


class BadgeComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.BADGE)
    text: str = Field(...)
    color: Optional[str] = None


class IconTextComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.ICON_TEXT)
    icon: str = Field(...)
    text: str = Field(...)


class CardComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.CARD)
    title: str = Field(...)
    content: Optional[str] = None


class ButtonComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.BUTTON)
    label: str = Field(...)
    action: str = Field(..., description="Action identifier to send back to the client")
    variant: Optional[str] = Field(default=None)
    disabled: bool = Field(default=False)


class ButtonGroupComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.BUTTON_GROUP)
    buttons: List[Dict[str, Any]] = Field(default_factory=list)


class ChartComponent(RichComponent):
    """Chart component for Plotly or other chart types."""

    type: ComponentType = Field(default=ComponentType.CHART)
    chart_type: str = Field(default="plotly")
    spec: Dict[str, Any] = Field(default_factory=dict)
    title: Optional[str] = Field(default=None)
    config: Optional[Dict[str, Any]] = Field(default=None)

    def __init__(self, **data: Any) -> None:
        # Allow passing chart data directly as 'data' kwarg (maps to spec)
        if "data" in data and "spec" not in data:
            data["spec"] = data.pop("data")
        super().__init__(**data)


class DataFrameComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.DATAFRAME)
    columns: List[str] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    title: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)

    @classmethod
    def from_records(
        cls,
        records: List[Dict[str, Any]],
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> "DataFrameComponent":
        """Create a DataFrameComponent from a list of record dicts."""
        if not records:
            return cls(columns=[], rows=[], title=title, description=description)
        columns = list(records[0].keys())
        rows = [[row.get(col) for col in columns] for row in records]
        return cls(columns=columns, rows=rows, title=title, description=description)


class TaskListComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.TASK_LIST)
    tasks: List[Dict[str, Any]] = Field(default_factory=list)


class ArtifactComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.ARTIFACT)
    name: str = Field(...)
    uri: str = Field(...)
    kind: Optional[str] = Field(default=None)
