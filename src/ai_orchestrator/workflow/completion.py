from __future__ import annotations

from pathlib import Path

from ..errors import INVALID_TRANSITION, NOT_FOUND, OrchestratorError
from ..models.task import Task, TaskState
from ..store.task_store import TaskStore
from .state_machine import require_state, transition


def complete(store: TaskStore, task: Task, version: int) -> tuple[Task, Path]:
    """Complete only with a passing validation on that version (FR-020)."""
    require_state(task, TaskState.REVIEWING)
    if version not in task.versions:
        raise OrchestratorError(NOT_FOUND, f"{task.task_id} has no version {version}")
    latest = store.latest_validation(task.task_id, version)
    if latest is None or latest.verdict != "pass":
        raise OrchestratorError(
            INVALID_TRANSITION,
            f"{task.task_id} v{version:03d} has no passing validation; cannot complete",
        )
    path = store.publish_artifact(task, version)
    task.final_version = version
    transition(task, TaskState.COMPLETED, f"v{version:03d} accepted")
    store.save(task)
    return task, path
