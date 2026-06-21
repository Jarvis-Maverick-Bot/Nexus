"""Engineering Delivery Core Slice 001/002/003/004 contract records and validators.

This module is intentionally contract-only. It defines deterministic records and
fail-closed validators for Layer 1 publication, DeliveryPacket intake, and
delivery-team roster eligibility, plus Layer 2 WorkItem planning and advisory
dispatch recommendations, plus Layer 3 evidence envelope transport-state
contracts. It does not execute work, transport evidence, decide gates, issue
receipts, or start any live process.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from hashlib import sha256
import json
import re
from typing import Any


ACCEPTED_EDC_ISSUE_IDS = {
    "EDC-ISSUE-01",
    "EDC-ISSUE-02",
    "EDC-ISSUE-03",
    "EDC-ISSUE-04",
    "EDC-ISSUE-05",
    "EDC-ISSUE-06",
    "EDC-ISSUE-07",
}
PUBLICATION_STATUSES = {"draft", "blocked", "published", "withdrawn"}
PUBLICATION_TRANSITIONS = {
    "draft": {"blocked", "published"},
    "blocked": {"draft", "withdrawn"},
    "published": {"withdrawn"},
    "withdrawn": set(),
}
DELIVERY_PACKET_STATUSES = {"candidate", "bounded", "ready_for_roster", "blocked", "deferred", "withdrawn"}
DELIVERY_PACKET_TRANSITIONS = {
    "candidate": {"bounded", "blocked", "deferred", "withdrawn"},
    "bounded": {"ready_for_roster", "blocked", "deferred", "withdrawn"},
    "ready_for_roster": {"blocked", "deferred", "withdrawn"},
    "blocked": {"bounded", "deferred", "withdrawn"},
    "deferred": {"bounded", "blocked", "withdrawn"},
    "withdrawn": set(),
}
ROSTER_STATES = {"registered_active", "registered_passive", "unavailable", "suspended", "unregistered"}
ROSTER_SNAPSHOT_STATES = {"captured", "stale", "superseded", "invalid"}
ROSTER_STATE_TRANSITIONS = {
    "unregistered": {"registered_passive"},
    "registered_passive": {"registered_active", "suspended"},
    "registered_active": {"unavailable", "suspended"},
    "unavailable": {"registered_active", "suspended"},
    "suspended": {"registered_passive"},
}
WORK_ITEM_STATES = {"proposed", "ready_for_dispatch", "dispatch_blocked", "dispatch_deferred", "cancelled"}
DISPATCH_RECOMMENDATION_STATES = {"dispatchable", "blocked", "deferred", "cancelled"}
EVIDENCE_EVENT_TYPES = {
    "dispatch_received",
    "work_started",
    "progress_checkpoint",
    "evidence_available",
    "business_blocked",
    "business_deferred",
    "retry_scheduled",
    "transport_timeout",
    "transport_failed",
    "work_returned",
}
EVIDENCE_TRANSPORT_STATUSES = {
    "created",
    "acknowledged",
    "retrying",
    "timed_out",
    "failed",
    "superseded",
    "cancelled",
    "evidence_available",
}
EVIDENCE_BUSINESS_STATUSES = {"not_started", "in_progress", "blocked", "deferred", "returned"}
EVIDENCE_TRANSPORT_TRANSITIONS = {
    "created": {"acknowledged", "timed_out", "failed", "cancelled"},
    "acknowledged": {"evidence_available", "retrying", "timed_out", "failed", "superseded", "cancelled"},
    "retrying": {"acknowledged", "timed_out", "failed", "cancelled"},
    "timed_out": {"retrying", "failed", "cancelled", "superseded"},
    "failed": {"retrying", "superseded", "cancelled"},
    "evidence_available": {"superseded", "cancelled"},
    "superseded": set(),
    "cancelled": set(),
}
LAYER1_AUTHORITY_PREFIXES = ("nova", "alex", "layer1", "layer-1", "l1")
SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-fA-F]{64}$")


@dataclass
class EDCContractValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    explanations: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceAuthorityRef:
    authority_id: str
    source_type: str
    source_uri: str
    source_sha256: str
    authority_actor: str
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceExpectation:
    expectation_id: str
    required_artifacts: list[str]
    validation_refs: list[str]
    reviewer: str
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TraceabilityRef:
    issue_ids: list[str]
    prd_ids: list[str]
    spec_ids: list[str]
    ux_surface_ids: list[str]
    test_case_ids: list[str]
    future_evidence_ids: list[str]
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BlockerEvidence:
    reason_code: str
    human_readable_reason: str
    evidence_refs: list[str]
    recommended_action: str = ""
    revisit_condition: str | None = None
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Layer1TaskPublication:
    publication_id: str
    title: str
    owner: str
    source_authority: SourceAuthorityRef | None
    issue_ids: list[str]
    evidence_expectation: EvidenceExpectation | None
    no_go_boundaries: list[str]
    status: str
    authority_actor: str
    authority_timestamp: str
    traceability: TraceabilityRef
    blocker_evidence: BlockerEvidence | None = None
    supersedes_publication_id: str = ""
    bound_delivery_packet_ids: list[str] = field(default_factory=list)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def contract_fields(self) -> dict[str, Any]:
        data = self.to_dict()
        data.pop("bound_delivery_packet_ids", None)
        return data


@dataclass
class RoadmapBacklogItem:
    item_id: str
    source_publication_id: str
    title: str
    desired_outcomes: list[str]
    source_refs: list[str]
    owner: str
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeliveryPacket:
    packet_id: str
    source_publication_id: str
    roadmap_item_id: str
    objectives: list[str]
    exclusions: list[str]
    evidence_expectation: EvidenceExpectation | None
    no_go_boundaries: list[str]
    status: str
    traceability: TraceabilityRef
    blocker_evidence: BlockerEvidence | None = None
    supersedes_packet_id: str = ""
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def scope_fields(self) -> dict[str, Any]:
        return {
            "source_publication_id": self.source_publication_id,
            "roadmap_item_id": self.roadmap_item_id,
            "objectives": list(self.objectives),
            "exclusions": list(self.exclusions),
            "no_go_boundaries": list(self.no_go_boundaries),
        }

    def contract_fields(self) -> dict[str, Any]:
        return self.to_dict()


@dataclass
class RosterMember:
    agent_id: str
    display_name: str
    registration_state: str
    capability_tags: list[str]
    authority_boundary: list[str]
    source_authority_ref: SourceAuthorityRef | None
    state_reason: str
    state_changed_by: str
    state_changed_at_utc: str
    execution_mode: str = ""
    adapter_type: str = ""
    runtime_capabilities: list[str] = field(default_factory=list)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RosterSnapshot:
    roster_snapshot_id: str
    delivery_packet_id: str
    captured_at_utc: str
    source_registry_ref: SourceAuthorityRef | None
    agent_registrations: list[RosterMember]
    eligibility_policy_version: str
    snapshot_state: str
    supersedes_snapshot_id: str = ""
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def snapshot_hash(self) -> str:
        return stable_contract_hash(self.to_dict())


@dataclass
class RosterEligibilityRequirement:
    requirement_id: str
    delivery_packet_id: str
    required_capability_tags: list[str]
    authority_boundary: list[str]
    no_go_boundaries: list[str]
    traceability: TraceabilityRef
    required_snapshot_state: str = "captured"
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RosterEligibilityDecision:
    decision_id: str
    agent_id: str
    eligible: bool
    roster_snapshot_id: str
    roster_snapshot_hash: str
    matched_capabilities: list[str]
    matched_authority_boundary: list[str]
    exclusion_reasons: list[str]
    evidence_refs: list[str]
    advisory_only: bool = True
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RosterStateTransition:
    agent_id: str
    from_state: str
    to_state: str
    authority_actor: str
    authority_timestamp: str
    evidence_refs: list[str]
    reason: str
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkItem:
    work_item_id: str
    delivery_packet_id: str
    source_publication_id: str
    work_title: str
    work_scope: str
    required_capabilities: list[str]
    authority_boundary: list[str]
    inherited_no_go_control_ids: list[str]
    output_contract: list[str]
    evidence_contract: list[str]
    evidence_expectation_id: str
    state: str
    correlation_root_id: str
    traceability: TraceabilityRef
    source_issue_ids: list[str]
    decomposition_reason: str
    requirement_ids: list[str]
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def work_item_hash(self) -> str:
        return stable_contract_hash(self.to_dict())


@dataclass
class WorkItemDecompositionPlan:
    decomposition_plan_id: str
    delivery_packet_id: str
    work_items: list[WorkItem]
    decomposed_by: str
    decomposed_at_utc: str
    decomposition_order: list[str]
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DispatchRecommendation:
    dispatch_decision_id: str
    work_item_id: str
    roster_snapshot_id: str
    eligible_agent_ids: list[str]
    selected_agent_id: str | None
    decision_state: str
    eligibility_checks: list[dict[str, Any]]
    blocked_reason: str
    deferred_reason: str
    decided_by: str
    decided_at_utc: str
    roster_snapshot_hash: str
    work_item_hash: str
    selected_agent_reason: str = ""
    external_revisit_condition: str = ""
    advisory_only: bool = True
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceReference:
    evidence_ref_id: str
    artifact_uri: str
    content_sha256: str
    producer: str
    produced_at_utc: str
    source_work_item_id: str
    actual_content_sha256: str = ""
    inclusion_state: str = "candidate"
    exclusion_reason: str = ""
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceEnvelope:
    envelope_id: str
    correlation_root_id: str
    delivery_packet_id: str
    work_item_id: str
    dispatch_decision_id: str
    agent_id: str
    event_type: str
    sequence_number: int
    idempotency_key: str
    evidence_refs: list[EvidenceReference]
    transport_status: str
    business_status: str
    created_at_utc: str
    traceability: TraceabilityRef | None
    attempt_number: int = 1
    evidence_package_complete: bool = False
    replay_of_envelope_id: str = ""
    supersedes_envelope_id: str = ""
    superseded_by_envelope_id: str = ""
    creates_gate_decision: bool = False
    creates_delivery_receipt: bool = False
    not_delivery_truth: bool = True
    not_gate_decision: bool = True
    not_delivery_receipt: bool = True
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def envelope_hash(self) -> str:
        return stable_contract_hash(self.to_dict())


@dataclass
class EvidenceTransportState:
    transport_state_id: str
    envelope_id: str
    work_item_id: str
    dispatch_decision_id: str
    correlation_root_id: str
    idempotency_key: str
    sequence_number: int
    status: str
    event_type: str
    attempt_number: int
    observed_at_utc: str
    prior_state: str = ""
    prior_envelope_id: str = ""
    timeout_class: str = ""
    failure_reason: str = ""
    retry_after_utc: str = ""
    evidence_package_complete: bool = False
    gate_state: str = "pending"
    receipt_state: str = "pending_gate"
    gate_decision_created: bool = False
    delivery_receipt_created: bool = False
    transport_failure_is_gate_blocker: bool = False
    not_delivery_truth: bool = True
    not_gate_decision: bool = True
    not_delivery_receipt: bool = True
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_publication(value: Layer1TaskPublication) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(value.publication_id, "MISSING_PUBLICATION_ID"))
    errors.extend(_missing_scalar(value.title, "MISSING_PUBLICATION_TITLE"))
    errors.extend(_missing_scalar(value.owner, "MISSING_PUBLICATION_OWNER"))
    errors.extend(_validate_source_authority(value.source_authority))
    errors.extend(_validate_accepted_issue_ids(value.issue_ids))
    errors.extend(_validate_evidence_expectation(value.evidence_expectation))
    errors.extend(_missing_list(value.no_go_boundaries, "MISSING_NO_GO_BOUNDARIES"))
    errors.extend(_validate_traceability(value.traceability))
    if value.status not in PUBLICATION_STATUSES:
        errors.append("INVALID_PUBLICATION_STATUS")
    if value.status == "blocked":
        errors.extend(_validate_blocker(value.blocker_evidence, "PUBLICATION"))
    return _result(errors)


def validate_publication_transition(
    publication: Layer1TaskPublication,
    *,
    target_status: str,
    authority_actor: str,
    authority_timestamp: str = "",
    blocker_evidence: BlockerEvidence | None = None,
) -> EDCContractValidationResult:
    errors: list[str] = []
    explanations: dict[str, Any] = {}
    errors.extend(
        _validate_transition(
            current_status=publication.status,
            target_status=target_status,
            valid_statuses=PUBLICATION_STATUSES,
            transition_table=PUBLICATION_TRANSITIONS,
            invalid_current_code="INVALID_PUBLICATION_STATUS",
            invalid_target_code="INVALID_PUBLICATION_TARGET_STATUS",
            invalid_transition_code="INVALID_PUBLICATION_TRANSITION",
        )
    )
    if not _is_layer1_authority(authority_actor):
        errors.append("ACTOR_NOT_LAYER1_AUTHORITY")
    if target_status == "published":
        errors.extend(_missing_scalar(authority_timestamp, "MISSING_AUTHORITY_TIMESTAMP"))
        errors.extend(validate_publication(publication).errors)
    if target_status == "blocked":
        errors.extend(_validate_blocker(blocker_evidence, "PUBLICATION"))
        if blocker_evidence:
            explanations.update(_blocker_explanation(blocker_evidence))
    if target_status == "withdrawn":
        errors.extend(_missing_scalar(authority_timestamp, "MISSING_AUTHORITY_TIMESTAMP"))
    return _result(errors, explanations=explanations)


def explain_publication_block(publication: Layer1TaskPublication) -> dict[str, Any]:
    if publication.status != "blocked" or not publication.blocker_evidence:
        return {
            "reason_code": "PUBLICATION_NOT_BLOCKED",
            "human_readable_reason": "Publication is not in blocked state.",
            "evidence_refs": [],
        }
    return _blocker_explanation(publication.blocker_evidence)


def validate_publication_supersession(
    original: Layer1TaskPublication,
    candidate: Layer1TaskPublication,
) -> EDCContractValidationResult:
    if not original.bound_delivery_packet_ids:
        return _result([])
    if stable_contract_hash(original.contract_fields()) == stable_contract_hash(candidate.contract_fields()):
        return _result([])
    if candidate.supersedes_publication_id == original.publication_id:
        return _result([])
    return _result(["PUBLICATION_BOUND_REQUIRES_SUPERSESSION"])


def validate_roadmap_backlog_item(value: RoadmapBacklogItem) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(value.item_id, "MISSING_ROADMAP_ITEM_ID"))
    errors.extend(_missing_scalar(value.source_publication_id, "MISSING_SOURCE_PUBLICATION_ID"))
    errors.extend(_missing_scalar(value.title, "MISSING_ROADMAP_TITLE"))
    errors.extend(_missing_scalar(value.owner, "MISSING_ROADMAP_OWNER"))
    errors.extend(_missing_list(value.desired_outcomes, "MISSING_ROADMAP_OUTCOMES"))
    errors.extend(_missing_list(value.source_refs, "MISSING_ROADMAP_SOURCE_REFS"))
    return _result(errors)


def validate_delivery_packet(
    packet: DeliveryPacket,
    *,
    source_publication: Layer1TaskPublication,
    roadmap_item: RoadmapBacklogItem,
) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(packet.packet_id, "MISSING_PACKET_ID"))
    errors.extend(_missing_scalar(packet.source_publication_id, "MISSING_SOURCE_PUBLICATION_ID"))
    errors.extend(_missing_scalar(packet.roadmap_item_id, "MISSING_ROADMAP_ITEM_ID"))
    errors.extend(_validate_traceability(packet.traceability))
    if packet.status not in DELIVERY_PACKET_STATUSES:
        errors.append("INVALID_DELIVERY_PACKET_STATUS")
    if source_publication.status == "withdrawn":
        errors.append("SOURCE_PUBLICATION_WITHDRAWN")
    elif source_publication.status != "published":
        errors.append("SOURCE_PUBLICATION_NOT_PUBLISHED")
    if packet.source_publication_id != source_publication.publication_id:
        errors.append("SOURCE_PUBLICATION_ID_MISMATCH")
    roadmap_errors = validate_roadmap_backlog_item(roadmap_item).errors
    errors.extend(roadmap_errors)
    if roadmap_item.item_id and packet.roadmap_item_id and packet.roadmap_item_id != roadmap_item.item_id:
        errors.append("ROADMAP_ITEM_ID_MISMATCH")
    errors.extend(_validate_single_objective(packet.objectives))
    if packet.status != "blocked":
        errors.extend(_missing_list(packet.exclusions, "MISSING_PACKET_EXCLUSIONS"))
    errors.extend(_validate_evidence_expectation(packet.evidence_expectation))
    errors.extend(_validate_evidence_inheritance(packet, source_publication))
    errors.extend(_validate_no_go_inheritance(packet.no_go_boundaries, source_publication.no_go_boundaries))
    if packet.status in {"blocked", "deferred"}:
        errors.extend(_validate_blocker(packet.blocker_evidence, "PACKET"))
    if packet.status == "deferred" and packet.blocker_evidence and not packet.blocker_evidence.revisit_condition:
        errors.append("DEFERRED_PACKET_REQUIRES_REVISIT_CONDITION")
    return _result(errors)


def validate_delivery_packet_transition(
    packet: DeliveryPacket,
    *,
    target_status: str,
    source_publication: Layer1TaskPublication,
    roadmap_item: RoadmapBacklogItem,
    blocker_evidence: BlockerEvidence | None = None,
) -> EDCContractValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    explanations: dict[str, Any] = {}
    errors.extend(
        _validate_transition(
            current_status=packet.status,
            target_status=target_status,
            valid_statuses=DELIVERY_PACKET_STATUSES,
            transition_table=DELIVERY_PACKET_TRANSITIONS,
            invalid_current_code="INVALID_DELIVERY_PACKET_STATUS",
            invalid_target_code="INVALID_DELIVERY_PACKET_TARGET_STATUS",
            invalid_transition_code="INVALID_DELIVERY_PACKET_TRANSITION",
        )
    )
    packet_errors = validate_delivery_packet(packet, source_publication=source_publication, roadmap_item=roadmap_item).errors
    if target_status in {"bounded", "ready_for_roster"}:
        errors.extend(packet_errors)
        explanations["scope_hash"] = stable_contract_hash(packet.scope_fields())
    if target_status == "ready_for_roster":
        if packet.status != "bounded":
            errors.append("PACKET_MUST_BE_BOUNDED_BEFORE_ROSTER")
        warnings.append("ROSTER_BASELINE_REQUIRED_BEFORE_DISPATCH")
    if target_status == "blocked":
        errors.extend(_validate_blocker(blocker_evidence or packet.blocker_evidence, "PACKET"))
    if target_status == "deferred":
        selected_blocker = blocker_evidence or packet.blocker_evidence
        errors.extend(_validate_blocker(selected_blocker, "PACKET"))
        if selected_blocker and not selected_blocker.revisit_condition:
            errors.append("DEFERRED_PACKET_REQUIRES_REVISIT_CONDITION")
    return _result(errors, warnings=warnings, explanations=explanations)


def explain_delivery_packet_block(packet: DeliveryPacket) -> dict[str, Any]:
    if packet.status != "blocked" or not packet.blocker_evidence:
        return {
            "reason_code": "PACKET_NOT_BLOCKED",
            "human_readable_reason": "DeliveryPacket is not in blocked state.",
            "evidence_refs": [],
        }
    return _blocker_explanation(packet.blocker_evidence)


def validate_delivery_packet_supersession(
    original: DeliveryPacket,
    candidate: DeliveryPacket,
) -> EDCContractValidationResult:
    if stable_contract_hash(original.contract_fields()) == stable_contract_hash(candidate.contract_fields()):
        return _result([])
    if candidate.supersedes_packet_id == original.packet_id:
        return _result([])
    return _result(["PACKET_HASH_CHANGED_WITHOUT_SUPERSESSION"])


def validate_roster_member(member: RosterMember) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(member.agent_id, "MISSING_ROSTER_AGENT_ID"))
    errors.extend(_missing_scalar(member.display_name, "MISSING_ROSTER_DISPLAY_NAME"))
    errors.extend(_validate_source_authority(member.source_authority_ref))
    errors.extend(_missing_scalar(member.state_reason, "MISSING_ROSTER_STATE_REASON"))
    errors.extend(_missing_scalar(member.state_changed_by, "MISSING_ROSTER_STATE_CHANGED_BY"))
    errors.extend(_missing_scalar(member.state_changed_at_utc, "MISSING_ROSTER_STATE_CHANGED_AT"))
    if member.registration_state not in ROSTER_STATES:
        errors.append("INVALID_ROSTER_STATE")
    if member.registration_state != "unregistered":
        errors.extend(_missing_list(member.capability_tags, "MISSING_ROSTER_CAPABILITY_TAGS"))
    if member.registration_state == "registered_active":
        errors.extend(_missing_list(member.authority_boundary, "MISSING_ROSTER_AUTHORITY_BOUNDARY"))
    return _result(errors)


def validate_roster_snapshot(snapshot: RosterSnapshot) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(snapshot.roster_snapshot_id, "MISSING_ROSTER_SNAPSHOT_ID"))
    errors.extend(_missing_scalar(snapshot.delivery_packet_id, "MISSING_ROSTER_DELIVERY_PACKET_ID"))
    errors.extend(_missing_scalar(snapshot.captured_at_utc, "MISSING_ROSTER_CAPTURED_AT"))
    errors.extend(_validate_source_authority(snapshot.source_registry_ref))
    errors.extend(_missing_list(snapshot.agent_registrations, "MISSING_ROSTER_AGENT_REGISTRATIONS"))
    errors.extend(_missing_scalar(snapshot.eligibility_policy_version, "MISSING_ROSTER_POLICY_VERSION"))
    if snapshot.snapshot_state not in ROSTER_SNAPSHOT_STATES:
        errors.append("INVALID_ROSTER_SNAPSHOT_STATE")
    for member in snapshot.agent_registrations:
        errors.extend(validate_roster_member(member).errors)
    return _result(errors)


def validate_roster_eligibility_requirement(requirement: RosterEligibilityRequirement) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(requirement.requirement_id, "MISSING_ROSTER_REQUIREMENT_ID"))
    errors.extend(_missing_scalar(requirement.delivery_packet_id, "MISSING_ROSTER_REQUIREMENT_PACKET_ID"))
    errors.extend(_missing_list(requirement.required_capability_tags, "MISSING_REQUIRED_CAPABILITY_TAGS"))
    errors.extend(_missing_list(requirement.authority_boundary, "MISSING_REQUIRED_AUTHORITY_BOUNDARY"))
    errors.extend(_missing_list(requirement.no_go_boundaries, "MISSING_ROSTER_NO_GO_BOUNDARIES"))
    errors.extend(_validate_traceability(requirement.traceability))
    if requirement.required_snapshot_state != "captured":
        errors.append("INVALID_REQUIRED_ROSTER_SNAPSHOT_STATE")
    return _result(errors)


def validate_roster_state_transition(transition: RosterStateTransition) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(transition.agent_id, "MISSING_ROSTER_TRANSITION_AGENT_ID"))
    errors.extend(_missing_scalar(transition.authority_actor, "MISSING_ROSTER_TRANSITION_AUTHORITY"))
    errors.extend(_missing_scalar(transition.authority_timestamp, "MISSING_ROSTER_TRANSITION_TIMESTAMP"))
    errors.extend(_missing_scalar(transition.reason, "MISSING_ROSTER_TRANSITION_REASON"))
    errors.extend(_missing_list(transition.evidence_refs, "MISSING_ROSTER_TRANSITION_EVIDENCE"))
    errors.extend(
        _validate_transition(
            current_status=transition.from_state,
            target_status=transition.to_state,
            valid_statuses=ROSTER_STATES,
            transition_table=ROSTER_STATE_TRANSITIONS,
            invalid_current_code="INVALID_ROSTER_FROM_STATE",
            invalid_target_code="INVALID_ROSTER_TO_STATE",
            invalid_transition_code="INVALID_ROSTER_STATE_TRANSITION",
        )
    )
    return _result(errors)


def evaluate_roster_eligibility(
    snapshot: RosterSnapshot | None,
    requirement: RosterEligibilityRequirement,
) -> EDCContractValidationResult:
    errors: list[str] = []
    explanations: dict[str, Any] = {
        "eligible_agent_ids": [],
        "decisions": [],
        "advisory_only": True,
    }
    errors.extend(validate_roster_eligibility_requirement(requirement).errors)
    if snapshot is None:
        errors.append("MISSING_ROSTER_SNAPSHOT")
        errors.append("NO_ELIGIBLE_AGENT")
        return _result(errors, explanations=explanations)

    errors.extend(validate_roster_snapshot(snapshot).errors)
    snapshot_hash = snapshot.snapshot_hash()
    explanations["roster_snapshot_hash"] = snapshot_hash
    if snapshot.delivery_packet_id and requirement.delivery_packet_id and snapshot.delivery_packet_id != requirement.delivery_packet_id:
        errors.append("ROSTER_REQUIREMENT_PACKET_MISMATCH")
    if snapshot.snapshot_state != requirement.required_snapshot_state:
        errors.append("ROSTER_SNAPSHOT_NOT_CURRENT")
        errors.append("NO_ELIGIBLE_AGENT")
        return _result(errors, explanations=explanations)

    for member in snapshot.agent_registrations:
        decision = _evaluate_roster_member(snapshot, snapshot_hash, member, requirement)
        explanations["decisions"].append(decision.to_dict())
        if decision.eligible:
            explanations["eligible_agent_ids"].append(decision.agent_id)
    if not explanations["eligible_agent_ids"]:
        errors.append("NO_ELIGIBLE_AGENT")
    return _result(errors, explanations=explanations)


def validate_roster_eligibility_decision(
    decision: RosterEligibilityDecision,
    snapshot: RosterSnapshot,
) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(decision.decision_id, "MISSING_ROSTER_DECISION_ID"))
    errors.extend(_missing_scalar(decision.agent_id, "MISSING_ROSTER_DECISION_AGENT_ID"))
    errors.extend(_missing_scalar(decision.roster_snapshot_id, "MISSING_ROSTER_DECISION_SNAPSHOT_ID"))
    errors.extend(_missing_scalar(decision.roster_snapshot_hash, "MISSING_ROSTER_DECISION_SNAPSHOT_HASH"))
    errors.extend(_missing_list(decision.evidence_refs, "MISSING_ROSTER_DECISION_EVIDENCE"))
    if decision.roster_snapshot_id != snapshot.roster_snapshot_id:
        errors.append("ROSTER_DECISION_SNAPSHOT_ID_MISMATCH")
    if decision.roster_snapshot_hash != snapshot.snapshot_hash():
        errors.append("ROSTER_SNAPSHOT_HASH_MISMATCH")
    if decision.eligible and decision.exclusion_reasons:
        errors.append("ELIGIBLE_ROSTER_DECISION_HAS_EXCLUSIONS")
    if not decision.eligible and not decision.exclusion_reasons:
        errors.append("INELIGIBLE_ROSTER_DECISION_REQUIRES_REASON")
    if decision.advisory_only is not True:
        errors.append("ROSTER_DECISION_MUST_REMAIN_ADVISORY")
    return _result(errors)


def explain_no_eligible_agent(
    snapshot: RosterSnapshot | None,
    requirement: RosterEligibilityRequirement,
) -> dict[str, Any]:
    result = evaluate_roster_eligibility(snapshot, requirement)
    decisions = result.explanations.get("decisions", [])
    roster_state_reasons = {
        "AGENT_PLANNING_VISIBLE_ONLY",
        "AGENT_UNAVAILABLE",
        "AGENT_SUSPENDED",
        "AGENT_UNREGISTERED",
    }
    return {
        "reason_code": "NO_ELIGIBLE_AGENT" if not result.explanations.get("eligible_agent_ids") else "ELIGIBLE_AGENT_AVAILABLE",
        "human_readable_reason": "No registered_active agent satisfied roster state, capability, and authority requirements.",
        "eligible_agent_ids": list(result.explanations.get("eligible_agent_ids", [])),
        "roster_state_gaps": _decision_reasons(decisions, roster_state_reasons),
        "capability_gaps": _decision_reasons(decisions, {"MISSING_REQUIRED_CAPABILITY"}),
        "authority_gaps": _decision_reasons(decisions, {"AUTHORITY_BOUNDARY_MISMATCH"}),
        "evidence_refs": _collect_decision_evidence(decisions),
        "advisory_only": True,
    }


def validate_work_item(
    work_item: WorkItem,
    *,
    parent_packet: DeliveryPacket | None,
) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(work_item.work_item_id, "MISSING_WORK_ITEM_ID"))
    errors.extend(_missing_scalar(work_item.delivery_packet_id, "MISSING_WORK_ITEM_PARENT_PACKET_ID"))
    errors.extend(_missing_scalar(work_item.source_publication_id, "MISSING_WORK_ITEM_SOURCE_PUBLICATION_ID"))
    errors.extend(_missing_scalar(work_item.work_title, "MISSING_WORK_ITEM_TITLE"))
    errors.extend(_missing_scalar(work_item.work_scope, "MISSING_WORK_ITEM_SCOPE"))
    errors.extend(_missing_list(work_item.required_capabilities, "MISSING_WORK_ITEM_REQUIRED_CAPABILITIES"))
    errors.extend(_missing_list(work_item.authority_boundary, "MISSING_WORK_ITEM_AUTHORITY_BOUNDARY"))
    errors.extend(_missing_list(work_item.inherited_no_go_control_ids, "MISSING_WORK_ITEM_NO_GO_CONTROLS"))
    errors.extend(_missing_list(work_item.output_contract, "MISSING_WORK_ITEM_OUTPUT_CONTRACT"))
    errors.extend(_missing_list(work_item.evidence_contract, "MISSING_WORK_ITEM_EVIDENCE_CONTRACT"))
    errors.extend(_missing_scalar(work_item.evidence_expectation_id, "MISSING_WORK_ITEM_EVIDENCE_EXPECTATION_ID"))
    errors.extend(_missing_scalar(work_item.correlation_root_id, "MISSING_WORK_ITEM_CORRELATION_ROOT"))
    errors.extend(_missing_scalar(work_item.decomposition_reason, "MISSING_WORK_ITEM_DECOMPOSITION_REASON"))
    errors.extend(_missing_list(work_item.requirement_ids, "MISSING_WORK_ITEM_REQUIREMENT_IDS"))
    errors.extend(_validate_traceability(work_item.traceability))
    errors.extend(_validate_accepted_issue_ids(work_item.source_issue_ids))
    if work_item.state not in WORK_ITEM_STATES:
        errors.append("INVALID_WORK_ITEM_STATE")
    if parent_packet is None:
        errors.append("MISSING_PARENT_DELIVERY_PACKET")
        return _result(errors)
    if work_item.delivery_packet_id and work_item.delivery_packet_id != parent_packet.packet_id:
        errors.append("WORK_ITEM_PARENT_PACKET_ID_MISMATCH")
    if work_item.source_publication_id and work_item.source_publication_id != parent_packet.source_publication_id:
        errors.append("WORK_ITEM_SOURCE_AUTHORITY_NOT_INHERITED")
    if work_item.correlation_root_id and work_item.correlation_root_id != parent_packet.packet_id:
        errors.append("WORK_ITEM_CORRELATION_ROOT_NOT_INHERITED")
    if work_item.evidence_expectation_id and parent_packet.evidence_expectation:
        if work_item.evidence_expectation_id != parent_packet.evidence_expectation.expectation_id:
            errors.append("WORK_ITEM_EVIDENCE_EXPECTATION_NOT_INHERITED")
    missing_no_go = [
        control_id for control_id in parent_packet.no_go_boundaries if control_id not in work_item.inherited_no_go_control_ids
    ]
    if missing_no_go:
        errors.append("WORK_ITEM_NO_GO_BOUNDARY_NOT_INHERITED")
    if any(issue_id not in parent_packet.traceability.issue_ids for issue_id in work_item.source_issue_ids):
        errors.append("WORK_ITEM_SOURCE_ISSUE_NOT_INHERITED")
    if any(issue_id not in parent_packet.traceability.issue_ids for issue_id in work_item.traceability.issue_ids):
        errors.append("WORK_ITEM_TRACEABILITY_NOT_INHERITED")
    return _result(errors)


def validate_work_item_decomposition(
    plan: WorkItemDecompositionPlan,
    *,
    parent_packet: DeliveryPacket | None,
) -> EDCContractValidationResult:
    errors: list[str] = []
    explanations: dict[str, Any] = {"ordering": list(plan.decomposition_order)}
    errors.extend(_missing_scalar(plan.decomposition_plan_id, "MISSING_DECOMPOSITION_PLAN_ID"))
    errors.extend(_missing_scalar(plan.delivery_packet_id, "MISSING_DECOMPOSITION_PACKET_ID"))
    errors.extend(_missing_scalar(plan.decomposed_by, "MISSING_DECOMPOSITION_ACTOR"))
    errors.extend(_missing_scalar(plan.decomposed_at_utc, "MISSING_DECOMPOSITION_TIMESTAMP"))
    errors.extend(_missing_list(plan.work_items, "MISSING_DECOMPOSITION_WORK_ITEMS"))
    errors.extend(_missing_list(plan.decomposition_order, "MISSING_DECOMPOSITION_ORDER"))
    if parent_packet is None:
        errors.append("MISSING_PARENT_DELIVERY_PACKET")
        return _result(errors, explanations=explanations)
    if plan.delivery_packet_id and plan.delivery_packet_id != parent_packet.packet_id:
        errors.append("DECOMPOSITION_PACKET_ID_MISMATCH")
    if parent_packet.status != "ready_for_roster":
        errors.append("PACKET_NOT_READY_FOR_ROSTER")
    if plan.decomposition_order:
        if plan.decomposition_order[0] != "packet_validation":
            errors.append("PACKET_VALIDATION_MUST_PRECEDE_ROSTER_EVALUATION")
        if "roster_evaluation" in plan.decomposition_order:
            if plan.decomposition_order.index("packet_validation") > plan.decomposition_order.index("roster_evaluation"):
                errors.append("PACKET_VALIDATION_MUST_PRECEDE_ROSTER_EVALUATION")
    for work_item in plan.work_items:
        errors.extend(validate_work_item(work_item, parent_packet=parent_packet).errors)
    return _result(errors, explanations=explanations)


def create_dispatch_recommendation(
    *,
    work_item: WorkItem,
    roster_snapshot: RosterSnapshot,
    eligibility_result: EDCContractValidationResult,
    decided_by: str,
    decided_at_utc: str,
    selected_agent_id: str | None = None,
    selected_agent_reason: str = "",
    external_constraint_reason: str = "",
    external_revisit_condition: str = "",
    advisory_only: bool = True,
) -> DispatchRecommendation:
    eligible_agent_ids = list(eligibility_result.explanations.get("eligible_agent_ids", []))
    effective_selected_agent_id = selected_agent_id
    if effective_selected_agent_id is None and eligible_agent_ids and not external_constraint_reason:
        effective_selected_agent_id = eligible_agent_ids[0]
    if external_constraint_reason:
        decision_state = "deferred"
        blocked_reason = ""
        deferred_reason = external_constraint_reason
        effective_selected_agent_id = None
    elif not eligible_agent_ids and effective_selected_agent_id is None:
        decision_state = "blocked"
        blocked_reason = "NO_ELIGIBLE_AGENT"
        deferred_reason = ""
    else:
        decision_state = "dispatchable"
        blocked_reason = ""
        deferred_reason = ""
    if effective_selected_agent_id and not selected_agent_reason:
        selected_agent_reason = f"{effective_selected_agent_id} is advisory-selected from the eligible roster baseline."
    return DispatchRecommendation(
        dispatch_decision_id=f"dispatch-rec::{work_item.work_item_id}::{roster_snapshot.roster_snapshot_id}",
        work_item_id=work_item.work_item_id,
        roster_snapshot_id=roster_snapshot.roster_snapshot_id,
        eligible_agent_ids=eligible_agent_ids,
        selected_agent_id=effective_selected_agent_id,
        decision_state=decision_state,
        eligibility_checks=list(eligibility_result.explanations.get("decisions", [])),
        blocked_reason=blocked_reason,
        deferred_reason=deferred_reason,
        decided_by=decided_by,
        decided_at_utc=decided_at_utc,
        roster_snapshot_hash=roster_snapshot.snapshot_hash(),
        work_item_hash=work_item.work_item_hash(),
        selected_agent_reason=selected_agent_reason,
        external_revisit_condition=external_revisit_condition,
        advisory_only=advisory_only,
    )


def validate_dispatch_recommendation(
    recommendation: DispatchRecommendation,
    *,
    work_item: WorkItem,
    roster_snapshot: RosterSnapshot,
    eligibility_result: EDCContractValidationResult,
) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(recommendation.dispatch_decision_id, "MISSING_DISPATCH_RECOMMENDATION_ID"))
    errors.extend(_missing_scalar(recommendation.work_item_id, "MISSING_DISPATCH_WORK_ITEM_ID"))
    errors.extend(_missing_scalar(recommendation.roster_snapshot_id, "MISSING_DISPATCH_ROSTER_SNAPSHOT_ID"))
    errors.extend(_missing_scalar(recommendation.decided_by, "MISSING_DISPATCH_DECIDER"))
    errors.extend(_missing_scalar(recommendation.decided_at_utc, "MISSING_DISPATCH_DECIDED_AT"))
    errors.extend(_missing_scalar(recommendation.roster_snapshot_hash, "MISSING_DISPATCH_ROSTER_SNAPSHOT_HASH"))
    errors.extend(_missing_scalar(recommendation.work_item_hash, "MISSING_DISPATCH_WORK_ITEM_HASH"))
    if recommendation.decision_state not in DISPATCH_RECOMMENDATION_STATES:
        errors.append("INVALID_DISPATCH_RECOMMENDATION_STATE")
    if recommendation.advisory_only is not True:
        errors.append("DISPATCH_RECOMMENDATION_MUST_REMAIN_ADVISORY")
    if recommendation.work_item_id != work_item.work_item_id:
        errors.append("DISPATCH_WORK_ITEM_ID_MISMATCH")
    if recommendation.work_item_hash != work_item.work_item_hash():
        errors.append("DISPATCH_WORK_ITEM_HASH_MISMATCH")
    if recommendation.roster_snapshot_id != roster_snapshot.roster_snapshot_id:
        errors.append("DISPATCH_ROSTER_SNAPSHOT_ID_MISMATCH")
    if recommendation.roster_snapshot_hash != roster_snapshot.snapshot_hash():
        errors.append("DISPATCH_ROSTER_SNAPSHOT_HASH_MISMATCH")
    eligible_agent_ids = list(eligibility_result.explanations.get("eligible_agent_ids", []))
    if recommendation.eligible_agent_ids != eligible_agent_ids:
        errors.append("DISPATCH_ELIGIBLE_AGENT_LIST_MISMATCH")
    if recommendation.selected_agent_id:
        if recommendation.selected_agent_id not in eligible_agent_ids:
            errors.append("SELECTED_AGENT_REQUIRES_ELIGIBILITY_PROOF")
        errors.extend(_missing_scalar(recommendation.selected_agent_reason, "MISSING_SELECTED_AGENT_REASON"))
    if not eligible_agent_ids and recommendation.decision_state not in {"blocked", "deferred"}:
        errors.append("NO_ELIGIBLE_AGENT_REQUIRES_BLOCKED_OR_DEFERRED_RECOMMENDATION")
    if recommendation.decision_state == "dispatchable" and not recommendation.selected_agent_id:
        errors.append("DISPATCHABLE_RECOMMENDATION_REQUIRES_SELECTED_AGENT")
    if recommendation.decision_state == "blocked":
        errors.extend(_missing_scalar(recommendation.blocked_reason, "MISSING_BLOCKED_DISPATCH_REASON"))
        if recommendation.selected_agent_id:
            errors.append("BLOCKED_RECOMMENDATION_CANNOT_SELECT_AGENT")
    if recommendation.decision_state == "deferred":
        errors.extend(_missing_scalar(recommendation.deferred_reason, "MISSING_DEFERRED_DISPATCH_REASON"))
        errors.extend(_missing_scalar(recommendation.external_revisit_condition, "MISSING_DEFERRED_DISPATCH_REVISIT_CONDITION"))
        if recommendation.selected_agent_id:
            errors.append("DEFERRED_RECOMMENDATION_CANNOT_SELECT_AGENT")
    return _result(errors)


def explain_dispatch_recommendation(recommendation: DispatchRecommendation) -> dict[str, Any]:
    if recommendation.decision_state == "blocked":
        reason_code = recommendation.blocked_reason or "DISPATCH_RECOMMENDATION_BLOCKED"
    elif recommendation.decision_state == "deferred":
        reason_code = recommendation.deferred_reason or "DISPATCH_RECOMMENDATION_DEFERRED"
    else:
        reason_code = recommendation.decision_state.upper()
    return {
        "reason_code": reason_code,
        "decision_state": recommendation.decision_state,
        "selected_agent_id": recommendation.selected_agent_id,
        "eligible_agent_ids": list(recommendation.eligible_agent_ids),
        "evidence_refs": [
            f"work_item_hash:{recommendation.work_item_hash}",
            f"roster_snapshot_hash:{recommendation.roster_snapshot_hash}",
        ],
        "advisory_only": recommendation.advisory_only,
        "external_revisit_condition": recommendation.external_revisit_condition,
    }


def validate_evidence_reference(
    reference: EvidenceReference,
    *,
    expected_content_sha256: str = "",
    source_work_item_id: str = "",
) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(reference.evidence_ref_id, "MISSING_EVIDENCE_REF_ID"))
    errors.extend(_missing_scalar(reference.artifact_uri, "MISSING_EVIDENCE_ARTIFACT_URI"))
    errors.extend(_missing_scalar(reference.producer, "MISSING_EVIDENCE_PRODUCER"))
    errors.extend(_missing_scalar(reference.produced_at_utc, "MISSING_EVIDENCE_PRODUCED_AT"))
    errors.extend(_missing_scalar(reference.source_work_item_id, "MISSING_EVIDENCE_SOURCE_WORK_ITEM_ID"))
    if not reference.content_sha256:
        errors.append("MISSING_EVIDENCE_CONTENT_HASH")
    elif not SHA256_RE.match(reference.content_sha256):
        errors.append("INVALID_EVIDENCE_CONTENT_HASH")

    observed_hash = expected_content_sha256 or reference.actual_content_sha256
    if reference.content_sha256 and observed_hash:
        if not SHA256_RE.match(observed_hash):
            errors.append("INVALID_OBSERVED_EVIDENCE_CONTENT_HASH")
        elif _normal_sha256(reference.content_sha256) != _normal_sha256(observed_hash):
            errors.append("EVIDENCE_CONTENT_HASH_MISMATCH")

    if source_work_item_id and reference.source_work_item_id and reference.source_work_item_id != source_work_item_id:
        errors.append("EVIDENCE_SOURCE_WORK_ITEM_MISMATCH")

    exclusion_reason = ""
    if "MISSING_EVIDENCE_CONTENT_HASH" in errors:
        exclusion_reason = "missing_content_hash"
    elif "EVIDENCE_CONTENT_HASH_MISMATCH" in errors:
        exclusion_reason = "content_hash_mismatch"
    elif errors:
        exclusion_reason = "invalid_evidence_reference"
    return _result(
        errors,
        explanations={
            "inclusion_state": "excluded" if errors else "included",
            "exclusion_reason": exclusion_reason,
            "evidence_package_complete": not errors,
            "source_work_item_id": reference.source_work_item_id,
        },
    )


def validate_evidence_envelope(
    envelope: EvidenceEnvelope,
    *,
    work_item: WorkItem | None,
    dispatch_recommendation: DispatchRecommendation | None,
    parent_packet: DeliveryPacket | None,
) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(envelope.envelope_id, "MISSING_EVIDENCE_ENVELOPE_ID"))
    errors.extend(_missing_scalar(envelope.correlation_root_id, "MISSING_EVIDENCE_CORRELATION_ROOT_ID"))
    errors.extend(_missing_scalar(envelope.delivery_packet_id, "MISSING_EVIDENCE_PARENT_PACKET_ID"))
    errors.extend(_missing_scalar(envelope.work_item_id, "MISSING_EVIDENCE_PARENT_WORK_ITEM_ID"))
    errors.extend(_missing_scalar(envelope.dispatch_decision_id, "MISSING_EVIDENCE_DISPATCH_RECOMMENDATION_ID"))
    errors.extend(_missing_scalar(envelope.agent_id, "MISSING_EVIDENCE_AGENT_ID"))
    errors.extend(_missing_scalar(envelope.idempotency_key, "MISSING_EVIDENCE_IDEMPOTENCY_KEY"))
    errors.extend(_missing_scalar(envelope.created_at_utc, "MISSING_EVIDENCE_CREATED_AT"))
    errors.extend(_missing_list(envelope.evidence_refs, "MISSING_EVIDENCE_REFS"))
    if envelope.event_type not in EVIDENCE_EVENT_TYPES:
        errors.append("INVALID_EVIDENCE_EVENT_TYPE")
    if envelope.transport_status not in EVIDENCE_TRANSPORT_STATUSES:
        errors.append("INVALID_EVIDENCE_TRANSPORT_STATUS")
    if envelope.business_status not in EVIDENCE_BUSINESS_STATUSES:
        errors.append("INVALID_EVIDENCE_BUSINESS_STATUS")
    if envelope.sequence_number < 1:
        errors.append("INVALID_EVIDENCE_SEQUENCE_NUMBER")
    if envelope.attempt_number < 1:
        errors.append("INVALID_EVIDENCE_ATTEMPT_NUMBER")

    if parent_packet is None:
        errors.append("MISSING_PARENT_DELIVERY_PACKET")
    elif envelope.delivery_packet_id and envelope.delivery_packet_id != parent_packet.packet_id:
        errors.append("EVIDENCE_PARENT_PACKET_ID_MISMATCH")

    if work_item is None:
        errors.append("MISSING_PARENT_WORK_ITEM")
    else:
        if envelope.work_item_id and envelope.work_item_id != work_item.work_item_id:
            errors.append("EVIDENCE_WORK_ITEM_ID_MISMATCH")
        if envelope.delivery_packet_id and envelope.delivery_packet_id != work_item.delivery_packet_id:
            errors.append("EVIDENCE_WORK_ITEM_PACKET_ID_MISMATCH")
        if envelope.correlation_root_id and envelope.correlation_root_id != work_item.correlation_root_id:
            errors.append("EVIDENCE_CORRELATION_ROOT_MISMATCH")

    if dispatch_recommendation is None:
        errors.append("MISSING_DISPATCH_RECOMMENDATION")
    else:
        if envelope.dispatch_decision_id and envelope.dispatch_decision_id != dispatch_recommendation.dispatch_decision_id:
            errors.append("EVIDENCE_DISPATCH_RECOMMENDATION_ID_MISMATCH")
        if envelope.work_item_id and envelope.work_item_id != dispatch_recommendation.work_item_id:
            errors.append("EVIDENCE_DISPATCH_WORK_ITEM_ID_MISMATCH")
        if dispatch_recommendation.selected_agent_id and envelope.agent_id != dispatch_recommendation.selected_agent_id:
            errors.append("EVIDENCE_AGENT_ID_MISMATCH")

    if envelope.traceability is None:
        errors.append("MISSING_EVIDENCE_TRACEABILITY")
    else:
        errors.extend(_validate_traceability(envelope.traceability))
        if "EDC-ISSUE-05" not in envelope.traceability.issue_ids:
            errors.append("EVIDENCE_TRACEABILITY_MISSING_L3_ISSUE")

    for reference in envelope.evidence_refs:
        errors.extend(validate_evidence_reference(reference, source_work_item_id=envelope.work_item_id).errors)

    errors.extend(_validate_l3_non_authority(envelope))
    if envelope.transport_status == "acknowledged" and envelope.evidence_package_complete:
        errors.append("ACKNOWLEDGEMENT_IS_NOT_DELIVERY_TRUTH")

    return _result(errors, explanations=_envelope_explanation(envelope, work_item, dispatch_recommendation))


def validate_evidence_transport_state(
    state: EvidenceTransportState,
    *,
    envelope: EvidenceEnvelope | None,
    work_item: WorkItem | None,
    dispatch_recommendation: DispatchRecommendation | None,
) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(state.transport_state_id, "MISSING_EVIDENCE_TRANSPORT_STATE_ID"))
    errors.extend(_missing_scalar(state.envelope_id, "MISSING_EVIDENCE_TRANSPORT_ENVELOPE_ID"))
    errors.extend(_missing_scalar(state.work_item_id, "MISSING_EVIDENCE_TRANSPORT_WORK_ITEM_ID"))
    errors.extend(_missing_scalar(state.dispatch_decision_id, "MISSING_EVIDENCE_TRANSPORT_DISPATCH_ID"))
    errors.extend(_missing_scalar(state.correlation_root_id, "MISSING_EVIDENCE_TRANSPORT_CORRELATION_ROOT_ID"))
    errors.extend(_missing_scalar(state.idempotency_key, "MISSING_EVIDENCE_TRANSPORT_IDEMPOTENCY_KEY"))
    errors.extend(_missing_scalar(state.observed_at_utc, "MISSING_EVIDENCE_TRANSPORT_OBSERVED_AT"))
    if state.status not in EVIDENCE_TRANSPORT_STATUSES:
        errors.append("INVALID_EVIDENCE_TRANSPORT_STATUS")
    if state.event_type not in EVIDENCE_EVENT_TYPES:
        errors.append("INVALID_EVIDENCE_TRANSPORT_EVENT_TYPE")
    if state.sequence_number < 1:
        errors.append("INVALID_EVIDENCE_TRANSPORT_SEQUENCE_NUMBER")
    if state.attempt_number < 1:
        errors.append("INVALID_EVIDENCE_TRANSPORT_ATTEMPT_NUMBER")

    if envelope is None:
        errors.append("MISSING_EVIDENCE_ENVELOPE")
    else:
        if state.envelope_id and state.envelope_id != envelope.envelope_id:
            errors.append("EVIDENCE_TRANSPORT_ENVELOPE_ID_MISMATCH")
        if state.work_item_id and state.work_item_id != envelope.work_item_id:
            errors.append("EVIDENCE_TRANSPORT_WORK_ITEM_ID_MISMATCH")
        if state.dispatch_decision_id and state.dispatch_decision_id != envelope.dispatch_decision_id:
            errors.append("EVIDENCE_TRANSPORT_DISPATCH_ID_MISMATCH")
        if state.correlation_root_id and state.correlation_root_id != envelope.correlation_root_id:
            errors.append("EVIDENCE_TRANSPORT_CORRELATION_ROOT_MISMATCH")
        if state.idempotency_key and state.idempotency_key != envelope.idempotency_key:
            errors.append("EVIDENCE_TRANSPORT_IDEMPOTENCY_KEY_MISMATCH")
        if state.sequence_number != envelope.sequence_number:
            errors.append("EVIDENCE_TRANSPORT_SEQUENCE_NUMBER_MISMATCH")

    if work_item is None:
        errors.append("MISSING_PARENT_WORK_ITEM")
    elif state.work_item_id and state.work_item_id != work_item.work_item_id:
        errors.append("EVIDENCE_TRANSPORT_PARENT_WORK_ITEM_MISMATCH")

    if dispatch_recommendation is None:
        errors.append("MISSING_DISPATCH_RECOMMENDATION")
    elif state.dispatch_decision_id and state.dispatch_decision_id != dispatch_recommendation.dispatch_decision_id:
        errors.append("EVIDENCE_TRANSPORT_DISPATCH_RECOMMENDATION_MISMATCH")

    if state.status == "timed_out":
        errors.extend(_missing_scalar(state.timeout_class, "MISSING_EVIDENCE_TIMEOUT_CLASS"))
    if state.status == "failed":
        errors.extend(_missing_scalar(state.failure_reason, "MISSING_EVIDENCE_TRANSPORT_FAILURE_REASON"))

    errors.extend(_validate_l3_non_authority(state))
    if state.status == "acknowledged" and state.evidence_package_complete:
        errors.append("ACKNOWLEDGEMENT_IS_NOT_DELIVERY_TRUTH")

    return _result(errors, explanations=_transport_explanation(state))


def validate_evidence_transport_transition(
    previous_state: EvidenceTransportState,
    next_state: EvidenceTransportState,
    *,
    envelope: EvidenceEnvelope,
) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(
        _validate_transition(
            current_status=previous_state.status,
            target_status=next_state.status,
            valid_statuses=EVIDENCE_TRANSPORT_STATUSES,
            transition_table=EVIDENCE_TRANSPORT_TRANSITIONS,
            invalid_current_code="INVALID_EVIDENCE_TRANSPORT_STATUS",
            invalid_target_code="INVALID_EVIDENCE_TRANSPORT_TARGET_STATUS",
            invalid_transition_code="INVALID_EVIDENCE_TRANSPORT_TRANSITION",
        )
    )
    if next_state.envelope_id != envelope.envelope_id:
        errors.append("EVIDENCE_TRANSPORT_ENVELOPE_ID_MISMATCH")
    if next_state.work_item_id != previous_state.work_item_id:
        errors.append("EVIDENCE_TRANSPORT_WORK_ITEM_ID_CHANGED")
    if next_state.correlation_root_id != previous_state.correlation_root_id:
        errors.append("EVIDENCE_TRANSPORT_CORRELATION_ROOT_CHANGED")
    if next_state.idempotency_key != previous_state.idempotency_key:
        errors.append("EVIDENCE_TRANSPORT_IDEMPOTENCY_KEY_CHANGED")
    if next_state.sequence_number != previous_state.sequence_number:
        errors.append("EVIDENCE_TRANSPORT_SEQUENCE_NUMBER_CHANGED")
    if next_state.status in {"retrying", "superseded"}:
        errors.extend(_missing_scalar(next_state.prior_envelope_id, "MISSING_EVIDENCE_TRANSPORT_LINEAGE"))
        errors.extend(_missing_scalar(next_state.prior_state, "MISSING_EVIDENCE_TRANSPORT_PRIOR_STATE"))
        if next_state.prior_state and next_state.prior_state != previous_state.status:
            errors.append("EVIDENCE_TRANSPORT_PRIOR_STATE_MISMATCH")
        if next_state.prior_envelope_id and next_state.prior_envelope_id != previous_state.envelope_id:
            errors.append("EVIDENCE_TRANSPORT_PRIOR_ENVELOPE_MISMATCH")
    if next_state.status == "retrying":
        if next_state.attempt_number <= previous_state.attempt_number:
            errors.append("EVIDENCE_RETRY_REQUIRES_INCREMENTED_ATTEMPT")
        errors.extend(_missing_scalar(next_state.retry_after_utc, "MISSING_EVIDENCE_RETRY_AFTER"))
    if next_state.status == "timed_out":
        errors.extend(_missing_scalar(next_state.timeout_class, "MISSING_EVIDENCE_TIMEOUT_CLASS"))
    if next_state.status == "failed":
        errors.extend(_missing_scalar(next_state.failure_reason, "MISSING_EVIDENCE_TRANSPORT_FAILURE_REASON"))
    errors.extend(_validate_l3_non_authority(next_state))
    if next_state.status == "acknowledged" and next_state.evidence_package_complete:
        errors.append("ACKNOWLEDGEMENT_IS_NOT_DELIVERY_TRUTH")
    return _result(errors, explanations=_transport_explanation(next_state))


def evaluate_evidence_idempotency(
    candidate: EvidenceEnvelope,
    existing_envelopes: list[EvidenceEnvelope],
) -> EDCContractValidationResult:
    errors: list[str] = []
    errors.extend(_missing_scalar(candidate.idempotency_key, "MISSING_EVIDENCE_IDEMPOTENCY_KEY"))
    if errors:
        return _result(errors)
    for existing in existing_envelopes:
        if (
            existing.idempotency_key == candidate.idempotency_key
            and existing.work_item_id == candidate.work_item_id
            and existing.sequence_number == candidate.sequence_number
        ):
            return _result(
                [],
                warnings=["DUPLICATE_EVIDENCE_ENVELOPE_IGNORED"],
                explanations={
                    "action": "duplicate_ignored",
                    "original_envelope_id": existing.envelope_id,
                    "duplicate_envelope_id": candidate.envelope_id,
                    "idempotency_key": candidate.idempotency_key,
                },
            )
    return _result(
        [],
        explanations={
            "action": "accepted",
            "original_envelope_id": "",
            "idempotency_key": candidate.idempotency_key,
        },
    )


def validate_ack_not_delivery_truth(state: EvidenceTransportState) -> EDCContractValidationResult:
    errors: list[str] = []
    if state.status != "acknowledged":
        errors.append("EVIDENCE_TRANSPORT_STATE_NOT_ACKNOWLEDGED")
    if state.evidence_package_complete or state.not_delivery_truth is not True:
        errors.append("ACKNOWLEDGEMENT_IS_NOT_DELIVERY_TRUTH")
    errors.extend(_validate_l3_non_authority(state))
    return _result(errors, explanations=_transport_explanation(state))


def validate_transport_non_authority(state: EvidenceTransportState) -> EDCContractValidationResult:
    errors = _validate_l3_non_authority(state)
    if state.status == "acknowledged" and state.evidence_package_complete:
        errors.append("ACKNOWLEDGEMENT_IS_NOT_DELIVERY_TRUTH")
    return _result(errors, explanations=_transport_explanation(state))


def validate_evidence_replay_lineage(
    envelope: EvidenceEnvelope,
    *,
    prior_envelope: EvidenceEnvelope | None,
) -> EDCContractValidationResult:
    errors: list[str] = []
    if prior_envelope is None:
        errors.append("MISSING_REPLAY_PRIOR_ENVELOPE")
    else:
        errors.extend(_missing_scalar(envelope.replay_of_envelope_id, "MISSING_REPLAY_LINEAGE"))
        if envelope.replay_of_envelope_id and envelope.replay_of_envelope_id != prior_envelope.envelope_id:
            errors.append("REPLAY_PRIOR_ENVELOPE_MISMATCH")
        if envelope.work_item_id != prior_envelope.work_item_id:
            errors.append("REPLAY_WORK_ITEM_ID_MISMATCH")
        if envelope.idempotency_key != prior_envelope.idempotency_key:
            errors.append("REPLAY_IDEMPOTENCY_KEY_MISMATCH")
        if envelope.attempt_number <= prior_envelope.attempt_number:
            errors.append("REPLAY_REQUIRES_INCREMENTED_ATTEMPT")
    return _result(
        errors,
        explanations={
            "replay_of_envelope_id": envelope.replay_of_envelope_id,
            "current_envelope_id": envelope.envelope_id,
            "prior_envelope_hash": prior_envelope.envelope_hash() if prior_envelope else "",
        },
    )


def validate_evidence_supersession(
    superseded_envelope: EvidenceEnvelope,
    current_envelope: EvidenceEnvelope,
) -> EDCContractValidationResult:
    errors: list[str] = []
    if superseded_envelope.transport_status != "superseded":
        errors.append("PRIOR_EVIDENCE_ENVELOPE_NOT_SUPERSEDED")
    if superseded_envelope.superseded_by_envelope_id != current_envelope.envelope_id:
        errors.append("SUPERSEDED_ENVELOPE_CURRENT_POINTER_MISMATCH")
    if current_envelope.supersedes_envelope_id != superseded_envelope.envelope_id:
        errors.append("CURRENT_ENVELOPE_SUPERSESSION_POINTER_MISMATCH")
    if current_envelope.work_item_id != superseded_envelope.work_item_id:
        errors.append("SUPERSESSION_WORK_ITEM_ID_MISMATCH")
    return _result(
        errors,
        explanations={
            "superseded_envelope_id": superseded_envelope.envelope_id,
            "current_envelope_id": current_envelope.envelope_id,
            "visible_envelope_ids": [superseded_envelope.envelope_id, current_envelope.envelope_id],
        },
    )


def explain_evidence_transport_state(state: EvidenceTransportState) -> dict[str, Any]:
    return _transport_explanation(state)


def stable_contract_hash(value: Any) -> str:
    encoded = json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _evaluate_roster_member(
    snapshot: RosterSnapshot,
    snapshot_hash: str,
    member: RosterMember,
    requirement: RosterEligibilityRequirement,
) -> RosterEligibilityDecision:
    exclusion_reasons: list[str] = []
    matched_capabilities: list[str] = []
    matched_authority_boundary: list[str] = []

    if member.registration_state == "unregistered":
        exclusion_reasons.append("AGENT_UNREGISTERED")
    elif member.registration_state == "suspended":
        exclusion_reasons.append("AGENT_SUSPENDED")
    elif member.registration_state == "registered_passive":
        exclusion_reasons.append("AGENT_PLANNING_VISIBLE_ONLY")
    elif member.registration_state == "unavailable":
        exclusion_reasons.append("AGENT_UNAVAILABLE")

    if not exclusion_reasons:
        missing_capabilities = [tag for tag in requirement.required_capability_tags if tag not in member.capability_tags]
        if missing_capabilities:
            exclusion_reasons.append("MISSING_REQUIRED_CAPABILITY")
        else:
            matched_capabilities = list(requirement.required_capability_tags)

        missing_authority = [boundary for boundary in requirement.authority_boundary if boundary not in member.authority_boundary]
        if missing_authority:
            exclusion_reasons.append("AUTHORITY_BOUNDARY_MISMATCH")
        else:
            matched_authority_boundary = list(requirement.authority_boundary)

        if any(boundary in member.authority_boundary for boundary in requirement.no_go_boundaries):
            exclusion_reasons.append("NO_GO_BOUNDARY_CONFLICT")

    return RosterEligibilityDecision(
        decision_id=f"eligibility::{snapshot.roster_snapshot_id}::{member.agent_id}",
        agent_id=member.agent_id,
        eligible=not exclusion_reasons,
        roster_snapshot_id=snapshot.roster_snapshot_id,
        roster_snapshot_hash=snapshot_hash,
        matched_capabilities=matched_capabilities,
        matched_authority_boundary=matched_authority_boundary,
        exclusion_reasons=exclusion_reasons,
        evidence_refs=[
            f"roster_snapshot:{snapshot.roster_snapshot_id}",
            f"roster_snapshot_hash:{snapshot_hash}",
            f"roster_member:{member.agent_id}",
        ],
    )


def _decision_reasons(decisions: list[dict[str, Any]], allowed_reasons: set[str]) -> list[str]:
    found: list[str] = []
    for decision in decisions:
        for reason in decision.get("exclusion_reasons", []):
            if reason in allowed_reasons and reason not in found:
                found.append(reason)
    return found


def _collect_decision_evidence(decisions: list[dict[str, Any]]) -> list[str]:
    evidence_refs: list[str] = []
    for decision in decisions:
        for evidence_ref in decision.get("evidence_refs", []):
            if evidence_ref not in evidence_refs:
                evidence_refs.append(evidence_ref)
    return evidence_refs


def _validate_transition(
    *,
    current_status: str,
    target_status: str,
    valid_statuses: set[str],
    transition_table: dict[str, set[str]],
    invalid_current_code: str,
    invalid_target_code: str,
    invalid_transition_code: str,
) -> list[str]:
    errors: list[str] = []
    if current_status not in valid_statuses:
        errors.append(invalid_current_code)
    if target_status not in valid_statuses:
        errors.append(invalid_target_code)
    if errors:
        return errors
    if target_status not in transition_table[current_status]:
        errors.append(invalid_transition_code)
    return errors


def _validate_source_authority(value: SourceAuthorityRef | None) -> list[str]:
    if value is None:
        return ["MISSING_SOURCE_AUTHORITY_REF"]
    errors: list[str] = []
    errors.extend(_missing_scalar(value.authority_id, "MISSING_SOURCE_AUTHORITY_ID"))
    errors.extend(_missing_scalar(value.source_type, "MISSING_SOURCE_AUTHORITY_TYPE"))
    errors.extend(_missing_scalar(value.source_uri, "MISSING_SOURCE_AUTHORITY_URI"))
    errors.extend(_missing_scalar(value.authority_actor, "MISSING_SOURCE_AUTHORITY_ACTOR"))
    if not value.source_sha256:
        errors.append("MISSING_SOURCE_AUTHORITY_HASH")
    elif not SHA256_RE.match(value.source_sha256):
        errors.append("INVALID_SOURCE_AUTHORITY_HASH")
    return errors


def _validate_evidence_expectation(value: EvidenceExpectation | None) -> list[str]:
    if value is None:
        return ["MISSING_EVIDENCE_EXPECTATION"]
    errors: list[str] = []
    errors.extend(_missing_scalar(value.expectation_id, "MISSING_EVIDENCE_EXPECTATION_ID"))
    errors.extend(_missing_list(value.required_artifacts, "MISSING_EVIDENCE_REQUIRED_ARTIFACTS"))
    errors.extend(_missing_list(value.validation_refs, "MISSING_EVIDENCE_VALIDATION_REFS"))
    errors.extend(_missing_scalar(value.reviewer, "MISSING_EVIDENCE_REVIEWER"))
    return errors


def _validate_traceability(value: TraceabilityRef) -> list[str]:
    errors: list[str] = []
    errors.extend(_missing_list(value.issue_ids, "MISSING_TRACE_ISSUE_IDS"))
    errors.extend(_missing_list(value.prd_ids, "MISSING_TRACE_PRD_IDS"))
    errors.extend(_missing_list(value.spec_ids, "MISSING_TRACE_SPEC_IDS"))
    errors.extend(_missing_list(value.ux_surface_ids, "MISSING_TRACE_UX_SURFACES"))
    errors.extend(_missing_list(value.test_case_ids, "MISSING_TRACE_TEST_CASE_IDS"))
    errors.extend(_validate_accepted_issue_ids(value.issue_ids))
    return errors


def _validate_accepted_issue_ids(issue_ids: list[str]) -> list[str]:
    if not issue_ids:
        return ["MISSING_ACCEPTED_ISSUE_MAPPING"]
    if any(issue_id not in ACCEPTED_EDC_ISSUE_IDS for issue_id in issue_ids):
        return ["UNKNOWN_EDC_ISSUE"]
    return []


def _validate_single_objective(objectives: list[str]) -> list[str]:
    if not objectives:
        return ["MISSING_PACKET_OBJECTIVE"]
    if len([objective for objective in objectives if objective]) != 1:
        return ["PACKET_REQUIRES_SINGLE_OBJECTIVE"]
    return []


def _validate_evidence_inheritance(
    packet: DeliveryPacket,
    source_publication: Layer1TaskPublication,
) -> list[str]:
    if not packet.evidence_expectation or not source_publication.evidence_expectation:
        return []
    if packet.evidence_expectation.expectation_id != source_publication.evidence_expectation.expectation_id:
        return ["PACKET_EVIDENCE_EXPECTATION_NOT_INHERITED"]
    return []


def _validate_no_go_inheritance(packet_boundaries: list[str], publication_boundaries: list[str]) -> list[str]:
    if not packet_boundaries:
        return ["MISSING_NO_GO_BOUNDARIES"]
    missing = [boundary for boundary in publication_boundaries if boundary not in packet_boundaries]
    if missing:
        return ["MISSING_INHERITED_NO_GO_BOUNDARY"]
    return []


def _validate_blocker(value: BlockerEvidence | None, prefix: str) -> list[str]:
    if value is None:
        return [f"MISSING_{prefix}_BLOCKER_EVIDENCE"]
    errors: list[str] = []
    errors.extend(_missing_scalar(value.reason_code, f"MISSING_{prefix}_BLOCKER_REASON_CODE"))
    errors.extend(_missing_scalar(value.human_readable_reason, f"MISSING_{prefix}_BLOCKER_REASON"))
    errors.extend(_missing_list(value.evidence_refs, f"MISSING_{prefix}_BLOCKER_EVIDENCE_REFS"))
    return errors


def _blocker_explanation(value: BlockerEvidence) -> dict[str, Any]:
    return {
        "reason_code": value.reason_code,
        "human_readable_reason": value.human_readable_reason,
        "evidence_refs": list(value.evidence_refs),
        "recommended_action": value.recommended_action,
        "revisit_condition": value.revisit_condition,
    }


def _missing_scalar(value: str | None, error: str) -> list[str]:
    return [error] if value is None or not str(value).strip() else []


def _missing_list(value: list[Any], error: str) -> list[str]:
    return [error] if not value else []


def _is_layer1_authority(actor: str) -> bool:
    actor_norm = (actor or "").strip().lower()
    return any(actor_norm == prefix or actor_norm.startswith(f"{prefix}:") for prefix in LAYER1_AUTHORITY_PREFIXES)


def _result(
    errors: list[str],
    *,
    warnings: list[str] | None = None,
    explanations: dict[str, Any] | None = None,
) -> EDCContractValidationResult:
    deduped_errors = _dedupe(errors)
    return EDCContractValidationResult(
        ok=not deduped_errors,
        errors=deduped_errors,
        warnings=_dedupe(warnings or []),
        explanations=explanations or {},
    )


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped


def _normal_sha256(value: str) -> str:
    return value.removeprefix("sha256:").lower()


def _validate_l3_non_authority(value: Any) -> list[str]:
    errors: list[str] = []
    if getattr(value, "creates_gate_decision", False) or getattr(value, "gate_decision_created", False):
        errors.append("TRANSPORT_STATUS_CANNOT_CREATE_GATE_DECISION")
    if getattr(value, "creates_delivery_receipt", False) or getattr(value, "delivery_receipt_created", False):
        errors.append("TRANSPORT_STATUS_CANNOT_CREATE_DELIVERY_RECEIPT")
    if getattr(value, "not_gate_decision", True) is not True:
        errors.append("TRANSPORT_STATUS_CANNOT_CREATE_GATE_DECISION")
    if getattr(value, "not_delivery_receipt", True) is not True:
        errors.append("TRANSPORT_STATUS_CANNOT_CREATE_DELIVERY_RECEIPT")
    if getattr(value, "transport_failure_is_gate_blocker", False):
        errors.append("TRANSPORT_FAILURE_IS_NOT_GATE_BLOCKER")
    return errors


def _transport_explanation(state: EvidenceTransportState) -> dict[str, Any]:
    return {
        "transport_state_id": state.transport_state_id,
        "envelope_id": state.envelope_id,
        "work_item_id": state.work_item_id,
        "dispatch_decision_id": state.dispatch_decision_id,
        "correlation_root_id": state.correlation_root_id,
        "status": state.status,
        "event_type": state.event_type,
        "attempt_number": state.attempt_number,
        "retry_scheduled": state.status == "retrying",
        "evidence_package_complete": state.evidence_package_complete,
        "package_state": "complete" if state.evidence_package_complete else "incomplete",
        "gate_state": state.gate_state,
        "receipt_state": state.receipt_state,
        "receipt_available": state.receipt_state == "issuable",
        "not_delivery_truth": state.not_delivery_truth,
        "not_gate_decision": state.not_gate_decision,
        "not_delivery_receipt": state.not_delivery_receipt,
        "gate_outcome_created": state.gate_decision_created,
        "transport_failure_is_gate_blocker": state.transport_failure_is_gate_blocker,
        "prior_state": state.prior_state,
        "prior_envelope_id": state.prior_envelope_id,
    }


def _envelope_explanation(
    envelope: EvidenceEnvelope,
    work_item: WorkItem | None,
    dispatch_recommendation: DispatchRecommendation | None,
) -> dict[str, Any]:
    return {
        "envelope_id": envelope.envelope_id,
        "work_item_id": envelope.work_item_id,
        "work_item_hash": work_item.work_item_hash() if work_item else "",
        "delivery_packet_id": envelope.delivery_packet_id,
        "dispatch_decision_id": envelope.dispatch_decision_id,
        "dispatch_recommendation_id": dispatch_recommendation.dispatch_decision_id if dispatch_recommendation else "",
        "correlation_root_id": envelope.correlation_root_id,
        "idempotency_key": envelope.idempotency_key,
        "sequence_number": envelope.sequence_number,
        "evidence_package_complete": envelope.evidence_package_complete,
        "not_delivery_truth": envelope.not_delivery_truth,
        "not_gate_decision": envelope.not_gate_decision,
        "not_delivery_receipt": envelope.not_delivery_receipt,
    }


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
