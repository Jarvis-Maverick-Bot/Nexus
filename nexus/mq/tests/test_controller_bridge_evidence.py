from nexus.mq.controller_bridge_evidence import (
    ControllerBridgeEvidenceInput,
    build_controller_bridge_evidence_package,
)


def _evidence(**overrides):
    data = {
        "package_id": "bridge-package-001",
        "dispatch_run_id": "run-001",
        "decision_ref": "decision://layer1/001",
        "dispatch_records": ["dispatch://run/001", "dispatch://publish/001"],
        "lifecycle_decision_refs": ["decision://runtime/001"],
        "reservation_lease_refs": ["lease://001"],
        "assignment_refs": ["assignment://001"],
        "mq_transport_refs": ["mq://publish/001"],
        "runtime_event_refs": ["runtime://ack/001", "runtime://progress/001"],
        "result_candidate_refs": ["result://candidate/001"],
        "drain_offline_refs": ["drain://run-001", "offline://runtime/001"],
        "secret_scan_ref": "evidence://secret-scan/clean",
        "checksum_manifest_ref": "evidence://SHA256SUMS",
        "secret_scan_passed": True,
        "checksum_verification_passed": True,
    }
    data.update(overrides)
    return ControllerBridgeEvidenceInput(**data)


def test_controller_bridge_evidence_accepts_complete_lease_backed_package():
    package = build_controller_bridge_evidence_package(_evidence())

    assert package.accepted is True
    assert package.status == "READY_FOR_REVIEW"
    assert package.final_pass_claimed is False
    assert package.live_readiness_claimed is False


def test_evidence_package_requires_lifecycle_dispatch_mq_runtime_result_refs():
    package = build_controller_bridge_evidence_package(
        _evidence(
            dispatch_records=[],
            lifecycle_decision_refs=[],
            reservation_lease_refs=[],
            mq_transport_refs=[],
            runtime_event_refs=[],
            result_candidate_refs=[],
        )
    )

    assert package.accepted is False
    assert package.status == "FAILED_VALIDATION"
    for error in [
        "MISSING_DISPATCH_RECORDS",
        "MISSING_LIFECYCLE_DECISION_REFS",
        "MISSING_RESERVATION_LEASE_REFS",
        "MISSING_MQ_TRANSPORT_REFS",
        "MISSING_RUNTIME_EVENT_REFS",
        "MISSING_RESULT_CANDIDATE_REFS",
    ]:
        assert error in package.errors


def test_phase3_transport_diagnostic_cannot_mark_pass():
    package = build_controller_bridge_evidence_package(
        _evidence(
            lifecycle_decision_refs=[],
            reservation_lease_refs=[],
            runtime_event_refs=[],
            result_candidate_refs=[],
            diagnostic_only=True,
        )
    )

    assert package.accepted is False
    assert package.status == "PARTIAL_BLOCKED"
    assert "DIAGNOSTIC_ONLY_NOT_REVIEW_READY" in package.errors
    assert package.final_pass_claimed is False
    assert package.live_readiness_claimed is False
