"""Generate one artifact version with a backend and record the outcome."""

from __future__ import annotations

import json
import re

from ..backends.base import Backend
from ..errors import INVALID_OUTPUT, OrchestratorError
from ..logging_setup import get_logger
from ..models.artifact import ArtifactKind, ArtifactVersion
from ..models.model_definition import ModelDefinition
from ..models.task import Task, TaskState
from ..store.task_store import TaskStore
from .state_machine import transition

EXT = {"text": "txt", "json": "json", "code": "txt"}


def check_output(model: ModelDefinition, text: str) -> None:
    if not text.strip():
        raise OrchestratorError(INVALID_OUTPUT, f"model '{model.id}' returned empty output", True)
    if model.output_format == "json":
        body = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
        try:
            json.loads(body)
        except json.JSONDecodeError as e:
            raise OrchestratorError(
                INVALID_OUTPUT, f"model '{model.id}' returned invalid JSON: {e}", True
            ) from e


class Generator:
    def __init__(self, store: TaskStore, backend: Backend, vram_limit_gb: float | None) -> None:
        self.store = store
        self.backend = backend
        self.vram_limit_gb = vram_limit_gb
        self.current: ModelDefinition | None = None  # last model used (tie-break, unload)

    @property
    def current_id(self) -> str | None:
        return self.current.id if self.current else None

    async def generate(
        self,
        task: Task,
        model: ModelDefinition,
        prompt: str,
        kind: ArtifactKind,
        parent_version: int | None = None,
    ) -> ArtifactVersion:
        """Precondition: task is RUNNING. On success -> REVIEWING; on error -> FAILED."""
        log = get_logger()
        log.info("%s: generating with %s (%s)", task.task_id, model.id, kind)
        try:
            await self.backend.prepare(model, self.current, self.vram_limit_gb)
            text = await self.backend.chat(model, prompt)
            self.current = model
            check_output(model, text)
        except OrchestratorError as e:
            log.warning("%s: %s: %s", task.task_id, e.kind, e.message)
            self.store.fail(task, e.kind, e.message, e.retryable)
            raise
        ext = EXT.get(model.output_format, "txt")
        av = self.store.save_version(task, text, ext, kind, model.id, prompt, parent_version)
        transition(task, TaskState.REVIEWING, f"generated v{av.version:03d} by {model.id}")
        self.store.save(task)
        log.info("%s: v%03d saved -> REVIEWING", task.task_id, av.version)
        return av
