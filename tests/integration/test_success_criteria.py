"""SC-004: every version is traceable. SC-007: no task is left hanging in RUNNING after failures."""

import json

import pytest

from ai_orchestrator.errors import OrchestratorError
from ai_orchestrator.models.task import TaskState

ISSUE = [{"aspect": "x", "description": "y"}]


async def test_sc004_every_version_traceable(orch, settings):
    orch.create_task("x", ["story"])
    await orch.run_agent("TASK-001")
    orch.validate_artifact("TASK-001", 1, "fail", issues=ISSUE)
    await orch.request_revision("TASK-001", 1, "switch_model", "別モデルで")
    orch.validate_artifact("TASK-001", 2, "pass", ["要求充足"])

    d = settings.workspace / "tasks" / "TASK-001"
    for v in (1, 2):
        meta = json.loads((d / f"result_v{v:03d}.meta.json").read_text(encoding="utf-8"))
        assert meta["model_id"] and meta["created_at"] and meta["kind"]
        assert (d / meta["prompt_file"]).read_text(encoding="utf-8")  # prompt is recorded
        assert (d / meta["content_file"]).exists()
    assert (d / "validation_v001.json").exists() and (d / "validation_v002.json").exists()


@pytest.mark.parametrize("failure", ["unknown_model", "malformed", "empty", "timeout"])
async def test_sc007_failures_never_leave_running(orch, fake, failure):
    if failure == "unknown_model":
        fake.unknown_models.add("writer-a")
    elif failure == "malformed":
        fake.malformed = True
    elif failure == "empty":
        fake.reply = lambda m, p: ""
    else:
        orch.settings.timeout = 0.2
        fake.delay = 0.6
    orch.create_task("x", ["story"])
    with pytest.raises(OrchestratorError) as e:
        await orch.run_agent("TASK-001")
    task = orch.store.load("TASK-001")
    assert task.state == TaskState.FAILED
    assert task.error and task.error.kind == e.value.kind and task.error.message
    assert not [t for t in orch.list_tasks() if t.state == TaskState.RUNNING]
