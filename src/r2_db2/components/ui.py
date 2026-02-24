"""UI state components for status/task/chat updates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from pydantic import Field

from r2-db2.core.rich_component import ComponentType, RichComponent


@dataclass
class Task:
    """Simple task model used for tracking progress."""

    title: str
    description: str = ""
    status: str = "pending"
    id: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
        }


class StatusBarUpdateComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.STATUS_BAR_UPDATE)
    status: str = Field(..., description="Status value")
    message: str = Field(default="")
    detail: str = Field(default="")


class TaskTrackerUpdateComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.TASK_TRACKER_UPDATE)
    operation: str = Field(default="add")
    task: Optional[Dict[str, Any]] = Field(default=None)

    @classmethod
    def add_task(cls, task: Task) -> "TaskTrackerUpdateComponent":
        return cls(operation="add", task=task.to_dict())

    @classmethod
    def update_task(
        cls, task_id: str, *, status: str, detail: Optional[str] = None
    ) -> "TaskTrackerUpdateComponent":
        payload: Dict[str, Any] = {"id": task_id, "status": status}
        if detail is not None:
            payload["detail"] = detail
        return cls(operation="update", task=payload)


class ChatInputUpdateComponent(RichComponent):
    type: ComponentType = Field(default=ComponentType.CHAT_INPUT_UPDATE)
    placeholder: str = Field(default="")
    disabled: bool = Field(default=False)
