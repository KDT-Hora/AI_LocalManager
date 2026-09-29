from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from .task import now


class ArtifactKind(StrEnum):
    INITIAL = "initial"
    MINOR_REVISION = "minor_revision"
    REGENERATE = "regenerate"
    MODEL_SWITCH = "model_switch"
    USER_EDIT = "user_edit"


class ArtifactVersion(BaseModel):
    version: int = Field(ge=1)
    model_id: str | None = None
    kind: ArtifactKind
    prompt_file: str = ""
    content_file: str
    content_hash: str
    parent_version: int | None = None
    created_at: datetime = Field(default_factory=now)
