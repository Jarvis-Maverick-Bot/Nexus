from nexus.mq.controller_bridge_models import DispatchRun
from nexus.mq.controller_bridge_state_store import ControllerBridgeStateStore
from nexus.mq.durable_state import DurableStateStore
from nexus.mq.eligibility_reservation_policy import RuntimeEligibilityDecision, RuntimeReservationLease


NOW = "2026-05-27T12:00:00+00:00"


def _store(path):
    return ControllerBridgeStateStore(DurableStateStore(str(path)))


def _run():
    return DispatchRun(
        dispatch_run_id="run-001",
        decision_id="decision-001",
        dispatch_packet_ref="dispatch-packet://controller-bridge/run-001",
        source_hash="source-hash-001",
        owner_principal_id="principal://alex",
        target_agent_id="jarvis",
        target_runtime_instance_id="jarvis-runtime-001",
        target_runtime_role="implementation_agent",
        assignment_id="assignment-001",
        assignment_ttl_seconds=30,
        idempotency_key="idem-001",
        evidence_required=["dispatch", "lifecycle", "lease"],
        status="source_bound",
        created_at=NOW,
    )


def _decision():
    return RuntimeEligibilityDecision(
        decision_id="runtime-decision-001",
        request_id="eligibility-001",
        dispatch_run_id="run-001",
        assignment_id="assignment-001",
        target_agent_id="jarvis",
        target_runtime_instance_id="jarvis-runtime-001",
        accepted=True,
        policy_hash="policy-hash-001",
        idempotency_key="idem-001",
        valid_until="2026-05-27T12:00:30+00:00",
    )


def _lease():
    return RuntimeReservationLease(
        lease_id="lease-001",
        lifecycle_decision_id="runtime-decision-001",
        assignment_id="assignment-001",
        dispatch_run_id="run-001",
        target_runtime_instance_id="jarvis-runtime-001",
        active=True,
        status="active",
        expires_at="2026-05-27T12:01:00+00:00",
        policy_hash="policy-hash-001",
        idempotency_key="idem-001",
        release_required_by="2026-05-27T12:00:15+00:00",
    )


def test_controller_bridge_state_store_persists_restart_replay_records(tmp_path):
    db_path = tmp_path / "bridge.sqlite3"
    store = _store(db_path)

    store.record_dispatch_run(_run())
    store.record_lifecycle_decision(_decision())
    store.record_reservation_lease(_lease())
    store.record_evidence_ref("run-001", "dispatch", "evidence://dispatch/run-001")
    store.record_replay("publish", "idem-001", "message-001", {"accepted": True})
    store.close()

    reopened = _store(db_path)

    assert reopened.get_dispatch_run("run-001").decision_id == "decision-001"
    assert reopened.get_lifecycle_decision("runtime-decision-001").valid_until == "2026-05-27T12:00:30+00:00"
    assert reopened.get_reservation_lease("lease-001").release_required_by == "2026-05-27T12:00:15+00:00"
    assert reopened.get_replay("publish", "idem-001").result_detail["accepted"] is True
    assert reopened.list_evidence_refs("run-001") == ["evidence://dispatch/run-001"]
    reopened.close()
