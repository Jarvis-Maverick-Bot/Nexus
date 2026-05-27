"""Evidence package validation for Track 2 controller bridge."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from nexus.mq.controller_bridge_models import dedupe


@dataclass
class ControllerBridgeEvidenceInput:
    package_id: str
    dispatch_run_id: str
    decision_ref: str
    dispatch_records: list[str]
    lifecycle_decision_refs: list[str]
    reservation_lease_refs: list[str]
    assignment_refs: list[str]
    mq_transport_refs: list[str]
    runtime_event_refs: list[str]
    result_candidate_refs: list[str]
    drain_offline_refs: list[str]
    secret_scan_ref: str
    checksum_manifest_ref: str
    secret_scan_passed: bool
    checksum_verification_passed: bool
    diagnostic_only: bool = False
    not_business_completion: bool = True


@dataclass
class ControllerBridgeEvidencePackage:
    accepted: bool
    package_id: str
    dispatch_run_id: str
    status: str
    errors: list[str] = field(default_factory=list)
    final_pass_claimed: bool = False
    live_readiness_claimed: bool = False
    evidence_refs: dict[str, Any] = field(default_factory=dict)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_controller_bridge_evidence_package(source: ControllerBridgeEvidenceInput) -> ControllerBridgeEvidencePackage:
    errors: list[str] = []
    for error, value in {
        "MISSING_PACKAGE_ID": source.package_id,
        "MISSING_DISPATCH_RUN_ID": source.dispatch_run_id,
        "MISSING_DECISION_REF": source.decision_ref,
        "MISSING_SECRET_SCAN_REF": source.secret_scan_ref,
        "MISSING_CHECKSUM_MANIFEST_REF": source.checksum_manifest_ref,
    }.items():
        if not value:
            errors.append(error)
    for error, values in {
        "MISSING_DISPATCH_RECORDS": source.dispatch_records,
        "MISSING_LIFECYCLE_DECISION_REFS": source.lifecycle_decision_refs,
        "MISSING_RESERVATION_LEASE_REFS": source.reservation_lease_refs,
        "MISSING_ASSIGNMENT_REFS": source.assignment_refs,
        "MISSING_MQ_TRANSPORT_REFS": source.mq_transport_refs,
        "MISSING_RUNTIME_EVENT_REFS": source.runtime_event_refs,
        "MISSING_RESULT_CANDIDATE_REFS": source.result_candidate_refs,
        "MISSING_DRAIN_OFFLINE_REFS": source.drain_offline_refs,
    }.items():
        if not values:
            errors.append(error)
    if source.secret_scan_passed is not True:
        errors.append("SECRET_SCAN_NOT_CLEAN")
    if source.checksum_verification_passed is not True:
        errors.append("CHECKSUM_VERIFICATION_FAILED")
    if source.not_business_completion is not True:
        errors.append("CONTROLLER_BRIDGE_PACKAGE_CANNOT_BE_BUSINESS_COMPLETION")
    if source.diagnostic_only:
        errors.append("DIAGNOSTIC_ONLY_NOT_REVIEW_READY")

    status = "READY_FOR_REVIEW"
    if errors and source.diagnostic_only:
        status = "PARTIAL_BLOCKED"
    elif errors:
        status = "FAILED_VALIDATION"
    return ControllerBridgeEvidencePackage(
        accepted=not errors,
        package_id=source.package_id,
        dispatch_run_id=source.dispatch_run_id,
        status=status,
        errors=dedupe(errors),
        final_pass_claimed=False,
        live_readiness_claimed=False,
        evidence_refs={
            "decision": source.decision_ref,
            "dispatch": list(source.dispatch_records),
            "lifecycle_decisions": list(source.lifecycle_decision_refs),
            "reservation_leases": list(source.reservation_lease_refs),
            "assignments": list(source.assignment_refs),
            "mq_transport": list(source.mq_transport_refs),
            "runtime_events": list(source.runtime_event_refs),
            "result_candidates": list(source.result_candidate_refs),
            "drain_offline": list(source.drain_offline_refs),
            "secret_scan": source.secret_scan_ref,
            "checksum_manifest": source.checksum_manifest_ref,
        },
    )
