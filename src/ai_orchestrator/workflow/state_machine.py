"""Task state transitions (data-model.md)."""

from __future__ import annotations

from ..errors import INVALID_TRANSITION, OrchestratorError
from ..models.task import StateEvent, Task, TaskState, now

S = TaskState

TRANSITIONS: dict[TaskState, set[TaskState]] = {
    S.PENDING: {S.RUNNING, S.FAILED},
    S.RUNNING: {S.REVIEWING, S.FAILED},
    # REVIEWING -> RETRYING: further revision of a version that already passed
    S.REVIEWING: {S.COMPLETED, S.REVISION_REQUIRED, S.RETRYING, S.FAILED},
    S.REVISION_REQUIRED: {S.RETRYING, S.FAILED},
    S.RETRYING: {S.RUNNING, S.FAILED},
    S.COMPLETED: set(),
    S.FAILED: {S.PENDING},
}


def can_transition(current: TaskState, new: TaskState) -> bool:
    return new in TRANSITIONS[current]


def transition(task: Task, new: TaskState, reason: str = "") -> Task:
    if not can_transition(task.state, new):
        raise OrchestratorError(
            INVALID_TRANSITION, f"{task.task_id}: {task.state} -> {new} is not allowed"
        )
    task.state = new
    task.state_history.append(StateEvent(state=new, reason=reason))
    task.updated_at = now()
    return task


def require_state(task: Task, *allowed: TaskState) -> None:
    if task.state not in allowed:
        names = "/".join(s.value for s in allowed)
        raise OrchestratorError(
            INVALID_TRANSITION, f"{task.task_id} is {task.state}; requires {names}"
        )
