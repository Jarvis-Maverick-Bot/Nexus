import json

from nexus.mq.resident_controller.cli import main
from nexus.mq.resident_controller.service import (
    BrokerReadinessSnapshot,
    ResidentControllerService,
    ResidentControllerServicePolicy,
    build_drain_offline_record,
    build_status_snapshot,
)
from nexus.mq.tests.test_resident_controller_config import _config


def test_resident_controller_cli_default_off():
    assert main([]) == 2
    assert main(["start-once"]) == 2


def test_resident_controller_cli_validate_config_reads_file(tmp_path):
    config_path = tmp_path / "resident.json"
    config_path.write_text(json.dumps(_config()), encoding="utf-8")
    output_path = tmp_path / "validation.json"

    exit_code = main(["validate-config", "--config", str(config_path), "--output", str(output_path)])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["valid"] is True
    assert payload["live_runtime_allowed"] is False


def test_resident_controller_cli_validate_config_reads_committed_yaml_example(tmp_path):
    output_path = tmp_path / "validation.json"

    exit_code = main(
        [
            "validate-config",
            "--config",
            "config/resident_controller.example.yaml",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["valid"] is True
    assert payload["redacted_snapshot"]["controller"]["launch_mode"] == "disabled"


def test_resident_controller_cli_validate_config_rejects_unsafe_file(tmp_path):
    config = _config()
    config["policy"]["broker_mutation_allowed"] = True
    config_path = tmp_path / "resident.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    output_path = tmp_path / "validation.json"

    exit_code = main(["validate-config", "--config", str(config_path), "--output", str(output_path)])

    assert exit_code == 1
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert "BROKER_MUTATION_NOT_AUTHORIZED" in payload["errors"]


def test_resident_controller_cli_status_writes_machine_readable_output(tmp_path):
    output_path = tmp_path / "status.json"

    exit_code = main(["status", "--output", str(output_path)])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["service_state"] == "disabled"
    assert payload["final_acceptance"] is False


def test_resident_controller_cli_drain_writes_offline_record(tmp_path):
    output_path = tmp_path / "drain.json"

    exit_code = main(
        [
            "drain",
            "--run-id",
            "run-001",
            "--reason-ref",
            "operator-window-ended",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["state"] == "offline"
    assert payload["broker_mutated"] is False


def test_resident_controller_cli_recover_classifies_checkpoint(tmp_path):
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text(
        json.dumps(
            {
                "run_id": "run-001",
                "service_state": "assignment_active",
                "pending_assignments": {"assign-001": {"idempotency_key": "idem-001"}},
                "completed_assignments": {},
                "replay_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "recovery.json"

    exit_code = main(["recover", "--checkpoint", str(checkpoint_path), "--output", str(output_path)])

    assert exit_code == 1
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["classifications"]["assign-001"] == "pending_reconciliation"


def test_resident_controller_cli_build_evidence_package_creates_manifest(tmp_path):
    output_root = tmp_path / "evidence"

    exit_code = main(["build-evidence-package", "--run-id", "run-001", "--evidence-root", str(output_root)])

    assert exit_code == 0
    assert (output_root / "manifest.json").exists()
    assert (output_root / "SHA256SUMS").exists()


def test_resident_controller_cli_start_once_outputs_route_readiness(tmp_path):
    config = _config()
    config["controller"]["launch_mode"] = "bounded_uat"
    config_path = tmp_path / "resident.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    broker_path = tmp_path / "broker.json"
    broker_path.write_text(
        json.dumps({"connected": True, "subscriptions_ready": True}),
        encoding="utf-8",
    )
    output_path = tmp_path / "start_once.json"

    exit_code = main(
        [
            "start-once",
            "--config",
            str(config_path),
            "--broker-readiness",
            str(broker_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["accepted"] is True
    assert payload["daemon_started"] is False
    assert payload["service_state"] == "route_ready"


def test_resident_controller_status_never_claims_acceptance():
    snapshot = build_status_snapshot(
        service_state="route_ready",
        broker_connected=True,
        subscriptions_ready=True,
        last_heartbeat_at="2026-05-25T00:00:00+00:00",
        pending_assignments=["assign-001"],
        evidence_root="evidence/4.19/wbs-7.19.14/resident-controller/run-001",
    )

    assert snapshot["not_business_completion"] is True
    assert snapshot["final_acceptance"] is False
    assert "PASS" not in str(snapshot)


def test_resident_controller_uat_requires_authorization():
    service = ResidentControllerService(policy=ResidentControllerServicePolicy(default_enabled=False))

    decision = service.evaluate_start(run_authorization_ref="")

    assert decision.accepted is False
    assert decision.daemon_started is False
    assert "RESIDENT_CONTROLLER_DEFAULT_OFF" in decision.errors
    assert "MISSING_UAT_AUTHORIZATION" in decision.errors


def test_resident_controller_start_once_prepares_route_without_daemon_start():
    service = ResidentControllerService(
        policy=ResidentControllerServicePolicy(default_enabled=True, uat_authorized=True)
    )

    decision = service.evaluate_start_once(
        config=_config(),
        broker=BrokerReadinessSnapshot(connected=True, subscriptions_ready=True),
        run_authorization_ref="review-evidence/nova/uat-auth.md",
    )

    assert decision.accepted is True
    assert decision.daemon_started is False
    assert decision.service_state == "route_ready"
    assert decision.evidence_records


def test_resident_controller_drain_offline_cleanup_is_local_evidence_only():
    record = build_drain_offline_record(
        run_id="run-001",
        reason_ref="operator-window-ended",
        connected=False,
        event_time="2026-05-25T00:00:00+00:00",
    )

    assert record["state"] == "offline"
    assert record["broker_mutated"] is False
    assert record["publish_attempted"] is False
    assert record["not_business_completion"] is True
