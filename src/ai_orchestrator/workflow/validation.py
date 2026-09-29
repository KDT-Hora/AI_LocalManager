from __future__ import annotations

from pydantic import ValidationError

from ..errors import INVALID_OUTPUT, NOT_FOUND, OrchestratorError
from ..models.task import Task, TaskState
from ..models.validation import Action, Issue, ValidationResult
from ..store.task_store import TaskStore
from .state_machine import require_state, transition


def register_validation(
    store: TaskStore,
    task: Task,
    version: int,
    verdict: str,
    aspects_checked: list[str] | None = None,
    issues: list[dict] | None = None,
    recommended_action: Action | None = None,
) -> Task:
    """Store Claude's verdict. pass keeps REVIEWING; fail -> REVISION_REQUIRED."""
    require_state(task, TaskState.REVIEWING)
    if version not in task.versions:
        raise OrchestratorError(NOT_FOUND, f"{task.task_id} has no version {version}")
    try:
        result = ValidationResult(
            version=version,
            verdict=verdict,  # type: ignore[arg-type]
            aspects_checked=aspects_checked or [],
            issues=[Issue(**i) for i in (issues or [])],
            recommended_action=recommended_action,
        )
    except (ValidationError, TypeError) as e:
        raise OrchestratorError(INVALID_OUTPUT, f"invalid validation: {e}") from e
    store.save_validation(task.task_id, result)
    if verdict == "fail":
        transition(task, TaskState.REVISION_REQUIRED, f"v{version:03d} failed validation")
    store.save(task)
    return task
