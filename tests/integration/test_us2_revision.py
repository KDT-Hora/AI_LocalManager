import pytest

from ai_orchestrator.errors import OrchestratorError

FAIL_ISSUES = [{"aspect": "必須項目", "description": "年齢がない", "severity": "high"}]


async def generated(orch):
    orch.create_task("設定を作成", ["story"])
    await orch.run_agent("TASK-001")


async def test_pass_then_complete(orch, settings):
    await generated(orch)
    assert orch.validate_artifact("TASK-001", 1, "pass", ["要求充足"])["state"] == "REVIEWING"
    done = orch.complete_task("TASK-001", 1)
    assert done["state"] == "COMPLETED" and done["final_version"] == 1
    assert (settings.workspace / "artifacts" / "story" / "story_TASK-001.txt").exists()


async def test_minor_revision_keeps_old_version(orch, fake):
    await generated(orch)
    fake.reply = lambda m, p: "revised text"
    r = orch.validate_artifact("TASK-001", 1, "fail", ["必須項目"], FAIL_ISSUES, "minor")
    assert r["state"] == "REVISION_REQUIRED"
    rev = await orch.request_revision("TASK-001", 1, "minor", "年齢を追加")
    assert rev["version"] == 2 and rev["state"] == "REVIEWING"
    # the revision prompt carries the previous artifact and the instructions
    prompt = fake.calls[-1][1]
    assert "[writer-a] OK" in prompt and "年齢を追加" in prompt
    assert orch.get_artifact("TASK-001", 1)["content"] == "[writer-a] OK"  # v001 preserved
    a2 = orch.get_artifact("TASK-001", 2)
    assert a2["content"] == "revised text" and a2["kind"] == "minor_revision"
    task = orch.store.load("TASK-001")
    assert task.revision_count == 1
    orch.validate_artifact("TASK-001", 2, "pass")
    assert orch.complete_task("TASK-001", 2)["final_version"] == 2


async def test_regenerate_uses_same_model(orch, fake):
    await generated(orch)
    orch.validate_artifact("TASK-001", 1, "fail", issues=FAIL_ISSUES)
    await orch.request_revision("TASK-001", 1, "regenerate", "作り直し")
    assert [c[0] for c in fake.calls] == ["writer-a", "writer-a"]
    assert orch.get_artifact("TASK-001")["kind"] == "regenerate"


async def test_switch_model_records_other_model(orch, fake):
    await generated(orch)
    orch.validate_artifact(
        "TASK-001", 1, "fail", issues=FAIL_ISSUES, recommended_action="switch_model"
    )
    await orch.request_revision("TASK-001", 1, "switch_model", "品質が低い")
    art = orch.get_artifact("TASK-001", 2)
    assert art["model_id"] == "writer-b" and art["kind"] == "model_switch"
    assert orch.store.load("TASK-001").excluded_model_ids == ["writer-a"]


async def test_switch_model_without_alternative_does_not_burn_revision(orch):
    orch.create_task("x", ["code"])  # only one 'code' model
    await orch.run_agent("TASK-001")
    orch.validate_artifact("TASK-001", 1, "fail", issues=FAIL_ISSUES)
    with pytest.raises(OrchestratorError) as e:
        await orch.request_revision("TASK-001", 1, "switch_model", "x")
    assert e.value.kind == "no_capable_model"
    task = orch.store.load("TASK-001")
    assert task.state == "REVISION_REQUIRED" and task.revision_count == 0


async def test_revision_limit_reached(orch):
    orch.create_task("x", ["story"], max_revisions=3)
    await orch.run_agent("TASK-001")
    for i in range(3):
        orch.validate_artifact("TASK-001", i + 1, "fail", issues=FAIL_ISSUES)
        await orch.request_revision("TASK-001", i + 1, "minor", "again")
    orch.validate_artifact("TASK-001", 4, "fail", issues=FAIL_ISSUES)
    with pytest.raises(OrchestratorError) as e:
        await orch.request_revision("TASK-001", 4, "minor", "again")
    assert e.value.kind == "revision_limit_reached"
    task = orch.store.load("TASK-001")
    assert task.state == "FAILED" and task.revision_count == 3
    assert task.error.kind == "revision_limit_reached"


async def test_complete_without_passing_validation_rejected(orch):
    await generated(orch)
    with pytest.raises(OrchestratorError) as e:  # never validated
        orch.complete_task("TASK-001", 1)
    assert e.value.kind == "invalid_transition"
    orch.validate_artifact("TASK-001", 1, "fail", issues=FAIL_ISSUES)
    with pytest.raises(OrchestratorError) as e:  # failed validation
        orch.complete_task("TASK-001", 1)
    assert e.value.kind == "invalid_transition"
    assert orch.store.load("TASK-001").state == "REVISION_REQUIRED"


async def test_fail_verdict_requires_issues(orch):
    await generated(orch)
    with pytest.raises(OrchestratorError):
        orch.validate_artifact("TASK-001", 1, "fail")


async def test_run_agent_only_from_pending(orch):
    await generated(orch)
    with pytest.raises(OrchestratorError) as e:
        await orch.run_agent("TASK-001")
    assert e.value.kind == "invalid_transition"
