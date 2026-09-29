import pytest

from ai_orchestrator.errors import OrchestratorError
from ai_orchestrator.models.task import Task, TaskState
from ai_orchestrator.workflow.state_machine import can_transition, transition


def make_task() -> Task:
    return Task(task_id="TASK-001", request="r", required_capabilities=["story"], category="story")


def test_valid_path_and_history():
    t = make_task()
    for s in (
        TaskState.RUNNING,
        TaskState.REVIEWING,
        TaskState.REVISION_REQUIRED,
        TaskState.RETRYING,
        TaskState.RUNNING,
        TaskState.REVIEWING,
        TaskState.COMPLETED,
    ):
        transition(t, s, "x")
    assert t.state == TaskState.COMPLETED
    assert [e.state for e in t.state_history][-1] == TaskState.COMPLETED
    assert len(t.state_history) == 7


@pytest.mark.parametrize(
    "start,new",
    [
        (TaskState.PENDING, TaskState.REVIEWING),
        (TaskState.PENDING, TaskState.COMPLETED),
        (TaskState.RUNNING, TaskState.COMPLETED),
        (TaskState.COMPLETED, TaskState.FAILED),
        (TaskState.COMPLETED, TaskState.PENDING),
        (TaskState.REVISION_REQUIRED, TaskState.COMPLETED),
    ],
)
def test_invalid_transitions_rejected(start, new):
    t = make_task()
    t.state = start
    with pytest.raises(OrchestratorError) as e:
        transition(t, new)
    assert e.value.kind == "invalid_transition"
    assert t.state == start


def test_any_active_state_can_fail():
    for s in (
        TaskState.PENDING,
        TaskState.RUNNING,
        TaskState.REVIEWING,
        TaskState.REVISION_REQUIRED,
        TaskState.RETRYING,
    ):
        assert can_transition(s, TaskState.FAILED)
