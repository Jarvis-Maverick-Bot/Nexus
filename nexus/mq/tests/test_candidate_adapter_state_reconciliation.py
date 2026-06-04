from nexus.mq.candidate_adapter_api import CandidateAdapterApi, CandidateAdapterProviders, InMemoryAssignmentBroker, InMemoryLifecycleProvider
from nexus.mq.candidate_adapter_session_store import CandidateAdapterSession, CandidateAdapterSessionStore


NOW = "2026-06-04T08:00:00+00:00"


def _session():
    return CandidateAdapterSession(
        session_id="session-001",
        agent_id="jarvis",
        runtime_instance_id="jarvis-runtime-001",
        owner_principal_id="principal://jarvis",
        runtime_type="candidate",
        adapter_protocol_version="4.19.candidate_adapter.v1",
        broker_profile_ref="broker-profile://nexus-distributed-uat",
        broker_url="nats://192.168.31.124:7422",
        authority_scopes=["workflow.command"],
        capabilities=["implementation"],
        no_go_scope=["no business execution"],
        allowed_message_families=["assignment", "evidence"],
        allowed_subject_patterns=["nexus.4_19.wbs7_19_15.run-001.jarvis.assignment"],
        evidence_output_ref="evidence://candidate-adapter/jarvis",
        profile_digest="digest-001",
        active_assignment_refs=["assignment-001"],
        active_decision_ids=["decision-001"],
        active_reservation_lease_ids=["lease-001"],
        active_idempotency_keys=["idem-001"],
        lifecycle_state="assigned",
    )


def _snapshot(**overrides):
    data = {
        "snapshot_id": "snapshot-001",
        "snapshot_hash": "snapshot-hash-001",
        "stale": False,
        "stale_after": "2026-06-04T08:10:00+00:00",
        "run_id": "run-001",
        "target_agent_id": "jarvis",
        "runtime_instance_id": "jarvis-runtime-001",
        "assignment_id": "assignment-001",
        "package_name": "package-v0.1",
        "package_version": "v0.1",
        "package_verdict": "ready_for_review",
        "package_manifest_ref": "manifest://package-v0.1",
        "package_manifest_hash": "manifest-hash-001",
        "duplicate_replay_status": "suppressed",
        "lifecycle_phase": "assigned",
        "reservation_lease_status": "consumed",
        "clean_run_tuple": {
            "idempotency_key": "idem-001",
            "lifecycle_decision_id": "decision-001",
            "reservation_lease_id": "lease-001",
        },
    }
    data.update(overrides)
    return data


def _api(tmp_path, session):
    session_path = tmp_path / "session.json"
    store = CandidateAdapterSessionStore(session_path)
    store.save(session)
    return (
        CandidateAdapterApi(
            session_store=store,
            providers=CandidateAdapterProviders(
                broker=InMemoryAssignmentBroker(),
                lifecycle=InMemoryLifecycleProvider(),
            ),
        ),
        session_path,
    )


def test_candidate_run_state_reconciliation_accepts_synced_state(tmp_path):
    api, session_path = _api(tmp_path, _session())

    result = api.reconcile_run_state(
        session_path,
        platform_snapshot=_snapshot(),
        package_manifest={
            "verdict": "ready_for_review",
            "manifest_ref": "manifest://package-v0.1",
            "manifest_hash": "manifest-hash-001",
            "package_name": "package-v0.1",
            "package_version": "v0.1",
            "duplicate_replay_status": "suppressed",
            "reservation_lease_status": "consumed",
        },
        generated_at=NOW,
    )

    assert result.accepted is True
    assert result.payload["reconciliation"]["status"] == "SYNCED"
    assert result.payload["reconciliation"]["mismatches"] == []
    assert result.payload["reconciliation"]["reconciliation_record_ref"]


def test_candidate_run_state_reconciliation_blocks_divergence(tmp_path):
    api, session_path = _api(tmp_path, _session())

    result = api.reconcile_run_state(
        session_path,
        platform_snapshot=_snapshot(assignment_id="assignment-other"),
        package_manifest={
            "verdict": "ready_for_review",
            "manifest_ref": "manifest://package-v0.1",
            "manifest_hash": "manifest-hash-001",
            "package_name": "package-v0.1",
            "package_version": "v0.1",
            "duplicate_replay_status": "suppressed",
            "reservation_lease_status": "consumed",
        },
        generated_at=NOW,
    )

    assert result.accepted is False
    assert "BLOCKED_STATE_DIVERGENCE" in result.errors
    reconciliation = result.payload["reconciliation"]
    assert reconciliation["status"] == "BLOCKED"
    assert reconciliation["required_action"] == "emit_blocked"
    assert reconciliation["mismatches"][0]["field"] == "assignment_id"


def test_candidate_run_state_reconciliation_checks_snapshot_package_and_phase_fields(tmp_path):
    api, session_path = _api(tmp_path, _session())

    result = api.reconcile_run_state(
        session_path,
        platform_snapshot=_snapshot(
            package_manifest_hash="snapshot-manifest-hash-other",
            duplicate_replay_status="missing",
            lifecycle_phase="idle",
            reservation_lease_status="active",
        ),
        package_manifest={
            "verdict": "ready_for_review",
            "manifest_ref": "manifest://package-v0.1",
            "manifest_hash": "manifest-hash-001",
            "package_name": "package-v0.1",
            "package_version": "v0.1",
            "duplicate_replay_status": "suppressed",
            "reservation_lease_status": "consumed",
        },
        generated_at=NOW,
    )

    assert result.accepted is False
    fields = {item["field"] for item in result.payload["reconciliation"]["mismatches"]}
    assert "package_manifest_hash" in fields
    assert "duplicate_replay_status" in fields
    assert "lifecycle_phase" in fields
    assert "reservation_lease_status" in fields


def test_candidate_run_state_reconciliation_blocks_stale_snapshot_and_persists_record(tmp_path):
    api, session_path = _api(tmp_path, _session())

    result = api.reconcile_run_state(
        session_path,
        platform_snapshot=_snapshot(stale_after="2026-06-04T07:59:59+00:00"),
        package_manifest={
            "verdict": "ready_for_review",
            "manifest_ref": "manifest://package-v0.1",
            "manifest_hash": "manifest-hash-001",
            "package_name": "package-v0.1",
            "package_version": "v0.1",
            "duplicate_replay_status": "suppressed",
            "reservation_lease_status": "consumed",
        },
        generated_at=NOW,
    )

    reconciliation = result.payload["reconciliation"]
    record_path = reconciliation["reconciliation_record_ref"]

    assert result.accepted is False
    assert "snapshot_staleness" in {item["field"] for item in reconciliation["mismatches"]}
    assert record_path
    assert (tmp_path / record_path.split("\\")[-1]).exists()
