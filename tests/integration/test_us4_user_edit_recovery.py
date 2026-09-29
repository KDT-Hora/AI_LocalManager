import json

from ai_orchestrator.models.task import TaskState
from ai_orchestrator.workflow.recovery import recover_stale_tasks


async def test_user_edit_imported_via_get_artifact(orch, settings):
    orch.create_task("x", ["story"])
    await orch.run_agent("TASK-001")
    f = settings.workspace / "tasks" / "TASK-001" / "result_v001.txt"
    f.write_text("ユーザーが直した文章", encoding="utf-8")

    art = orch.get_artifact("TASK-001")  # latest = user edit
    assert art["version"] == 2 and art["kind"] == "user_edit"
    assert art["content"] == "ユーザーが直した文章" and art["model_id"] is None
    assert orch.get_artifact("TASK-001", 1)["content"] == "[writer-a] OK"  # AI version kept


async def test_user_edit_can_be_validated_and_completed(orch, settings):
    orch.create_task("x", ["story"])
    await orch.run_agent("TASK-001")
    (settings.workspace / "tasks" / "TASK-001" / "result_v001.txt").write_text(
        "edited", encoding="utf-8"
    )
    v = orch.get_artifact("TASK-001")["version"]
    orch.validate_artifact("TASK-001", v, "pass")
    orch.complete_task("TASK-001", v)
    final = settings.workspace / "artifacts" / "story" / "story_TASK-001.txt"
    assert final.read_text(encoding="utf-8") == "edited"


async def test_stale_running_task_recovered(orch, settings):
    orch.create_task("x", ["story"])
    await orch.run_agent("TASK-001")
    orch.create_task("y", ["story"])
    # simulate a crash: TASK-002 stuck in RUNNING
    t2 = orch.store.load("TASK-002")
    t2.state = TaskState.RUNNING
    orch.store.save(t2)

    assert recover_stale_tasks(orch.store) == ["TASK-002"]
    t2 = orch.store.load("TASK-002")
    assert t2.state == "FAILED" and t2.error.kind == "interrupted" and t2.error.retryable
    t1 = orch.store.load("TASK-001")
    assert t1.state == "REVIEWING" and t1.versions == [1]  # untouched
    d = settings.workspace / "tasks" / "TASK-001"
    assert json.loads((d / "result_v001.meta.json").read_text(encoding="utf-8"))["version"] == 1


async def test_retry_moves_failed_retryable_back_to_pending(orch):
    orch.create_task("x", ["story"])
    t = orch.store.load("TASK-001")
    t.state = TaskState.RUNNING
    orch.store.save(t)
    orch.recover()
    assert orch.retry("TASK-001").state == "PENDING"
    await orch.run_agent("TASK-001")
    assert orch.store.load("TASK-001").state == "REVIEWING"
