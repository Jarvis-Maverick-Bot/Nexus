"""Agent transport binding metadata and envelope construction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexus.mq.message_contracts import ExecutionMessageEnvelope, build_execution_envelope
from nexus.mq.payloads import PayloadContract
from nexus.mq.protocol_routing import validate_agent_transport_subject
from nexus.mq.taxonomy import MESSAGE_CLASSES_BY_TYPE


AGENT_TRANSPORT_WORKFLOW_TYPE = "agent_transport"


@dataclass
class AgentTransportBinding:
    run_id: str
    source_agent_id: str
    source_runtime_instance_id: str
    source_role: str
    target_agent_id: str
    target_runtime_instance_id: str
    target_role: str
    capability: str
    authority_scope: str
    binding_policy_ref: str
    subject: str
    reply_to_subject: str
    payload_schema: str
    credential_ref: str
    workflow_type: str = AGENT_TRANSPORT_WORKFLOW_TYPE
    workflow_version: str = "1.0"
    no_go_scope: list[str] = field(default_factory=list)
    evidence_refs: list[Any] = field(default_factory=list)


def validate_agent_transport_binding(binding: AgentTransportBinding) -> list[str]:
    errors: list[str] = []
    for field_name in (
        "run_id",
        "source_agent_id",
        "source_runtime_instance_id",
        "source_role",
        "target_agent_id",
        "target_runtime_instance_id",
        "target_role",
        "capability",
        "authority_scope",
        "binding_policy_ref",
        "subject",
        "reply_to_subject",
        "payload_schema",
        "credential_ref",
        "workflow_type",
        "workflow_version",
    ):
        if not getattr(binding, field_name):
            errors.append(f"MISSING_BINDING_FIELD: {field_name}")
    for subject_field in ("subject", "reply_to_subject"):
        routed = validate_agent_transport_subject(str(getattr(binding, subject_field)), binding.run_id)
        if not routed.valid:
            errors.extend(f"{subject_field}: {error}" for error in (routed.errors or []))
    if not binding.no_go_scope:
        errors.append("MISSING_BINDING_FIELD: no_go_scope")
    if binding.credential_ref.lower().startswith(("env:", "secret:", "vault:")):
        errors.append("AGENT_TRANSPORT_BINDING_MUST_REFERENCE_RESOLVER_OUTPUT_NOT_SECRET")
    return list(dict.fromkeys(errors))


def build_agent_transport_envelope(
    *,
    binding: AgentTransportBinding,
    message_type: str,
    payload: dict | PayloadContract,
    payload_hash: str,
    expires_at: str,
    idempotency_key: str,
    correlation_id: str,
    causation_id: str | None = None,
) -> ExecutionMessageEnvelope:
    envelope = build_execution_envelope(
        message_type=message_type,
        message_class=MESSAGE_CLASSES_BY_TYPE[message_type],
        workflow_instance_id=binding.run_id,
        workflow_type=binding.workflow_type,
        workflow_version=binding.workflow_version,
        producer=binding.source_agent_id,
        payload=payload,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        causation_id=causation_id,
        intended_consumer=binding.target_agent_id,
        evidence_refs=list(binding.evidence_refs),
        expires_at=expires_at,
        ack_policy="explicit",
        source_agent_id=binding.source_agent_id,
        source_runtime_instance_id=binding.source_runtime_instance_id,
        source_role=binding.source_role,
        target_agent_id=binding.target_agent_id,
        target_runtime_instance_id=binding.target_runtime_instance_id,
        target_role=binding.target_role,
        authority_scope=binding.authority_scope,
        capability=binding.capability,
        binding_policy_ref=binding.binding_policy_ref,
        reply_to_subject=binding.reply_to_subject,
        payload_schema=binding.payload_schema,
        payload_hash=payload_hash,
        no_go_scope=list(binding.no_go_scope),
    )
    return envelope
