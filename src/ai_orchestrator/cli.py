"""Helper CLI: check-models, list, show, retry."""

from __future__ import annotations

import argparse
import sys

from .errors import OrchestratorError
from .models.task import Task, TaskState
from .registry.loader import RegistryError, load_config
from .settings import Settings
from .workflow.service import Orchestrator


def _mark(task: Task) -> str:
    return "!!" if task.state == TaskState.FAILED else "  "


def format_list(tasks: list[Task]) -> str:
    if not tasks:
        return "(no tasks)"
    lines = []
    for t in tasks:
        line = (
            f"{_mark(t)} {t.task_id}  {t.state.value:<17} model={t.selected_model_id or '-':<14} "
            f"rev={t.revision_count}/{t.max_revisions}  {t.request[:40]}"
        )
        if t.state == TaskState.FAILED and t.error:
            line += f"\n     ERROR {t.error.kind}: {t.error.message}"
            if t.error.retryable:
                line += "  (retryable: ai-orchestrator-cli retry " + t.task_id + ")"
        lines.append(line)
    return "\n".join(lines)


def format_show(orch: Orchestrator, task: Task) -> str:
    out = [
        f"{task.task_id}  state={task.state.value}  category={task.category}",
        f"request: {task.request}",
        f"capabilities: {', '.join(task.required_capabilities)}",
        f"model: {task.selected_model_id} ({task.selection_reason})",
        f"revisions: {task.revision_count}/{task.max_revisions}"
        f"  final_version: {task.final_version}",
    ]
    if task.error:
        out.append(
            f"ERROR {task.error.kind}: {task.error.message} (retryable={task.error.retryable})"
        )
    out.append("history:")
    out += [
        f"  {e.at:%Y-%m-%d %H:%M:%S}  {e.state.value:<17} {e.reason}" for e in task.state_history
    ]
    out.append("versions:")
    for v in task.versions:
        meta = orch.store.load_meta(task.task_id, v)
        vals = orch.store.load_validations(task.task_id, v)
        verdict = vals[-1].verdict if vals else "not validated"
        out.append(
            f"  v{v:03d}  {meta.kind.value:<15} model={meta.model_id or 'user'}  -> {verdict}"
        )
        if vals and vals[-1].issues:
            out += [
                f"        - [{i.severity}] {i.aspect}: {i.description}" for i in vals[-1].issues
            ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-orchestrator-cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check-models", help="validate config/models.yaml")
    sub.add_parser("list", help="list tasks")
    p_show = sub.add_parser("show", help="show a task")
    p_show.add_argument("task_id")
    p_retry = sub.add_parser("retry", help="reset a retryable FAILED task to PENDING")
    p_retry.add_argument("task_id")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    try:
        if args.cmd == "check-models":
            cfg = load_config(settings.models_path)
            print(f"OK: {len(cfg.models)} model(s) in {settings.models_path}")
            for m in cfg.models:
                flag = "" if m.enabled else " (disabled)"
                print(f"  {m.id}: {', '.join(m.capabilities)} priority={m.priority}{flag}")
            return 0
        orch = Orchestrator(settings)
        if args.cmd == "list":
            print(format_list(orch.list_tasks()))
        elif args.cmd == "show":
            print(format_show(orch, orch._load(args.task_id)))
        elif args.cmd == "retry":
            task = orch.retry(args.task_id)
            print(f"{task.task_id} -> {task.state.value}")
        return 0
    except (RegistryError, OrchestratorError) as e:
        print(f"ERROR: {getattr(e, 'message', e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
