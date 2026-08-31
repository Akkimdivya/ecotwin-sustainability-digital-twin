"""Vertex AI Gemini explanations with schema validation and demo-safe fallback."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.config import Settings
from app.models.explanation import ExplanationContent, SimulationExplanation
from app.models.simulation import RightsizeResult

LOGGER = logging.getLogger(__name__)
PROMPT_VERSION = "ecotwin-explanation-v1.0"

Generator = Callable[[RightsizeResult], Awaitable[ExplanationContent]]

SYSTEM_INSTRUCTION = """
You are EcoTwin's sustainability decision-support explainer.
Explain only the supplied, deterministic simulation JSON.
Never calculate, modify, round, replace, or invent any numeric value.
Do not introduce numeric thresholds, timelines, or counts that are absent from the supplied JSON.
Do not claim that a production change was performed.
State clearly when the risk is HIGH and do not recommend direct implementation in that case.
Keep rationale concise; do not reveal chain-of-thought or hidden reasoning.
Return only the requested structured response.
""".strip()

NUMERIC_TOKEN = re.compile(r"(?<![A-Za-z0-9_.-])\d+(?:\.\d+)?(?![A-Za-z0-9_.-])")


def _normalise_number(value: object) -> Decimal:
    return Decimal(str(value)).normalize()


def _result_numbers(value: Any) -> set[Decimal]:
    if isinstance(value, dict):
        return set().union(*(_result_numbers(item) for item in value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(_result_numbers(item) for item in value))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {_normalise_number(value)}
    return set()


def _validate_numerical_faithfulness(
    content: ExplanationContent,
    result: RightsizeResult,
) -> ExplanationContent:
    """Reject model prose that introduces numbers outside the deterministic result."""

    allowed = _result_numbers(result.model_dump(mode="json"))
    fields = (
        content.summary,
        content.recommendation,
        content.rationale,
        content.rollback_trigger,
        *content.validation_steps,
        *content.limitations,
    )
    unexpected: set[str] = set()
    for field in fields:
        for token in NUMERIC_TOKEN.findall(field):
            try:
                if _normalise_number(token) not in allowed:
                    unexpected.add(token)
            except InvalidOperation:
                unexpected.add(token)
    if unexpected:
        values = ", ".join(sorted(unexpected))
        raise ValueError(f"Gemini introduced unsupported numeric values: {values}")
    return content


class ExplanationService:
    def __init__(self, settings: Settings, generator: Generator | None = None) -> None:
        self.settings = settings
        self._generator = generator or self._generate_vertex
        self._cache: dict[str, SimulationExplanation] = {}
        self._lock = asyncio.Lock()

    async def explain(self, result: RightsizeResult) -> SimulationExplanation:
        cached = self._cache.get(result.simulation_id)
        if cached is not None:
            return cached.model_copy(update={"cached": True})

        async with self._lock:
            cached = self._cache.get(result.simulation_id)
            if cached is not None:
                return cached.model_copy(update={"cached": True})

            explanation = await self._create(result)
            self._cache[result.simulation_id] = explanation
            return explanation

    async def _create(self, result: RightsizeResult) -> SimulationExplanation:
        if not self.settings.gemini_enabled:
            return self._fallback(result, "Gemini is disabled by configuration")
        if not self.settings.gcp_project:
            return self._fallback(result, "Google Cloud project is not configured")

        final_error = "Vertex AI explanation unavailable"
        for attempt in range(2):
            try:
                content = await asyncio.wait_for(
                    self._generator(result),
                    timeout=self.settings.gemini_timeout_seconds,
                )
                content = _validate_numerical_faithfulness(content, result)
                return SimulationExplanation(
                    simulation_id=result.simulation_id,
                    content=content,
                    provider="VERTEX_AI",
                    model=self.settings.gemini_model,
                    prompt_version=PROMPT_VERSION,
                    generated_at=datetime.now(UTC),
                )
            except Exception as exc:
                final_error = type(exc).__name__
                LOGGER.warning(
                    "Gemini explanation attempt %s failed: %s",
                    attempt + 1,
                    final_error,
                )
        return self._fallback(result, final_error)

    async def _generate_vertex(self, result: RightsizeResult) -> ExplanationContent:
        from google import genai
        from google.genai import types

        client = genai.Client(
            vertexai=True,
            project=self.settings.gcp_project,
            location=self.settings.gemini_location,
            http_options=types.HttpOptions(api_version="v1"),
        )
        response = await client.aio.models.generate_content(
            model=self.settings.gemini_model,
            contents=(
                "Explain this EcoTwin simulation result. Use every risk reason, preserve all "
                "numbers exactly, and provide concrete validation steps and a rollback trigger.\n"
                + json.dumps(result.model_dump(mode="json"), sort_keys=True)
            ),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=ExplanationContent,
                temperature=0.1,
                max_output_tokens=2000,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if response.parsed is not None:
            return ExplanationContent.model_validate(response.parsed)
        if not response.text:
            raise ValueError("Gemini returned an empty response")
        return ExplanationContent.model_validate_json(response.text)

    def _fallback(self, result: RightsizeResult, reason: str) -> SimulationExplanation:
        risk = result.risk.level
        if risk == "HIGH":
            recommendation = (
                "Do not apply the proposed right-size directly. Test a safer intermediate "
                "configuration or collect stronger evidence first."
            )
        elif risk == "MEDIUM":
            recommendation = "Validate with a monitored canary before considering implementation."
        else:
            recommendation = "Proceed only through a monitored canary with a prepared rollback."

        content = ExplanationContent(
            summary=(
                f"The scenario estimates ${result.impact.monthly_cost_savings_usd:.2f} in monthly "
                f"savings and {result.impact.carbon_reduction_kgco2e:.3f} kgCO2e in monthly "
                f"operational-carbon reduction, with {risk} risk."
            ),
            recommendation=recommendation,
            rationale=(
                f"Projected CPU p95 is {result.performance.predicted_cpu_p95_pct:.1f}% and "
                f"projected memory p95 is {result.performance.predicted_memory_p95_pct:.1f}%. "
                + " ".join(result.risk.reasons)
            ),
            validation_steps=(
                "Confirm the resource owner, traffic pattern and critical dependency paths.",
                "Replay representative load against the proposed configuration in staging.",
                "Run a canary while tracking CPU, memory, latency and error-rate service levels.",
                (
                    "Verify that backups and the previous machine configuration are ready for "
                    "rollback."
                ),
            ),
            rollback_trigger=(
                "Rollback if CPU or memory pressure exceeds the validated boundary, or if latency "
                "or error rate breaches the workload service-level target."
            ),
            limitations=(
                (
                    "This is a capacity proxy based on controlled telemetry, not a production "
                    "load test."
                ),
                result.confidence_reason,
                "Cost and carbon values use versioned scenario assumptions.",
            ),
        )
        return SimulationExplanation(
            simulation_id=result.simulation_id,
            content=content,
            provider="DETERMINISTIC_FALLBACK",
            model="deterministic-template-v1.0",
            prompt_version=PROMPT_VERSION,
            generated_at=datetime.now(UTC),
            fallback_reason=reason,
        )
