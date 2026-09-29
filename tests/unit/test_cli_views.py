import pytest

from ai_orchestrator.cli import format_list, format_show, main


async def test_list_and_show(orch):
    orch.create_task("設定を作成", ["story"])
    await orch.run_agent("TASK-001")
    orch.validate_artifact(
        "TASK-001",
        1,
        "fail",
        issues=[{"aspect": "形式", "description": "見出しなし", "severity": "low"}],
    )
    out = format_list(orch.list_tasks())
    assert (
        "TASK-001" in out and "REVISION_REQUIRED" in out and "writer-a" in out and "rev=0/3" in out
    )

    show = format_show(orch, orch._load("TASK-001"))
    assert "v001" in show and "fail" in show and "見出しなし" in show and "writer-a" in show


async def test_failed_task_highlighted_with_error(orch):
    orch.create_task("x", ["nonexistent"])
    with pytest.raises(Exception):
        await orch.run_agent("TASK-001")
    out = format_list(orch.list_tasks())
    assert "!!" in out and "ERROR no_capable_model" in out


def test_check_models_cli(monkeypatch, models_path, capsys):
    monkeypatch.setenv("AIO_MODELS", str(models_path))
    assert main(["check-models"]) == 0
    assert "3 model(s)" in capsys.readouterr().out


def test_check_models_cli_reports_errors(monkeypatch, tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("models:\n  - id: a\n", encoding="utf-8")
    monkeypatch.setenv("AIO_MODELS", str(bad))
    assert main(["check-models"]) == 1
    assert "lmstudio_id" in capsys.readouterr().err
