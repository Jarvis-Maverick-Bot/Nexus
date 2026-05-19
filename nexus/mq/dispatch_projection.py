"""Read-only dispatch eligibility projection helpers for Agent Access."""

from __future__ import annotations

from typing import Any

from nexus.mq.dispatch_eligibility import DispatchEligibilityDecision
DISPATCH_PROJECTION_FIELDS = {
    "projection_type",
    "decision_status",
    "request_id",
    "correlation_id",
    "assignment_id",
    "target_agent_id",
    "target_runtime_instance_id",
    "registry_revision_seen",
    "heartbeat_timestamp_observed",
    "startup_packet_ref",
    "startup_packet_expires_at",
    "readiness_evidence_ref",
    "required_capability",
    "required_authority_scope",
    "required_privacy_scope",
    "allowed_task_boundary",
    "assignment_kind",
    "business_execution_allowed",
    "rejection_codes",
    "eligible_agent_ids",
    "expires_at",
    "evidence_refs",
    "read_only",
    "not_business_completion",
}


def build_dispatch_projection(decision: DispatchEligibilityDecision) -> dict[str, Any]:
    if decision.candidate is None:
        payload: dict[str, Any] = {
            "projection_type": "dispatch_eligibility",
            "decision_status": "rejected",
            "rejection_codes": _all_rejections(decision),
            "eligible_agent_ids": list(decision.eligible_agent_ids),
            "read_only": True,
            "not_business_completion": True,
        }
        return _filtered_redacted(payload)

    candidate = decision.candidate
    payload = {
        "projection_type": "dispatch_assignment_candidate",
        "decision_status": "candidate",
        "request_id": candidate.request_id,
        "correlation_id": candidate.correlation_id,
        "assignment_id": candidate.assignment_id,
        "target_agent_id": candidate.target_agent_id,
        "target_runtime_instance_id": candidate.target_runtime_instance_id,
        "registry_revision_seen": candidate.registry_revision_seen,
        "heartbeat_timestamp_observed": candidate.heartbeat_timestamp_observed,
        "startup_packet_ref": candidate.startup_packet_ref,
        "startup_packet_expires_at": candidate.startup_packet_expires_at,
        "readiness_evidence_ref": candidate.readiness_evidence_ref,
        "required_capability": candidate.required_capability,
        "required_authority_scope": candidate.required_authority_scope,
        "required_privacy_scope": candidate.required_privacy_scope,
        "allowed_task_boundary": candidate.allowed_task_boundary,
        "assignment_kind": candidate.assignment_kind,
        "business_execution_allowed": candidate.business_execution_allowed,
        "rejection_codes": _all_rejections(decision),
        "eligible_agent_ids": list(decision.eligible_agent_ids),
        "expires_at": candidate.expires_at,
        "evidence_refs": list(candidate.evidence_refs),
        "read_only": True,
        "not_business_completion": True,
    }
    return _filtered_redacted(payload)


def _all_rejections(decision: DispatchEligibilityDecision) -> list[str]:
    codes: list[str] = []
    codes.extend(decision.errors)
    for reasons in decision.rejected.values():
        codes.extend(reasons)
    deduped: list[str] = []
    for code in codes:
        if code not in deduped:
            deduped.append(code)
    return deduped


def _filtered_redacted(payload: dict[str, Any]) -> dict[str, Any]:
    filtered = {key: value for key, value in payload.items() if key in DISPATCH_PROJECTION_FIELDS}
    return _redact_value(filtered)


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(str(key)):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_value(item)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str) and _looks_secret(value):
        return "[REDACTED]"
    return value


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    if lowered.endswith("_ref") or lowered.endswith("_refs"):
        return False
    return any(marker in lowered for marker in ("authorization", "credential", "password", "private_key", "secret", "token"))


def _looks_secret(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("sk-") or any(
        marker in lowered for marker in ("authorization:", "bearer ", "password=", "secret=", "token=")
    )
