"""Startup recovery: tasks left RUNNING/RETRYING by an interrupted process (FR-019)."""

from __future__ import annotations

from ..errors import OrchestratorError
from ..logging_setup import get_logger
from ..models.task import TaskState
from ..store.task_store import TaskStore

STALE = {TaskState.RUNNING, TaskState.RETRYING}


def recover_stale_tasks(store: TaskStore) -> list[str]:
    recovered: list[str] = []
    for task_id in store.list_ids():
        try:
            task = store.load(task_id)
        except OrchestratorError as e:
            get_logger().warning("recovery skipped %s: %s", task_id, e.message)
            continue
        if task.state in STALE:
            store.fail(task, "interrupted", "process stopped while the task was running", True)
            recovered.append(task_id)
    return recovered
