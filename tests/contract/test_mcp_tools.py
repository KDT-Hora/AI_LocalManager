"""Contract tests: the MCP tools' input/output shapes (contracts/mcp-tools.md)."""

import pytest

import ai_orchestrator.mcp_server as srv
from ai_orchestrator.workflow.service import Orchestrator

TOOLS = {
    "create_task",
    "select_model",
    "run_agent",
    "get_artifact",
    "validate_artifact",
    "request_revision",
    "complete_task",
}
ISSUE = [{"aspect": "形式", "description": "x", "severity": "low"}]


@pytest.fixture
def tools(settings, monkeypatch):
    monkeypatch.setattr(srv, "_orch", Orchestrator(settings))
    return srv


async def test_seven_tools_registered(tools):
    names = {t.name for t in await tools.mcp.list_tools()}
    assert TOOLS <= names


async def test_success_and_error_envelopes(tools):
    r = await tools.create_task("x", ["story"])
    assert r == {"ok": True, "task_id": "TASK-001", "state": "PENDING"}

    r = await tools.select_model("TASK-001")
    assert r["ok"] and {"model_id", "reason", "candidates"} <= r.keys()

    r = await tools.run_agent("TASK-001")
    assert (
        r["ok"] and {"version", "artifact_path", "state"} <= r.keys() and r["state"] == "REVIEWING"
    )

    r = await tools.get_artifact("TASK-001")
    assert r["ok"] and {"version", "model_id", "kind", "content", "validation"} <= r.keys()

    r = await tools.validate_artifact("TASK-001", 1, "fail", issues=ISSUE)
    assert r == {"ok": True, "state": "REVISION_REQUIRED"}

    r = await tools.request_revision("TASK-001", 1, "minor", "直して")
    assert r["ok"] and r["version"] == 2

    await tools.validate_artifact("TASK-001", 2, "pass")
    r = await tools.complete_task("TASK-001", 2)
    assert r["ok"] and r["state"] == "COMPLETED" and r["final_version"] == 2
    assert "artifact_path" in r


async def test_errors_use_documented_shape(tools):
    r = await tools.get_artifact("TASK-999")
    assert r["ok"] is False and r["error"]["kind"] == "not_found"
    assert set(r["error"]) == {"kind", "message", "retryable"}

    await tools.create_task("x", ["nonexistent"])
    r = await tools.select_model("TASK-001")
    assert r["error"]["kind"] == "no_capable_model"

    await tools.create_task("y", ["story"])
    r = await tools.complete_task("TASK-002", 1)
    assert r["ok"] is False and r["error"]["kind"] in {"not_found", "invalid_transition"}


async def test_validate_fail_requires_issues(tools):
    await tools.create_task("x", ["story"])
    await tools.run_agent("TASK-001")
    r = await tools.validate_artifact("TASK-001", 1, "fail")
    assert r["ok"] is False


async def test_tool_input_schemas(tools):
    by_name = {t.name: t for t in await tools.mcp.list_tools()}
    assert by_name["create_task"].inputSchema["required"] == ["request", "required_capabilities"]
    assert set(by_name["request_revision"].inputSchema["required"]) == {
        "task_id",
        "base_version",
        "method",
        "instructions",
    }
