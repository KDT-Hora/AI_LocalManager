"""MCP server (stdio) exposing the seven orchestrator tools to Claude."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from .errors import OrchestratorError
from .logging_setup import get_logger, setup_logging
from .settings import Settings
from .workflow.service import Orchestrator

mcp = FastMCP("ai-orchestrator")
_orch: Orchestrator | None = None


def orchestrator() -> Orchestrator:
    global _orch
    if _orch is None:
        _orch = Orchestrator(Settings.from_env())
    return _orch


def safe(fn: Callable) -> Callable:
    """Turn results into {ok: true, ...} and errors into {ok: false, error: {...}}."""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            return {"ok": True, **result}
        except OrchestratorError as e:
            return {"ok": False, "error": e.to_dict()}
        except ValidationError as e:
            return {
                "ok": False,
                "error": {"kind": "invalid_output", "message": str(e), "retryable": False},
            }
        except Exception as e:  # never crash the stdio server
            get_logger().exception("unexpected error")
            return {
                "ok": False,
                "error": {"kind": "internal", "message": str(e), "retryable": False},
            }

    return wrapper


@mcp.tool()
@safe
def create_task(
    request: str,
    required_capabilities: list[str],
    max_revisions: int | None = None,
    input_files: list[str] | None = None,
) -> dict:
    """新しいAIタスクを作成する。required_capabilities は例: story, character_design, code。"""
    return orchestrator().create_task(request, required_capabilities, max_revisions, input_files)


@mcp.tool()
@safe
def select_model(task_id: str, exclude_model_ids: list[str] | None = None) -> dict:
    """タスクに適したモデルを選び、理由と候補一覧を返す。"""
    return orchestrator().select_model(task_id, exclude_model_ids)


@mcp.tool()
@safe
async def run_agent(task_id: str, model_id: str | None = None, prompt: str | None = None) -> dict:
    """PENDING のタスクをローカルAIで実行し、成果物 v001 を保存する。"""
    return await orchestrator().run_agent(task_id, model_id, prompt)


@mcp.tool()
@safe
def get_artifact(task_id: str, version: int | None = None) -> dict:
    """成果物を取得する（version 省略で最新）。"""
    return orchestrator().get_artifact(task_id, version)


@mcp.tool()
@safe
def validate_artifact(
    task_id: str,
    version: int,
    verdict: str,
    aspects_checked: list[str] | None = None,
    issues: list[dict] | None = None,
    recommended_action: str | None = None,
) -> dict:
    """Claude の検証結果を登録する。verdict は pass/fail。fail のとき issues 必須
    （各要素: aspect, description, severity=low|medium|high）。"""
    return orchestrator().validate_artifact(
        task_id, version, verdict, aspects_checked, issues, recommended_action
    )


@mcp.tool()
@safe
async def request_revision(
    task_id: str,
    base_version: int,
    method: str,
    instructions: str,
    target_model_id: str | None = None,
) -> dict:
    """修正を依頼する。method: minor（軽微修正）/ regenerate（再生成）/ switch_model（別AI）。"""
    return await orchestrator().request_revision(
        task_id, base_version, method, instructions, target_model_id
    )


@mcp.tool()
@safe
def complete_task(task_id: str, version: int) -> dict:
    """合格済みの版でタスクを完了し、artifacts/ に配置する。"""
    return orchestrator().complete_task(task_id, version)


def main() -> None:
    settings = Settings.from_env()
    setup_logging(settings.workspace)
    orch = orchestrator()
    recovered = orch.recover()
    if recovered:
        get_logger().warning("recovered interrupted tasks: %s", recovered)
    mcp.run()


if __name__ == "__main__":
    main()
