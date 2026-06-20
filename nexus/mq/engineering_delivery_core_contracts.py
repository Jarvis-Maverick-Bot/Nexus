"""Engineering Delivery Core Slice 001 contract records and validators.

This module is intentionally contract-only. It defines deterministic records and
fail-closed validators for Layer 1 publication plus DeliveryPacket intake. It
does not dispatch work, transport evidence, decide gates, issue receipts, or
start any live process.
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


def stable_contract_hash(value: Any) -> str:
    encoded = json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


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


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
