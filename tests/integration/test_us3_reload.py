import os
import time

from tests.conftest import MODELS_YAML


def rewrite(path, text):
    path.write_text(text, encoding="utf-8")
    future = time.time() + 5  # guarantee a distinct mtime on coarse filesystems
    os.utime(path, (future, future))


async def test_priority_change_applies_to_next_task(orch, fake, models_path):
    orch.create_task("a", ["story"])
    assert orch.select_model("TASK-001")["model_id"] == "writer-a"
    rewrite(models_path, MODELS_YAML.replace("priority: 80", "priority: 10"))
    orch.create_task("b", ["story"])
    assert orch.select_model("TASK-002")["model_id"] == "writer-b"


async def test_disable_model(orch, models_path):
    rewrite(models_path, MODELS_YAML.replace("priority: 80", "priority: 80\n    enabled: false"))
    orch.create_task("a", ["story"])
    assert orch.select_model("TASK-001")["model_id"] == "writer-b"


async def test_new_model_becomes_selectable(orch, models_path):
    extra = (
        "  - id: poet\n    lmstudio_id: poet\n    capabilities: [poetry]\n"
        "    priority: 5\n    max_context: 8000\n"
    )
    orch.create_task("a", ["poetry"])
    rewrite(models_path, MODELS_YAML + extra)
    assert orch.select_model("TASK-001")["model_id"] == "poet"


async def test_in_flight_task_keeps_its_model(orch, fake, models_path):
    orch.create_task("a", ["story"])
    await orch.run_agent("TASK-001")
    orch.validate_artifact("TASK-001", 1, "fail", issues=[{"aspect": "x", "description": "y"}])
    # writer-a is disabled mid-flight: a same-model revision must still use writer-a
    rewrite(models_path, MODELS_YAML.replace("priority: 80", "priority: 80\n    enabled: false"))
    await orch.request_revision("TASK-001", 1, "minor", "fix")
    assert [c[0] for c in fake.calls] == ["writer-a", "writer-a"]
    # ...while a new task no longer selects it
    orch.create_task("b", ["story"])
    assert orch.select_model("TASK-002")["model_id"] == "writer-b"
