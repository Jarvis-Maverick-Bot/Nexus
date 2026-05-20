"""4.19 read-only capability gate for WBS 7.17 message send/receive tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from nexus.mq.agent_registry import AgentRegistryRecord, dispatch_ineligibility_reasons


@dataclass
class AgentMessageCapabilityRequest:
    source_agent_id: str
    source_runtime_instance_id: str
    target_agent_id: str
    target_runtime_instance_id: str
    capability: str
    authority_scope: str
    binding_policy_ref: str
    subject: str
    payload_schema: str
    allowed_task_boundary: str = "agent_transport_diagnostic_only"
    required_privacy_scope: str = "project"


@dataclass
class AgentMessagePolicyDecision:
    allowed: bool
    binding_policy_ref: str
    source_agent_id: str
    source_runtime_instance_id: str
    target_agent_id: str
    target_runtime_instance_id: str
    capability: str
    authority_scope: str
    subject: str
    payload_schema: str
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


def evaluate_agent_message_capability(
    request: AgentMessageCapabilityRequest,
    *,
    target_record: Optional[AgentRegistryRecord] = None,
    source_record: Optional[AgentRegistryRecord] = None,
    now_at: Optional[str] = None,
) -> AgentMessagePolicyDecision:
    errors: list[str] = []
    for field_name in (
        "source_agent_id",
        "source_runtime_instance_id",
        "target_agent_id",
        "target_runtime_instance_id",
        "capability",
        "authority_scope",
        "binding_policy_ref",
        "subject",
        "payload_schema",
    ):
        if not getattr(request, field_name):
            errors.append(f"MISSING_POLICY_FIELD: {field_name}")

    if target_record is None:
        errors.append("TARGET_REGISTRY_RECORD_REQUIRED")
    else:
        if target_record.agent_id != request.target_agent_id:
            errors.append("TARGET_AGENT_ID_MISMATCH")
        if target_record.runtime_instance_id != request.target_runtime_instance_id:
            errors.append("TARGET_RUNTIME_INSTANCE_MISMATCH")
        errors.extend(
            dispatch_ineligibility_reasons(
                target_record,
                required_capability=request.capability,
                required_authority_scope=request.authority_scope,
                required_privacy_scope=request.required_privacy_scope,
                allowed_task_boundary=request.allowed_task_boundary,
                now_at=now_at,
            )
        )

    if source_record is not None:
        if source_record.agent_id != request.source_agent_id:
            errors.append("SOURCE_AGENT_ID_MISMATCH")
        if source_record.runtime_instance_id != request.source_runtime_instance_id:
            errors.append("SOURCE_RUNTIME_INSTANCE_MISMATCH")
        if source_record.registry_status != "active":
            errors.append(f"SOURCE_REGISTRY_NOT_ACTIVE: {source_record.registry_status}")

    if now_at:
        parsed = _parse_iso(now_at)
        if parsed is None:
            errors.append("POLICY_NOW_AT_INVALID")

    deduped = list(dict.fromkeys(errors))
    return AgentMessagePolicyDecision(
        allowed=len(deduped) == 0,
        binding_policy_ref=request.binding_policy_ref,
        source_agent_id=request.source_agent_id,
        source_runtime_instance_id=request.source_runtime_instance_id,
        target_agent_id=request.target_agent_id,
        target_runtime_instance_id=request.target_runtime_instance_id,
        capability=request.capability,
        authority_scope=request.authority_scope,
        subject=request.subject,
        payload_schema=request.payload_schema,
        errors=deduped,
    )


def _parse_iso(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
