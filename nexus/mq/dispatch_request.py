"""Pure dispatch request contract for WBS 7.10."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from nexus.mq.agent_registry_events import secret_material_errors


DISPATCH_REQUEST_SCHEMA_VERSION = "4.19.dispatch.request.v1"
NON_BUSINESS_ASSIGNMENT_KIND = "non_business_probe"
BUSINESS_ASSIGNMENT_KIND = "business_task"
ASSIGNMENT_KINDS = {
    NON_BUSINESS_ASSIGNMENT_KIND,
    BUSINESS_ASSIGNMENT_KIND,
    "diagnostic",
    "readiness_probe",
}


@dataclass
class DispatchRequest:
    request_id: str
    correlation_id: str
    work_ref: str
    required_capability: str
    required_authority_scope: str
    required_privacy_scope: str
    allowed_task_boundary: str
    no_go_scope: list[str]
    assignment_kind: str = NON_BUSINESS_ASSIGNMENT_KIND
    target_agent_id: Optional[str] = None
    target_runtime_instance_id: Optional[str] = None
    expires_at: Optional[str] = None
    candidate_ttl_seconds: int = 60
    business_dispatch_authorized: bool = False
    evidence_refs: list[str] = field(default_factory=list)
    schema_version: str = DISPATCH_REQUEST_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DispatchRequestValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_dispatch_request(request: DispatchRequest, *, now_at: Optional[str] = None) -> DispatchRequestValidationResult:
    errors: list[str] = []
    if request.schema_version != DISPATCH_REQUEST_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_DISPATCH_REQUEST_SCHEMA")
    if request.not_business_completion is not True:
        errors.append("DISPATCH_REQUEST_CANNOT_BE_BUSINESS_COMPLETION")
    for field_name in [
        "request_id",
        "correlation_id",
        "work_ref",
        "required_capability",
        "required_authority_scope",
        "required_privacy_scope",
        "allowed_task_boundary",
    ]:
        if not getattr(request, field_name):
            errors.append(f"MISSING_{field_name.upper()}")
    if request.assignment_kind not in ASSIGNMENT_KINDS:
        errors.append(f"UNSUPPORTED_ASSIGNMENT_KIND: {request.assignment_kind}")
    if not request.no_go_scope:
        errors.append("MISSING_NO_GO_SCOPE")
    if request.candidate_ttl_seconds <= 0:
        errors.append("INVALID_CANDIDATE_TTL")
    if request.expires_at:
        expires_dt = _parse_iso(request.expires_at)
        now_dt = _parse_iso(now_at) if now_at else datetime.now(timezone.utc)
        if expires_dt is None or now_dt is None:
            errors.append("DISPATCH_REQUEST_EXPIRY_INVALID")
        elif expires_dt <= now_dt:
            errors.append("DISPATCH_REQUEST_EXPIRED")
    errors.extend(secret_material_errors(request.to_dict(), path="dispatch_request"))
    return DispatchRequestValidationResult(valid=not errors, errors=_dedupe(errors))


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
