"""Read-only Agent Access projection for 4.19."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from nexus.mq.agent_registry import AgentRegistryRecord, DispatchAssignmentRecord
from nexus.mq.channel_outbox import ChannelOutboxItem
from nexus.mq.operational_observability import redact_payload


ADAPTER_HEALTH_FIELDS = {
    "adapter_id",
    "adapter_type",
    "status",
    "last_event_at",
    "error_ref",
    "supported_protocol_versions",
    "evidence_refs",
}
EXCEPTION_FIELDS = {
    "event_type",
    "severity",
    "owner",
    "related_record_ref",
    "next_action",
    "evidence_refs",
}
EVIDENCE_FIELDS = {
    "evidence_ref",
    "source_doc",
    "source_record",
    "timestamp",
    "checksum_ref",
}
HEARTBEAT_FIELDS = {
    "agent_id",
    "supervisor_state",
    "presence_state",
    "last_heartbeat_at",
    "heartbeat_ttl_seconds",
    "heartbeat_sequence",
    "stale_at",
    "offline_at",
    "health_summary_ref",
    "heartbeat_evidence_ref",
    "projection_status",
}
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
PRIVATE_AGENT_PROJECTION_FIELDS = {
    "projection_type",
    "contract_id",
    "contract_revision",
    "contract_status",
    "trust_class",
    "adapter_agent_id",
    "adapter_runtime_instance_id",
    "diagnostic_only",
    "eligibility_status",
    "invocation_status",
    "task_package_id",
    "task_package_hash",
    "result_id",
    "result_state",
    "evidence_status",
    "safety_status",
    "governed_status",
    "business_state_committed",
    "rejection_codes",
    "evidence_refs",
    "read_only",
    "not_business_completion",
}


@dataclass
class AgentAccessReadModel:
    agent_roster: list[dict[str, Any]]
    readiness: list[dict[str, Any]]
    presence: list[dict[str, Any]]
    dispatch: list[dict[str, Any]]
    outbox: list[dict[str, Any]]
    adapter_health: list[dict[str, Any]]
    exceptions: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    private_agents: list[dict[str, Any]] = field(default_factory=list)
    status_families: dict[str, str] = field(default_factory=lambda: {
        "ack": "durable_intake_only",
        "progress": "governed_evidence_state_commit_required",
        "delivery": "visible_delivery_only",
        "completion": "governed_completion_only",
    })
    read_only: bool = True
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def apply_operator_action(self, action: str) -> None:
        if action not in {"refresh", "filter", "open_evidence"}:
            raise PermissionError("AGENT_ACCESS_READ_MODEL_IS_READ_ONLY")


def build_agent_access_read_model(
    *,
    agents: list[AgentRegistryRecord],
    assignments: list[DispatchAssignmentRecord],
    outbox_items: list[ChannelOutboxItem],
    adapter_health: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    heartbeat_projection: dict[str, dict[str, Any]] | None = None,
    dispatch_projection: list[dict[str, Any]] | None = None,
    private_agent_projection: list[dict[str, Any]] | None = None,
) -> AgentAccessReadModel:
    heartbeat_projection = heartbeat_projection or {}
    dispatch_projection = dispatch_projection or []
    private_agent_projection = private_agent_projection or []
    return AgentAccessReadModel(
        agent_roster=[
            {
                "agent_id": agent.agent_id,
                "role": agent.role,
                "owner": agent.owner_principal_id,
                "runtime_type": agent.runtime_type,
                "capabilities": list(agent.capabilities),
                "authority_scopes": list(agent.authority_scopes),
                "registry_status": agent.registry_status,
            }
            for agent in agents
        ],
        readiness=[
            {
                "agent_id": agent.agent_id,
                "initialization_status": agent.initialization_status,
                "startup_packet_ref": agent.startup_packet_ref,
                "readiness_evidence_ref": agent.readiness_evidence_ref,
                "last_verified_at": agent.updated_at,
                "blocker": agent.readiness_blocker,
            }
            for agent in agents
        ],
        presence=[
            {
                "agent_id": agent.agent_id,
                "presence_state": agent.presence_state,
                "last_heartbeat_at": agent.last_heartbeat_at,
                "ttl_seconds": agent.heartbeat_ttl_seconds,
                "load_score": agent.load_score,
                "accepting_new_work": agent.accepting_new_work,
                **_heartbeat_projection_for(agent.agent_id, heartbeat_projection),
            }
            for agent in agents
        ],
        dispatch=[
            *[
                {
                    "assignment_id": assignment.assignment_id,
                    "work_ref": assignment.work_ref,
                    "required_capability": assignment.required_capability,
                    "assigned_agent": assignment.assigned_agent_id,
                    "state": assignment.dispatch_state,
                    "timeout_at": assignment.timeout_at,
                    "reallocation_count": assignment.reallocation_count,
                }
                for assignment in assignments
            ],
            *_sanitize_records(dispatch_projection, DISPATCH_PROJECTION_FIELDS),
        ],
        outbox=[
            {
                "outbox_id": item.outbox_id,
                "target_channel": item.target_channel,
                "status": item.status,
                "attempt_count": item.attempt_count,
                "channel_message_ref": item.channel_message_ref,
                "last_error_ref": item.last_error_ref,
            }
            for item in outbox_items
        ],
        adapter_health=_sanitize_records(adapter_health, ADAPTER_HEALTH_FIELDS),
        exceptions=_sanitize_records(exceptions, EXCEPTION_FIELDS),
        evidence=_sanitize_records(evidence, EVIDENCE_FIELDS),
        private_agents=_sanitize_records(private_agent_projection, PRIVATE_AGENT_PROJECTION_FIELDS),
    )


def export_agent_access_evidence(read_model: AgentAccessReadModel) -> dict[str, Any]:
    return {
        "evidence": _sanitize_records(read_model.evidence, EVIDENCE_FIELDS),
        "read_only": True,
        "not_business_completion": True,
        "status_families": dict(read_model.status_families),
    }


def _sanitize_records(records: list[dict[str, Any]], allowed_fields: set[str]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        filtered = {key: value for key, value in record.items() if key in allowed_fields}
        sanitized.append(_redact_value(redact_payload(filtered)))
    return sanitized


def _heartbeat_projection_for(agent_id: str, heartbeat_projection: dict[str, dict[str, Any]]) -> dict[str, Any]:
    raw = heartbeat_projection.get(agent_id)
    if not isinstance(raw, dict):
        return {}
    sanitized = _sanitize_records([raw], HEARTBEAT_FIELDS)
    if not sanitized:
        return {}
    sanitized[0].pop("agent_id", None)
    return sanitized[0]


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
