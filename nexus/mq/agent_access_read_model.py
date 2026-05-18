"""Read-only Agent Access projection for 4.19."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from nexus.mq.agent_registry import AgentRegistryRecord, DispatchAssignmentRecord
from nexus.mq.channel_outbox import ChannelOutboxItem


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
) -> AgentAccessReadModel:
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
            }
            for agent in agents
        ],
        dispatch=[
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
        adapter_health=list(adapter_health),
        exceptions=list(exceptions),
        evidence=list(evidence),
    )


def export_agent_access_evidence(read_model: AgentAccessReadModel) -> dict[str, Any]:
    return {
        "evidence": list(read_model.evidence),
        "read_only": True,
        "not_business_completion": True,
        "status_families": dict(read_model.status_families),
    }
