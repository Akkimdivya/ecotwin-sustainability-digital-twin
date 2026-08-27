"""Structured Gemini explanation contracts that contain no hidden calculations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from .domain import DomainModel


class FrozenExplanationModel(DomainModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class ExplanationContent(FrozenExplanationModel):
    summary: str = Field(min_length=1, max_length=600)
    recommendation: str = Field(min_length=1, max_length=600)
    rationale: str = Field(min_length=1, max_length=1000)
    validation_steps: tuple[str, ...] = Field(min_length=2, max_length=6)
    rollback_trigger: str = Field(min_length=1, max_length=500)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=6)


class SimulationExplanation(FrozenExplanationModel):
    simulation_id: str
    content: ExplanationContent
    provider: Literal["VERTEX_AI", "DETERMINISTIC_FALLBACK"]
    model: str
    prompt_version: str
    generated_at: datetime
    fallback_reason: str | None = None
    cached: bool = False
