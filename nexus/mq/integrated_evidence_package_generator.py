"""Integrated 4.19 real-agent evidence package classifier."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class IntegratedEvidencePackageInput:
    package_id: str
    run_id: str
    adapter_event_refs: list[str]
    lifecycle_record_refs: list[str]
    eligibility_decision_refs: list[str]
    reservation_lease_refs: list[str]
    dispatch_record_refs: list[str]
    layer3_transport_refs: list[str]
    runtime_result_refs: list[str]
    drain_offline_refs: list[str]
    runbook_ref: str
    secret_scan_ref: str
    checksum_manifest_ref: str
    no_a2a_evidence_ref: str
    diagnostic_readiness_evidence_ref: str
    secret_scan_passed: bool
    checksum_verification_passed: bool
    controller_bridge_required: bool = False
    controller_bridge_evidence_refs: list[str] = field(default_factory=list)
    not_business_completion: bool = True


@dataclass
class IntegratedEvidencePackage:
    accepted: bool
    package_id: str
    run_id: str
    status: str
    errors: list[str] = field(default_factory=list)
    review_ready_candidate: bool = False
    final_readiness_claimed: bool = False
    evidence_refs: dict[str, Any] = field(default_factory=dict)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_integrated_evidence_package(source: IntegratedEvidencePackageInput) -> IntegratedEvidencePackage:
    errors: list[str] = []
    required_lists = {
        "MISSING_ADAPTER_EVENT_REFS": source.adapter_event_refs,
        "MISSING_LIFECYCLE_RECORD_REFS": source.lifecycle_record_refs,
        "MISSING_ELIGIBILITY_DECISION_REFS": source.eligibility_decision_refs,
        "MISSING_RESERVATION_LEASE_REFS": source.reservation_lease_refs,
        "MISSING_DISPATCH_RECORD_REFS": source.dispatch_record_refs,
        "MISSING_LAYER3_TRANSPORT_REFS": source.layer3_transport_refs,
        "MISSING_RUNTIME_RESULT_REFS": source.runtime_result_refs,
        "MISSING_DRAIN_OFFLINE_REFS": source.drain_offline_refs,
    }
    for error, values in required_lists.items():
        if not values:
            errors.append(error)
    for error, value in {
        "MISSING_PACKAGE_ID": source.package_id,
        "MISSING_RUN_ID": source.run_id,
        "MISSING_RUNBOOK_REF": source.runbook_ref,
        "MISSING_SECRET_SCAN_REF": source.secret_scan_ref,
        "MISSING_CHECKSUM_MANIFEST_REF": source.checksum_manifest_ref,
        "MISSING_NO_A2A_EVIDENCE_REF": source.no_a2a_evidence_ref,
        "MISSING_DIAGNOSTIC_READINESS_EVIDENCE_REF": source.diagnostic_readiness_evidence_ref,
    }.items():
        if not value:
            errors.append(error)
    if source.secret_scan_passed is not True:
        errors.append("SECRET_SCAN_NOT_CLEAN")
    if source.checksum_verification_passed is not True:
        errors.append("CHECKSUM_VERIFICATION_FAILED")
    if source.controller_bridge_required and not source.controller_bridge_evidence_refs:
        errors.append("MISSING_CONTROLLER_BRIDGE_EVIDENCE_REFS")
    if source.not_business_completion is not True:
        errors.append("INTEGRATED_PACKAGE_CANNOT_BE_BUSINESS_COMPLETION")

    accepted = not errors
    return IntegratedEvidencePackage(
        accepted=accepted,
        package_id=source.package_id,
        run_id=source.run_id,
        status="complete_for_nova_review" if accepted else "blocked_incomplete",
        errors=_dedupe(errors),
        review_ready_candidate=accepted,
        final_readiness_claimed=False,
        evidence_refs={
            "adapter": list(source.adapter_event_refs),
            "lifecycle": list(source.lifecycle_record_refs),
            "eligibility_decisions": list(source.eligibility_decision_refs),
            "reservation_leases": list(source.reservation_lease_refs),
            "dispatch": list(source.dispatch_record_refs),
            "layer3_transport": list(source.layer3_transport_refs),
            "runtime_results": list(source.runtime_result_refs),
            "drain_offline": list(source.drain_offline_refs),
            "runbook": source.runbook_ref,
            "secret_scan": source.secret_scan_ref,
            "checksum_manifest": source.checksum_manifest_ref,
            "no_a2a": source.no_a2a_evidence_ref,
            "diagnostic_readiness": source.diagnostic_readiness_evidence_ref,
            "controller_bridge": list(source.controller_bridge_evidence_refs),
        },
    )


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
