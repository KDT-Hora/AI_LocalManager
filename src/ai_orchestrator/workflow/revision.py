"""Revision prompts and limit check."""

from __future__ import annotations

from ..errors import REVISION_LIMIT_REACHED, OrchestratorError
from ..models.artifact import ArtifactKind
from ..models.task import Task
from ..store.task_store import TaskStore

KIND = {
    "minor": ArtifactKind.MINOR_REVISION,
    "regenerate": ArtifactKind.REGENERATE,
    "switch_model": ArtifactKind.MODEL_SWITCH,
}


def check_limit(store: TaskStore, task: Task) -> None:
    if task.revision_count >= task.max_revisions:
        msg = f"{task.task_id}: revision limit ({task.max_revisions}) reached"
        store.fail(task, REVISION_LIMIT_REACHED, msg, False)
        raise OrchestratorError(REVISION_LIMIT_REACHED, msg)


def build_prompt(method: str, original_prompt: str, previous: str, instructions: str) -> str:
    if method == "minor":
        return (
            "以下の成果物を、修正指示に従って修正してください。"
            "修正後の成果物の全文のみを出力し、説明は書かないでください。\n\n"
            f"## 元の依頼\n{original_prompt}\n\n"
            f"## 現在の成果物\n{previous}\n\n"
            f"## 修正指示\n{instructions}\n"
        )
    if method == "switch_model":
        return (
            f"{original_prompt}\n\n"
            "## 参考: 前回の成果物（品質上の問題があり作り直しています）\n"
            f"{previous}\n\n"
            f"## 前回の問題点と要望\n{instructions}\n\n"
            "問題点を解消した成果物の全文のみを出力してください。\n"
        )
    return (  # regenerate: from scratch, but keep the reasons in view
        f"{original_prompt}\n\n"
        f"## 前回の問題点（繰り返さないこと）\n{instructions}\n\n"
        "成果物の全文のみを出力してください。\n"
    )
