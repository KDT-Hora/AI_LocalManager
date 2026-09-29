from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


def now() -> datetime:
    return datetime.now(UTC)


class TaskState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    REVIEWING = "REVIEWING"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StateEvent(BaseModel):
    state: TaskState
    at: datetime = Field(default_factory=now)
    reason: str = ""


class TaskError(BaseModel):
    kind: str
    message: str
    retryable: bool = False


class Task(BaseModel):
    task_id: str = Field(pattern=r"^TASK-\d{3,}$")
    request: str
    required_capabilities: list[str] = Field(min_length=1)
    category: str
    state: TaskState = TaskState.PENDING
    state_history: list[StateEvent] = Field(default_factory=list)
    selected_model_id: str | None = None
    selection_reason: str | None = None
    model_snapshot: dict | None = None
    excluded_model_ids: list[str] = Field(default_factory=list)
    revision_count: int = Field(default=0, ge=0)
    max_revisions: int = Field(default=3, ge=0)
    versions: list[int] = Field(default_factory=list)
    final_version: int | None = None
    error: TaskError | None = None
    input_files: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    @model_validator(mode="after")
    def _limit(self) -> Task:
        if self.revision_count > self.max_revisions:
            raise ValueError("revision_count exceeds max_revisions")
        return self
