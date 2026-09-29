import pytest

from ai_orchestrator.errors import OrchestratorError


async def test_no_capable_model_on_run(orch):
    orch.create_task("x", ["nonexistent"])
    with pytest.raises(OrchestratorError) as e:
        await orch.run_agent("TASK-001")
    assert e.value.kind == "no_capable_model"
    task = orch.store.load("TASK-001")
    assert task.state == "FAILED" and task.error.kind == "no_capable_model"


def test_no_capable_model_on_select(orch):
    orch.create_task("x", ["nonexistent"])
    with pytest.raises(OrchestratorError) as e:
        orch.select_model("TASK-001")
    assert e.value.kind == "no_capable_model"
    assert orch.store.load("TASK-001").state == "FAILED"
