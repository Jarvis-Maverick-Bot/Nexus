"""Bounded LLM advisory helpers for WBS 7.19."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LlmAdvisoryContext:
    source_refs: list[str]
    deterministic_fields: dict[str, Any]
    eligible_candidate_ids: list[str]
    no_go_scope: list[str]
    advisory_only: bool = True
    not_business_completion: bool = True


@dataclass
class LlmAdvisoryValidationResult:
    ok: bool
    errors: list[str]


def build_llm_advisory_context(
    *,
    source_refs: list[str],
    deterministic_fields: dict[str, Any],
    eligible_candidate_ids: list[str],
    no_go_scope: list[str],
) -> LlmAdvisoryContext:
    safe_fields = {
        key: value
        for key, value in deterministic_fields.items()
        if key not in {"secret", "token", "password", "credential"}
    }
    return LlmAdvisoryContext(
        source_refs=list(source_refs),
        deterministic_fields=safe_fields,
        eligible_candidate_ids=list(eligible_candidate_ids),
        no_go_scope=list(no_go_scope),
    )


def validate_llm_advisory_output(
    *,
    output: dict[str, Any],
    eligible_candidate_ids: list[str],
    no_go_scope: list[str],
    telemetry_ref: str,
) -> LlmAdvisoryValidationResult:
    errors: list[str] = []
    owner = output.get("suggested_owner_id")
    if owner and owner not in eligible_candidate_ids:
        errors.append("LLM_OWNER_NOT_ELIGIBLE")
    if output.get("added_scope"):
        errors.append("LLM_SCOPE_EXPANSION_REJECTED")
    if not telemetry_ref:
        errors.append("MISSING_MODEL_CALL_TELEMETRY")
    if output.get("not_business_completion") is False:
        errors.append("LLM_OUTPUT_CANNOT_BE_BUSINESS_COMPLETION")
    return LlmAdvisoryValidationResult(ok=not errors, errors=errors)
