from nexus.mq.integrated_evidence_package_generator import (
    IntegratedEvidencePackageInput,
    build_integrated_evidence_package,
)


def _package_input(**overrides):
    data = {
        "package_id": "real-agent-package-001",
        "run_id": "run-001",
        "adapter_event_refs": ["evidence://adapter/connect", "evidence://adapter/result"],
        "lifecycle_record_refs": ["evidence://lifecycle/register", "evidence://lifecycle/heartbeat"],
        "eligibility_decision_refs": ["decision://001"],
        "reservation_lease_refs": ["lease://001"],
        "dispatch_record_refs": ["dispatch://assignment/001"],
        "layer3_transport_refs": ["mq://assignment/001"],
        "runtime_result_refs": ["result://candidate/001"],
        "drain_offline_refs": ["drain://run-001", "offline://run-001"],
        "runbook_ref": "docs/runbooks/4.19_REAL_AGENT_OPERATING_ENVIRONMENT_RUNBOOK.md",
        "secret_scan_ref": "evidence://secret-scan/clean",
        "checksum_manifest_ref": "evidence://manifest/SHA256SUMS.txt",
        "no_a2a_evidence_ref": "evidence://no-a2a",
        "diagnostic_readiness_evidence_ref": "evidence://diagnostic-readiness",
        "secret_scan_passed": True,
        "checksum_verification_passed": True,
    }
    data.update(overrides)
    return IntegratedEvidencePackageInput(**data)


def test_integrated_evidence_package_requires_all_raw_records_secret_scan_checksums():
    package = build_integrated_evidence_package(_package_input())

    assert package.accepted is True
    assert package.review_ready_candidate is True
    assert package.final_readiness_claimed is False
    assert package.not_business_completion is True
    assert package.status == "complete_for_nova_review"


def test_integrated_evidence_package_blocks_missing_decision_lease_or_runbook_refs():
    package = build_integrated_evidence_package(
        _package_input(eligibility_decision_refs=[], reservation_lease_refs=[], runbook_ref="")
    )

    assert package.accepted is False
    assert package.review_ready_candidate is False
    assert "MISSING_ELIGIBILITY_DECISION_REFS" in package.errors
    assert "MISSING_RESERVATION_LEASE_REFS" in package.errors
    assert "MISSING_RUNBOOK_REF" in package.errors


def test_integrated_evidence_package_blocks_failed_secret_scan_or_checksum():
    package = build_integrated_evidence_package(
        _package_input(secret_scan_passed=False, checksum_verification_passed=False)
    )

    assert package.accepted is False
    assert "SECRET_SCAN_NOT_CLEAN" in package.errors
    assert "CHECKSUM_VERIFICATION_FAILED" in package.errors


def test_integrated_evidence_package_blocks_missing_controller_bridge_refs_when_required():
    package = build_integrated_evidence_package(
        _package_input(controller_bridge_required=True, controller_bridge_evidence_refs=[])
    )

    assert package.accepted is False
    assert package.review_ready_candidate is False
    assert "MISSING_CONTROLLER_BRIDGE_EVIDENCE_REFS" in package.errors
