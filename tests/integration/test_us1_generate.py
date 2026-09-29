import json


async def test_request_select_run_get(orch, fake, settings):
    t = orch.create_task("キャラクターAの設定を作成", ["character_design", "story"])
    assert t == {"task_id": "TASK-001", "state": "PENDING"}

    sel = orch.select_model("TASK-001")
    assert sel["model_id"] == "writer-a"  # highest priority with both capabilities
    assert {c["model_id"] for c in sel["candidates"]} == {"writer-a", "writer-b", "coder"}

    run = await orch.run_agent("TASK-001")
    assert run["version"] == 1 and run["state"] == "REVIEWING"

    art = orch.get_artifact("TASK-001")
    assert art["content"] == "[writer-a] OK" and art["model_id"] == "writer-a"
    assert art["kind"] == "initial"

    d = settings.workspace / "tasks" / "TASK-001"
    assert (d / "result_v001.txt").exists() and (d / "prompt.txt").exists()
    task = json.loads((d / "task.json").read_text(encoding="utf-8"))
    assert task["selected_model_id"] == "writer-a" and task["model_snapshot"]["id"] == "writer-a"
    states = [e["state"] for e in task["state_history"]]
    assert states == ["PENDING", "RUNNING", "REVIEWING"]
    assert fake.calls[0][0] == "writer-a"


async def test_specified_model_used(orch, fake):
    orch.create_task("x", ["story"])
    await orch.run_agent("TASK-001", model_id="writer-b")
    assert fake.calls[0][0] == "writer-b"


async def test_input_file_appended_to_prompt(orch, fake, tmp_path):
    f = tmp_path / "world.txt"
    f.write_text("世界設定です", encoding="utf-8")
    orch.create_task("設定を書いて", ["story"], input_files=[str(f)])
    await orch.run_agent("TASK-001")
    assert "世界設定です" in fake.calls[0][1]
