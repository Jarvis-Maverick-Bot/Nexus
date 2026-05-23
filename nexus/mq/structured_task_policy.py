"""Deterministic decomposition and routing policy for WBS 7.19."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Optional

from nexus.mq.structured_task_models import (
    DecompositionPlan,
    RuntimeEligibilitySnapshot,
    SourceAuthoritySet,
    TaskEnvelope,
    TaskUnit,
)
from nexus.mq.structured_task_validation import validate_task_unit


APPROVED_INPUT_KINDS = {"approved_objective", "wbs_row", "goal_driven_command_ref"}


@dataclass
class SourceAuthorityResult:
    ok: bool
    authority: Optional[SourceAuthoritySet] = None
    errors: list[str] = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


@dataclass
class DecompositionResult:
    ok: bool
    plan: Optional[DecompositionPlan] = None
    errors: list[str] = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


@dataclass
class RouteDecision:
    ok: bool
    selected_owner_id: Optional[str] = None
    eligible_owner_ids: list[str] = None
    rejected: dict[str, list[str]] = None
    errors: list[str] = None
    not_business_completion: bool = True

    def __post_init__(self) -> None:
        if self.eligible_owner_ids is None:
            self.eligible_owner_ids = []
        if self.rejected is None:
            self.rejected = {}
        if self.errors is None:
            self.errors = []


def resolve_source_authority(
    *,
    input_kind: str,
    source_refs: list[str],
    source_hash: str,
    policy_hash: str,
) -> SourceAuthorityResult:
    errors: list[str] = []
    if input_kind not in APPROVED_INPUT_KINDS:
        errors.append("UNSUPPORTED_SOURCE_AUTHORITY_KIND")
    if not source_refs:
        errors.append("MISSING_SOURCE_AUTHORITY")
    if not source_hash:
        errors.append("MISSING_SOURCE_HASH")
    if not policy_hash:
        errors.append("MISSING_POLICY_HASH")
    if errors:
        return SourceAuthorityResult(False, errors=errors)
    seed = "|".join([input_kind, *source_refs, source_hash, policy_hash])
    digest = sha256(seed.encode("utf-8")).hexdigest()[:16]
    return SourceAuthorityResult(
        True,
        authority=SourceAuthoritySet(
            authority_id=f"source-authority-{digest}",
            input_kind=input_kind,
            source_refs=list(source_refs),
            source_hash=source_hash,
            policy_hash=policy_hash,
        ),
    )


def build_decomposition_plan(
    *,
    envelope: TaskEnvelope,
    child_specs: list[dict[str, Any]],
) -> DecompositionResult:
    if any(str(dep).startswith("blocked:") for dep in envelope.dependencies):
        return DecompositionResult(False, errors=["DEPENDENCY_BLOCKED"])
    if not envelope.source_refs:
        return DecompositionResult(False, errors=["MISSING_SOURCE_AUTHORITY"])
    tasks: list[TaskUnit] = []
    errors: list[str] = []
    for spec in child_specs:
        task = TaskUnit(
            task_id=spec.get("task_id", ""),
            parent_id=envelope.task_id,
            title=spec.get("title", ""),
            objective=spec.get("objective", envelope.objective),
            source_refs=list(envelope.source_refs),
            source_hash=envelope.source_hash,
            owner=spec.get("owner", "thunder"),
            verifier=spec.get("verifier", "nova"),
            dependencies=list(spec.get("dependencies", [])),
            priority=spec.get("priority", "normal"),
            status="validated",
            dod=list(spec.get("dod", envelope.deliverables)),
            no_go_scope=list(spec.get("no_go_scope", envelope.no_go_scope)),
            allowed_tools=list(spec.get("allowed_tools", ["pytest"])),
            allowed_write_surfaces=list(spec.get("allowed_write_surfaces", ["nexus/mq/structured_task_*.py"])),
            evidence_requirements=list(spec.get("evidence_requirements", envelope.deliverables)),
            stop_conditions=list(spec.get("stop_conditions", envelope.stop_conditions)),
            escalation_conditions=list(spec.get("escalation_conditions", ["nova-review"])),
        )
        validation = validate_task_unit(task)
        if validation.ok:
            tasks.append(task)
        else:
            errors.extend(validation.errors)
    if errors:
        return DecompositionResult(False, errors=_dedupe(errors))
    plan_seed = "|".join([envelope.task_id, envelope.source_hash, envelope.policy_hash, str(len(tasks))])
    digest = sha256(plan_seed.encode("utf-8")).hexdigest()[:16]
    return DecompositionResult(
        True,
        plan=DecompositionPlan(
            plan_id=f"decomposition-plan-{digest}",
            source_objective=envelope.objective,
            policy_ref=envelope.policy_hash,
            generated_tasks=tasks,
            dependency_graph={task.task_id: list(task.dependencies) for task in tasks},
            rejected_candidates=[],
            ambiguity_notes=[],
            validation_result="validated",
        ),
    )


def filter_route_candidates(
    *,
    task_unit: TaskUnit,
    snapshot: RuntimeEligibilitySnapshot,
    required_capability: str,
    required_authority_scope: str,
) -> RouteDecision:
    if not task_unit.source_refs:
        return RouteDecision(False, errors=["MISSING_TASK_SOURCE_REFS"])
    eligible: list[dict[str, Any]] = []
    rejected: dict[str, list[str]] = {}
    for candidate in snapshot.candidate_owners:
        owner_id = str(candidate.get("owner_id", ""))
        reasons = _candidate_rejection_reasons(
            candidate,
            task_unit=task_unit,
            required_capability=required_capability,
            required_authority_scope=required_authority_scope,
        )
        if reasons:
            rejected[owner_id or "unknown"] = reasons
        else:
            eligible.append(candidate)
    if not eligible:
        return RouteDecision(False, rejected=rejected, errors=["BLOCKED_NO_ELIGIBLE_AGENT"])
    if len(eligible) > 1:
        return RouteDecision(
            False,
            eligible_owner_ids=[str(item["owner_id"]) for item in eligible],
            rejected=rejected,
            errors=["BLOCKED_AMBIGUOUS_OWNER"],
        )
    selected = eligible[0]
    return RouteDecision(
        True,
        selected_owner_id=str(selected["owner_id"]),
        eligible_owner_ids=[str(selected["owner_id"])],
        rejected=rejected,
    )


def _candidate_rejection_reasons(
    candidate: dict[str, Any],
    *,
    task_unit: TaskUnit,
    required_capability: str,
    required_authority_scope: str,
) -> list[str]:
    reasons: list[str] = []
    if candidate.get("verifier_id") == candidate.get("owner_id"):
        reasons.append("OWNER_EQUALS_VERIFIER")
    if candidate.get("owner_id") == task_unit.verifier:
        reasons.append("OWNER_EQUALS_TASK_VERIFIER")
    if required_capability not in candidate.get("capabilities", []):
        reasons.append("CAPABILITY_MISMATCH")
    if required_authority_scope not in candidate.get("authority_scopes", []):
        reasons.append("AUTHORITY_SCOPE_MISMATCH")
    if candidate.get("readiness") != "ready":
        reasons.append("READINESS_NOT_READY")
    if candidate.get("freshness") != "fresh":
        reasons.append("STALE_AGENT_ACCESS")
    if candidate.get("capacity_available") is not True:
        reasons.append("NO_CAPACITY")
    if candidate.get("channel_available") is not True:
        reasons.append("CHANNEL_UNAVAILABLE")
    if not set(task_unit.allowed_tools).issubset(set(candidate.get("allowed_tools", []))):
        reasons.append("TOOLS_NOT_ALLOWED")
    if not set(task_unit.allowed_write_surfaces).issubset(set(candidate.get("allowed_write_surfaces", []))):
        reasons.append("WRITE_SURFACE_NOT_ALLOWED")
    return reasons


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
