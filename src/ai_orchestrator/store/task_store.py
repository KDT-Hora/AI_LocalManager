"""File-based storage for tasks, versions, and validations (contracts/task-files.md)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from ..errors import CORRUPTED_DATA, NOT_FOUND, OrchestratorError
from ..models.artifact import ArtifactKind, ArtifactVersion
from ..models.task import StateEvent, Task, TaskError, TaskState, now
from ..models.validation import ValidationResult
from ..workflow.state_machine import transition
from . import files

_TASK_RE = re.compile(r"^TASK-(\d{3,})$")


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_") or "misc"


class TaskStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = Path(workspace)
        self.tasks_dir = self.workspace / "tasks"
        self.artifacts_dir = self.workspace / "artifacts"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    # ---- tasks -------------------------------------------------------
    def task_dir(self, task_id: str) -> Path:
        return self.tasks_dir / task_id

    def lock(self, task_id: str):
        return files.dir_lock(self.task_dir(task_id))

    def list_ids(self) -> list[str]:
        ids = [p.name for p in self.tasks_dir.iterdir() if p.is_dir() and _TASK_RE.match(p.name)]
        return sorted(ids)

    def create_task(
        self,
        request: str,
        capabilities: list[str],
        max_revisions: int,
        prompt: str,
        input_files: list[str] | None = None,
    ) -> Task:
        with files.dir_lock(self.tasks_dir, ".alloc.lock"):
            nums = [int(_TASK_RE.match(i).group(1)) for i in self.list_ids()]
            task_id = f"TASK-{max(nums, default=0) + 1:03d}"
            task = Task(
                task_id=task_id,
                request=request,
                required_capabilities=capabilities,
                category=_slug(capabilities[0]) if capabilities else "misc",
                max_revisions=max_revisions,
                input_files=input_files or [],
            )
            task.state_history.append(StateEvent(state=TaskState.PENDING, reason="created"))
            task_dir = self.task_dir(task_id)
            task_dir.mkdir(parents=True)
            files.write_new_text(task_dir / "prompt.txt", prompt)
            self.save(task)
        return task

    def save(self, task: Task) -> None:
        task.updated_at = now()
        files.write_json(self.task_dir(task.task_id) / "task.json", task.model_dump(mode="json"))

    def load(self, task_id: str) -> Task:
        path = self.task_dir(task_id) / "task.json"
        if not path.exists():
            raise OrchestratorError(NOT_FOUND, f"task not found: {task_id}")
        try:
            return Task.model_validate_json(files.read_text(path))
        except (ValidationError, json.JSONDecodeError) as e:
            raise OrchestratorError(
                CORRUPTED_DATA, f"{task_id}/task.json is corrupted (left untouched): {e}"
            ) from e

    def read_prompt(self, task_id: str, name: str = "prompt.txt") -> str:
        return files.read_text(self.task_dir(task_id) / name)

    # ---- versions ----------------------------------------------------
    def _existing_versions(self, task_id: str) -> list[int]:
        out = []
        for p in self.task_dir(task_id).glob("result_v*.meta.json"):
            m = re.match(r"result_v(\d+)\.meta\.json$", p.name)
            if m:
                out.append(int(m.group(1)))
        return sorted(out)

    def save_version(
        self,
        task: Task,
        content: str,
        ext: str,
        kind: ArtifactKind,
        model_id: str | None,
        prompt_text: str = "",
        parent_version: int | None = None,
    ) -> ArtifactVersion:
        task_dir = self.task_dir(task.task_id)
        with self.lock(task.task_id):
            version = max(self._existing_versions(task.task_id), default=0) + 1
            prompt_file = ""
            if prompt_text:
                base = task_dir / "prompt.txt"
                if version == 1 and base.exists() and files.read_text(base) == prompt_text:
                    prompt_file = "prompt.txt"
                else:
                    prompt_file = f"prompt_v{version:03d}.txt"
                    files.write_new_text(task_dir / prompt_file, prompt_text)
            content_file = f"result_v{version:03d}.{ext}"
            files.write_new_text(task_dir / content_file, content)
            files.write_new_text(task_dir / ".history" / content_file, content)  # pristine copy
            av = ArtifactVersion(
                version=version,
                model_id=model_id,
                kind=kind,
                prompt_file=prompt_file,
                content_file=content_file,
                content_hash=files.sha256_text(content),
                parent_version=parent_version,
            )
            files.write_new_text(
                task_dir / f"result_v{version:03d}.meta.json",
                av.model_dump_json(indent=2),
            )
            task.versions.append(version)
        return av

    def load_meta(self, task_id: str, version: int) -> ArtifactVersion:
        path = self.task_dir(task_id) / f"result_v{version:03d}.meta.json"
        if not path.exists():
            raise OrchestratorError(NOT_FOUND, f"{task_id} version {version} not found")
        return ArtifactVersion.model_validate_json(files.read_text(path))

    def read_version(self, task_id: str, version: int) -> tuple[ArtifactVersion, str]:
        meta = self.load_meta(task_id, version)
        return meta, files.read_text(self.task_dir(task_id) / meta.content_file)

    def latest_version(self, task: Task) -> int | None:
        return max(task.versions) if task.versions else None

    # ---- validations -------------------------------------------------
    def save_validation(self, task_id: str, result: ValidationResult) -> Path:
        task_dir = self.task_dir(task_id)
        with self.lock(task_id):
            n = result.version
            path = task_dir / f"validation_v{n:03d}.json"
            k = 1
            while path.exists():
                k += 1
                path = task_dir / f"validation_v{n:03d}.r{k}.json"
            files.write_new_text(path, result.model_dump_json(indent=2))
        return path

    def load_validations(self, task_id: str, version: int) -> list[ValidationResult]:
        task_dir = self.task_dir(task_id)
        paths = sorted(task_dir.glob(f"validation_v{version:03d}*.json"))

        # sort: base file first, then r2, r3 ... (numeric on suffix)
        def key(p: Path) -> int:
            m = re.search(r"\.r(\d+)\.json$", p.name)
            return int(m.group(1)) if m else 1

        return [
            ValidationResult.model_validate_json(files.read_text(p)) for p in sorted(paths, key=key)
        ]

    def latest_validation(self, task_id: str, version: int) -> ValidationResult | None:
        vals = self.load_validations(task_id, version)
        return vals[-1] if vals else None

    # ---- user edits --------------------------------------------------
    def sync_user_edits(self, task: Task) -> list[ArtifactVersion]:
        """Import hand-edited result files as `user_edit` versions; restore AI originals."""
        task_dir = self.task_dir(task.task_id)
        created: list[ArtifactVersion] = []
        for v in list(task.versions):
            meta = self.load_meta(task.task_id, v)
            path = task_dir / meta.content_file
            if not path.exists():
                continue
            current = files.read_text(path)
            if files.sha256_text(current) == meta.content_hash:
                continue
            original_path = task_dir / ".history" / meta.content_file
            ext = meta.content_file.rsplit(".", 1)[-1]
            av = self.save_version(
                task, current, ext, ArtifactKind.USER_EDIT, None, "", parent_version=v
            )
            if original_path.exists():
                files.atomic_write_text(path, files.read_text(original_path))
            created.append(av)
        if created:
            self.save(task)
        return created

    # ---- final artifacts ----------------------------------------------
    def publish_artifact(self, task: Task, version: int) -> Path:
        meta, content = self.read_version(task.task_id, version)
        ext = meta.content_file.rsplit(".", 1)[-1]
        out = self.artifacts_dir / task.category / f"{task.category}_{task.task_id}.{ext}"
        files.atomic_write_text(out, content)
        return out

    def fail(self, task: Task, kind: str, message: str, retryable: bool) -> None:
        task.error = TaskError(kind=kind, message=message, retryable=retryable)
        if task.state != TaskState.FAILED:
            transition(task, TaskState.FAILED, f"{kind}: {message}")
        self.save(task)
