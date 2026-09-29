from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LaunchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["jit", "lms_cli"] = "jit"
    context_length: int | None = Field(default=None, gt=0)  # passed to `lms load -c`


class ModelDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    lmstudio_id: str = Field(min_length=1)
    display_name: str = ""
    capabilities: list[str] = Field(min_length=1)
    priority: int = Field(ge=0, le=100)
    max_context: int = Field(gt=0)
    required_vram_gb: float = Field(default=0, ge=0)
    recommended_settings: dict = Field(default_factory=dict)
    output_format: Literal["text", "json", "code", "image"] = "text"
    model_type: Literal["llm", "vision", "image_gen"] = "llm"
    launch: LaunchConfig = Field(default_factory=LaunchConfig)
    enabled: bool = True

    @field_validator("capabilities")
    @classmethod
    def _unique_caps(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("capabilities must be unique")
        return v


class ModelsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vram_limit_gb: float | None = Field(default=None, ge=0)
    models: list[ModelDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> ModelsConfig:
        ids = [m.id for m in self.models]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            raise ValueError(f"duplicate model id: {sorted(dup)}")
        return self
