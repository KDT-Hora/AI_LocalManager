"""Orchestrator facade: the seven operations exposed to Claude (contracts/mcp-tools.md)."""

from __future__ import annotations

from pathlib import Path

from ..backends.base import Backend
from ..backends.lmstudio import LMStudioBackend
from ..errors import INVALID_OUTPUT, NO_CAPABLE_MODEL, NOT_FOUND, OrchestratorError
from ..logging_setup import get_logger
from ..models.artifact import ArtifactKind
from ..models.model_definition import ModelDefinition
from ..models.task import Task, TaskState
from ..models.validation import RevisionRequest
from ..registry.loader import ModelRegistry, RegistryError
from ..registry.selection import select_model
from ..settings import Settings
from ..store.task_store import TaskStore
from . import completion, revision
from .recovery import recover_stale_tasks
from .runner import Generator
from .state_machine import require_state, transition
from .validation import register_validation


class Orchestrator:
    def __init__(self, settings: Settings, backend: Backend | None = None) -> None:
        self.settings = settings
        self.store = TaskStore(settings.workspace)
        self.registry = ModelRegistry(settings.models_path)
        self.backend = backend or LMStudioBackend(settings)
        self._gen: Generator | None = None

    # ---- helpers -------------------------------------------------------
    def _config(self):
        try:
            return self.registry.config()
        except RegistryError as e:
            raise OrchestratorError(NO_CAPABLE_MODEL, f"models.yaml problem: {e}") from e

    @property
    def gen(self) -> Generator:
        cfg = self._config()
        if self._gen is None:
            self._gen = Generator(self.store, self.backend, cfg.vram_limit_gb)
        self._gen.vram_limit_gb = cfg.vram_limit_gb
        return self._gen

    def _load(self, task_id: str) -> Task:
        task = self.store.load(task_id)
        self.store.sync_user_edits(task)
        return task

    def recover(self) -> list[str]:
        return recover_stale_tasks(self.store)

    def _pick(self, task: Task, exclude: list[str] | None = None):
        prompt = self.store.read_prompt(task.task_id)
        return select_model(
            self._config(),
            task.required_capabilities,
            prompt,
            exclude=exclude,
            loaded_model_id=self.gen.current_id,
        )

    def _assign(self, task: Task, model: ModelDefinition, reason: str) -> None:
        task.selected_model_id = model.id
        task.selection_reason = reason
        task.model_snapshot = model.model_dump(mode="json")

    # ---- 1. create_task ------------------------------------------------
    def create_task(
        self,
        request: str,
        required_capabilities: list[str],
        max_revisions: int | None = None,
        input_files: list[str] | None = None,
    ) -> dict:
        if not required_capabilities:
            raise OrchestratorError(INVALID_OUTPUT, "required_capabilities must not be empty")
        prompt = request
        for f in input_files or []:
            p = Path(f)
            if not p.exists():
                raise OrchestratorError(NOT_FOUND, f"input file not found: {f}")
            prompt += f"\n\n## 入力ファイル: {p.name}\n{p.read_text(encoding='utf-8')}"
        task = self.store.create_task(
            request,
            required_capabilities,
            self.settings.max_revisions if max_revisions is None else max_revisions,
            prompt,
            input_files,
        )
        get_logger().info("%s: created (%s)", task.task_id, required_capabilities)
        return {"task_id": task.task_id, "state": task.state.value}

    # ---- 2. select_model -----------------------------------------------
    def select_model(self, task_id: str, exclude_model_ids: list[str] | None = None) -> dict:
        task = self._load(task_id)
        try:
            sel = self._pick(task, (exclude_model_ids or []) + task.excluded_model_ids)
        except OrchestratorError as e:
            if e.kind == NO_CAPABLE_MODEL and task.state == TaskState.PENDING:
                self.store.fail(task, e.kind, e.message, False)
            raise
        self._assign(task, sel.model, sel.reason)
        self.store.save(task)
        return {
            "model_id": sel.model.id,
            "reason": sel.reason,
            "candidates": [
                {
                    "model_id": c.model_id,
                    "priority": c.priority,
                    "rejected_reason": c.rejected_reason,
                }
                for c in sel.candidates
            ],
        }

    # ---- 3. run_agent --------------------------------------------------
    async def run_agent(
        self, task_id: str, model_id: str | None = None, prompt: str | None = None
    ) -> dict:
        task = self._load(task_id)
        require_state(task, TaskState.PENDING)
        try:
            if model_id:
                model = self.registry.get(model_id) if self._config() else None
                if model is None or not model.enabled:
                    raise OrchestratorError(NOT_FOUND, f"model '{model_id}' is not available")
                self._assign(task, model, "specified by caller")
            elif task.selected_model_id and self.registry.get(task.selected_model_id):
                model = self.registry.get(task.selected_model_id)
                if not model.enabled:
                    raise OrchestratorError(NO_CAPABLE_MODEL, f"'{model.id}' is disabled")
            else:
                sel = self._pick(task, task.excluded_model_ids)
                model = sel.model
                self._assign(task, model, sel.reason)
        except OrchestratorError as e:
            self.store.fail(task, e.kind, e.message, e.retryable)
            raise
        text = prompt if prompt is not None else self.store.read_prompt(task_id)
        transition(task, TaskState.RUNNING, f"run with {model.id}")
        self.store.save(task)
        av = await self.gen.generate(task, model, text, ArtifactKind.INITIAL)
        return self._version_result(task, av.version)

    def _version_result(self, task: Task, version: int) -> dict:
        meta = self.store.load_meta(task.task_id, version)
        return {
            "version": version,
            "artifact_path": str(self.store.task_dir(task.task_id) / meta.content_file),
            "state": task.state.value,
        }

    # ---- 4. get_artifact -----------------------------------------------
    def get_artifact(self, task_id: str, version: int | None = None) -> dict:
        task = self._load(task_id)
        v = version or self.store.latest_version(task)
        if v is None:
            raise OrchestratorError(NOT_FOUND, f"{task_id} has no artifact yet")
        meta, content = self.store.read_version(task_id, v)
        val = self.store.latest_validation(task_id, v)
        return {
            "version": v,
            "model_id": meta.model_id,
            "kind": meta.kind.value,
            "content": content,
            "validation": val.model_dump(mode="json") if val else None,
        }

    # ---- 5. validate_artifact ------------------------------------------
    def validate_artifact(
        self,
        task_id: str,
        version: int,
        verdict: str,
        aspects_checked: list[str] | None = None,
        issues: list[dict] | None = None,
        recommended_action: str | None = None,
    ) -> dict:
        task = self._load(task_id)
        register_validation(
            self.store,
            task,
            version,
            verdict,
            aspects_checked,
            issues,
            recommended_action,  # type: ignore[arg-type]
        )
        return {"state": task.state.value}

    # ---- 6. request_revision -------------------------------------------
    async def request_revision(
        self,
        task_id: str,
        base_version: int,
        method: str,
        instructions: str,
        target_model_id: str | None = None,
    ) -> dict:
        req = RevisionRequest(
            task_id=task_id,
            base_version=base_version,
            method=method,  # type: ignore[arg-type]
            instructions=instructions,
            target_model_id=target_model_id,
        )
        task = self._load(task_id)
        require_state(task, TaskState.REVISION_REQUIRED, TaskState.REVIEWING)
        if req.base_version not in task.versions:
            raise OrchestratorError(NOT_FOUND, f"{task_id} has no version {req.base_version}")
        revision.check_limit(self.store, task)

        # choose the model BEFORE spending a revision; failure here leaves the task as-is
        model = self._model_for_revision(task, req)

        transition(task, TaskState.RETRYING, f"{req.method} from v{req.base_version:03d}")
        task.revision_count += 1
        transition(task, TaskState.RUNNING, f"revision {task.revision_count} with {model.id}")
        self.store.save(task)

        _, previous = self.store.read_version(task_id, req.base_version)
        original = self.store.read_prompt(task_id)
        prompt = revision.build_prompt(req.method, original, previous, req.instructions)
        av = await self.gen.generate(
            task, model, prompt, revision.KIND[req.method], req.base_version
        )
        return self._version_result(task, av.version)

    def _model_for_revision(self, task: Task, req: RevisionRequest) -> ModelDefinition:
        if req.method != "switch_model":
            # in-flight tasks keep their starting definition (unaffected by models.yaml edits)
            if task.model_snapshot:
                return ModelDefinition.model_validate(task.model_snapshot)
            sel = self._pick(task, task.excluded_model_ids)
            self._assign(task, sel.model, sel.reason)
            return sel.model
        used = self.store.load_meta(task.task_id, req.base_version).model_id
        excluded = list({*task.excluded_model_ids, *([used] if used else [])})
        if req.target_model_id:
            model = self.registry.get(req.target_model_id)
            if model is None or not model.enabled:
                raise OrchestratorError(NOT_FOUND, f"model '{req.target_model_id}' not available")
            self._assign(task, model, "specified by caller (switch_model)")
        else:
            sel = self._pick(task, excluded)
            model = sel.model
            self._assign(task, model, f"switch_model: {sel.reason}")
        task.excluded_model_ids = excluded
        return model

    # ---- 7. complete_task ----------------------------------------------
    def complete_task(self, task_id: str, version: int) -> dict:
        task = self._load(task_id)
        task, path = completion.complete(self.store, task, version)
        return {
            "state": task.state.value,
            "final_version": task.final_version,
            "artifact_path": str(path),
        }

    # ---- views (CLI) ---------------------------------------------------
    def list_tasks(self) -> list[Task]:
        out = []
        for tid in self.store.list_ids():
            try:
                out.append(self._load(tid))
            except OrchestratorError as e:
                get_logger().warning("%s unreadable: %s", tid, e.message)
        return out

    def retry(self, task_id: str) -> Task:
        task = self._load(task_id)
        if not (task.error and task.error.retryable):
            raise OrchestratorError("invalid_transition", f"{task_id} is not retryable")
        transition(task, TaskState.PENDING, "manual retry")
        task.error = None
        self.store.save(task)
        return task
