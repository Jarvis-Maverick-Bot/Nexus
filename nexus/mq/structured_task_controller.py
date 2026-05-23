"""Safe/off Structured Task Handoff Controller facade for WBS 7.19."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Optional, Any

from nexus.mq.durable_state import DurableStateStore
from nexus.mq.structured_task_models import (
    OwnerHandoffPacket,
    RuntimeEligibilitySnapshot,
    TaskEnvelope,
    TaskUnit,
)
from nexus.mq.structured_task_persistence import write_structured_task_record
from nexus.mq.structured_task_policy import filter_route_candidates
from nexus.mq.structured_task_validation import validate_owner_handoff_packet, validate_task_envelope, validate_task_unit


@dataclass
class StructuredTaskControllerPolicy:
    controller_enabled: bool = False
    llm_advisory_enabled: bool = False
    live_dispatch_enabled: bool = False
    business_acceptance_enabled: bool = False


@dataclass
class OwnerHandoffPreparationResult:
    ok: bool
    packet: Optional[OwnerHandoffPacket] = None
    errors: list[str] = None
    dispatched: bool = False
    transport_message: Optional[dict[str, Any]] = None
    not_business_completion: bool = True

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def prepare_owner_handoff(
    *,
    envelope: TaskEnvelope,
    task_unit: TaskUnit,
    snapshot: RuntimeEligibilitySnapshot,
    store: DurableStateStore,
    policy: StructuredTaskControllerPolicy,
) -> OwnerHandoffPreparationResult:
    if not policy.controller_enabled:
        return OwnerHandoffPreparationResult(False, errors=["STRUCTURED_TASK_CONTROLLER_DISABLED"])

    errors: list[str] = []
    envelope_validation = validate_task_envelope(envelope)
    unit_validation = validate_task_unit(task_unit)
    errors.extend(envelope_validation.errors)
    errors.extend(unit_validation.errors)
    route = filter_route_candidates(
        task_unit=task_unit,
        snapshot=snapshot,
        required_capability=envelope.required_capabilities[0] if envelope.required_capabilities else "",
        required_authority_scope="implementation",
    )
    errors.extend(route.errors)
    if errors:
        return OwnerHandoffPreparationResult(False, errors=_dedupe(errors))

    audit = write_structured_task_record(
        store,
        family="structured_task.audit",
        status="validation_passed",
        workflow_instance_id=envelope.run_id,
        dedupe_key=f"{envelope.run_id}:{envelope.source_hash}:{envelope.policy_hash}:audit",
        payload={
            "run_id": envelope.run_id,
            "task_id": task_unit.task_id,
            "source_refs": list(envelope.source_refs),
            "source_hash": envelope.source_hash,
            "policy_hash": envelope.policy_hash,
            "selected_owner_id": route.selected_owner_id,
            "validation_result": "passed",
        },
    )
    seed = "|".join([envelope.run_id, task_unit.task_id, route.selected_owner_id or "", audit.record_id])
    digest = sha256(seed.encode("utf-8")).hexdigest()[:16]
    packet = OwnerHandoffPacket(
        packet_id=f"packet-{digest}",
        target_owner=route.selected_owner_id or task_unit.owner,
        task_unit_ref=task_unit.task_id,
        required_context=list(envelope.source_refs),
        exact_input_docs=list(task_unit.source_refs),
        owner_local_paths=list(task_unit.allowed_write_surfaces),
        no_go_boundaries=list(task_unit.no_go_scope),
        expected_deliverables=list(task_unit.dod),
        validation_commands_or_evidence=list(task_unit.evidence_requirements),
        due_or_timeout="manual-review",
        reply_format="result_candidate",
        stop_escalation_path=";".join(task_unit.escalation_conditions),
        audit_ref=audit.record_id,
    )
    packet_validation = validate_owner_handoff_packet(packet)
    if not packet_validation.ok:
        return OwnerHandoffPreparationResult(False, errors=packet_validation.errors)

    write_structured_task_record(
        store,
        family="structured_task.packet",
        status="rendered",
        workflow_instance_id=envelope.run_id,
        target_ref=packet.target_owner,
        related_record_id=audit.record_id,
        dedupe_key=f"{packet.packet_id}:{task_unit.task_id}:{packet.target_owner}",
        payload=packet.to_dict(),
    )
    return OwnerHandoffPreparationResult(
        True,
        packet=packet,
        dispatched=False,
        transport_message=None,
    )


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
