import pytest

from ai_orchestrator.errors import OrchestratorError
from ai_orchestrator.settings import Settings
from ai_orchestrator.workflow.service import Orchestrator


async def run_expect(orch, kind):
    orch.create_task("x", ["story"])
    with pytest.raises(OrchestratorError) as e:
        await orch.run_agent("TASK-001")
    assert e.value.kind == kind
    task = orch.store.load("TASK-001")
    assert task.state == "FAILED", "task must never stay RUNNING"
    assert task.error.kind == kind
    return task


async def test_model_load_failed(orch, fake):
    fake.unknown_models.add("writer-a")
    task = await run_expect(orch, "model_load_failed")
    assert not task.versions


async def test_backend_unreachable(settings, models_path, tmp_path):
    import socket

    with socket.socket() as sock:  # grab a free port, then close it: nothing listens there
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    s = Settings(
        workspace=tmp_path / "w2",
        models_path=models_path,
        lmstudio_url=f"http://127.0.0.1:{port}",
        timeout=2,
    )
    task = await run_expect(Orchestrator(s), "backend_unreachable")
    assert task.error.retryable


async def test_timeout(orch, fake):
    orch.settings.timeout = 0.2
    fake.delay = 1.0
    task = await run_expect(orch, "timeout")
    assert task.error.retryable


async def test_invalid_output_empty(orch, fake):
    fake.reply = lambda m, p: "   "
    await run_expect(orch, "invalid_output")


async def test_invalid_output_reasoning_only(orch, fake):
    fake.reasoning_only = True
    task = await run_expect(orch, "invalid_output")
    assert "max_tokens" in task.error.message


async def test_invalid_output_malformed_response(orch, fake):
    fake.malformed = True
    await run_expect(orch, "invalid_output")


async def test_image_model_unsupported(orch, models_path):
    models_path.write_text(
        "models:\n  - id: img\n    lmstudio_id: img\n    capabilities: [picture]\n"
        "    priority: 1\n    max_context: 8000\n    model_type: image_gen\n    output_format: image\n",
        encoding="utf-8",
    )
    orch.create_task("x", ["picture"])
    with pytest.raises(OrchestratorError) as e:
        await orch.run_agent("TASK-001")
    assert e.value.kind == "unsupported_backend"
    assert orch.store.load("TASK-001").state == "FAILED"
