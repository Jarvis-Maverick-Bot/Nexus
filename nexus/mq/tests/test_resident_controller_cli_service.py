from nexus.mq.resident_controller.cli import main
from nexus.mq.resident_controller.service import (
    ResidentControllerService,
    ResidentControllerServicePolicy,
    build_drain_offline_record,
    build_status_snapshot,
)


def test_resident_controller_cli_default_off():
    assert main([]) == 2
    assert main(["start-once"]) == 2


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
