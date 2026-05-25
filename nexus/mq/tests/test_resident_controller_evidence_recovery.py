import json

from nexus.mq.resident_controller.evidence import (
    ResidentEvidenceRecord,
    build_evidence_package,
)
from nexus.mq.resident_controller.recovery import (
    ResidentControllerCheckpoint,
    classify_restart_recovery,
)


def test_resident_controller_evidence_manifest_requires_raw_records(tmp_path):
    result = build_evidence_package(
        run_id="run-001",
        evidence_root=tmp_path,
        records=[],
        status_summary={"service_state": "stopped", "not_business_completion": True},
    )

    assert result.review_ready is False
    assert "MISSING_RAW_EVIDENCE_RECORDS" in result.errors


def test_resident_controller_evidence_manifest_writes_checksums(tmp_path):
    result = build_evidence_package(
        run_id="run-001",
        evidence_root=tmp_path,
        records=[
            ResidentEvidenceRecord(
                sequence=1,
                record_type="status",
                event_time="2026-05-25T00:00:00+00:00",
                payload={"service_state": "route_ready", "not_business_completion": True},
            )
        ],
        status_summary={"service_state": "review_ready", "not_business_completion": True},
    )

    assert result.review_ready is True
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "SHA256SUMS").exists()
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "run-001"
    assert manifest["not_business_completion"] is True
    assert manifest["checksums"]["events.jsonl"].startswith("sha256:")


def test_resident_controller_secret_scan_blocks_package(tmp_path):
    result = build_evidence_package(
        run_id="run-001",
        evidence_root=tmp_path,
        records=[
            ResidentEvidenceRecord(
                sequence=1,
                record_type="status",
                event_time="2026-05-25T00:00:00+00:00",
                payload={"note": "token=" + "abc123"},
            )
        ],
        status_summary={"service_state": "blocked", "not_business_completion": True},
    )

    assert result.review_ready is False
    assert any(error.startswith("SECRET_MATERIAL_VALUE") for error in result.errors)


def test_resident_controller_restart_classifies_inflight_before_replay():
    checkpoint = ResidentControllerCheckpoint(
        run_id="run-001",
        service_state="assignment_active",
        pending_assignments={"assign-001": {"idempotency_key": "idem-001"}},
        completed_assignments={},
        replay_allowed=False,
    )

    result = classify_restart_recovery(checkpoint)

    assert result.replay_allowed is False
    assert result.classifications["assign-001"] == "pending_reconciliation"
    assert "REPLAY_BLOCKED_PENDING_RECONCILIATION" in result.errors
