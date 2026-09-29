from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .task import now

Action = Literal["minor", "regenerate", "switch_model"]


class Issue(BaseModel):
    aspect: str
    description: str
    severity: Literal["low", "medium", "high"] = "medium"


class ValidationResult(BaseModel):
    version: int = Field(ge=1)
    verdict: Literal["pass", "fail"]
    issues: list[Issue] = Field(default_factory=list)
    aspects_checked: list[str] = Field(default_factory=list)
    recommended_action: Action | None = None
    created_at: datetime = Field(default_factory=now)

    @model_validator(mode="after")
    def _fail_needs_issues(self) -> ValidationResult:
        if self.verdict == "fail" and not self.issues:
            raise ValueError("issues are required when verdict is fail")
        return self


class RevisionRequest(BaseModel):
    task_id: str
    base_version: int = Field(ge=1)
    method: Action
    instructions: str = Field(min_length=1)
    target_model_id: str | None = None
