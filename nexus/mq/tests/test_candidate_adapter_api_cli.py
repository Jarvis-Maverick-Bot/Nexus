import json

from nexus.mq.candidate_adapter_api import (
    CandidateAdapterApi,
    CandidateAdapterProviders,
    InMemoryAssignmentBroker,
    InMemoryLifecycleProvider,
)
from nexus.mq.candidate_adapter_assignment_validator import CandidateAssignmentEvent, CandidateReservationLease
from nexus.mq.candidate_adapter_cli import main
from nexus.mq.candidate_adapter_profile_loader import (
    CANDIDATE_ADAPTER_PROFILE_SCHEMA_VERSION,
    CANDIDATE_ADAPTER_PROTOCOL_VERSION,
)
from nexus.mq.candidate_adapter_session_store import CandidateAdapterSessionStore


NOW = "2026-05-26T12:00:00+00:00"


def _write_profile(tmp_path, **overrides):
    data = {
        "profile_schema_version": CANDIDATE_ADAPTER_PROFILE_SCHEMA_VERSION,
        "adapter_protocol_version": CANDIDATE_ADAPTER_PROTOCOL_VERSION,
        "agent_id": "jarvis",
        "runtime_instance_id": "jarvis-runtime-001",
        "owner_principal_id": "principal:jarvis-owner",
        "runtime_type": "candidate",
        "role": "implementation",
        "capabilities": ["implementation"],
        "authority_scopes": ["workflow.command"],
        "privacy_scopes": ["project"],
        "no_go_scope": ["no business execution"],
        "broker_profile_ref": "broker-profile://nexus-distributed-uat",
        "broker_url": "nats://192.168.31.124:7422",
        "allowed_subject_patterns": ["nexus.candidate.jarvis.assignment.*"],
        "allowed_message_families": ["assignment", "evidence"],
        "evidence_output_ref": str(tmp_path / "candidate-evidence"),
        "trust_material_ref": "trust-ref://jarvis",
        "credential_ref": "credential-ref://nats/jarvis",
    }
    data.update(overrides)
    path = tmp_path / f"profile-{len(list(tmp_path.glob('profile-*.json')))}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _api(tmp_path, *, broker=None, lifecycle=None):
    store = CandidateAdapterSessionStore(tmp_path / "session.json")
    return CandidateAdapterApi(
        session_store=store,
        providers=CandidateAdapterProviders(
            broker=broker or InMemoryAssignmentBroker(),
            lifecycle=lifecycle or InMemoryLifecycleProvider(),
        ),
    )


def _connect_ready_api(tmp_path, *, broker=None, lifecycle=None):
    api = _api(tmp_path, broker=broker, lifecycle=lifecycle)
    connect = api.connect(_write_profile(tmp_path), session_path=tmp_path / "session.json")
    assert connect.accepted is True
    register = api.register(tmp_path / "session.json")
    assert register.accepted is True
    ready = api.submit_readiness(
        tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
    )
    assert ready.accepted is True
    return api


def _assignment(**overrides):
    data = {
        "assignment_id": "assignment-001",
        "idempotency_key": "idem-001",
        "lifecycle_decision_id": "decision-001",
        "reservation_lease_id": "lease-001",
        "assignment_subject": "nexus.candidate.jarvis.assignment.001",
        "agent_id": "jarvis",
        "runtime_instance_id": "jarvis-runtime-001",
        "adapter_protocol_version": CANDIDATE_ADAPTER_PROTOCOL_VERSION,
        "no_go_scope": ["no business execution"],
        "payload": {"task_ref": "task://001"},
    }
    data.update(overrides)
    return CandidateAssignmentEvent(**data)


def _lease(**overrides):
    data = {
        "lease_id": "lease-001",
        "lifecycle_decision_id": "decision-001",
        "assignment_id": "assignment-001",
        "runtime_instance_id": "jarvis-runtime-001",
        "active": True,
        "expires_at": "2026-05-26T12:05:00+00:00",
    }
    data.update(overrides)
    return CandidateReservationLease(**data)


def test_candidate_connect_does_not_use_openclaw_4222_without_local_authorization(tmp_path):
    api = _api(tmp_path)

    result = api.connect(_write_profile(tmp_path, broker_url="nats://openclaw.local:4222"), session_path=tmp_path / "session.json")

    assert result.accepted is False
    assert "BROKER_ENDPOINT_FORBIDDEN_FOR_DISTRIBUTED_UAT: openclaw.local:4222" in result.errors


def test_candidate_register_requires_owner_trust_and_protocol_version(tmp_path):
    api = _api(tmp_path)
    connect = api.connect(_write_profile(tmp_path, trust_material_ref="", adapter_protocol_version="4.19.unsupported"), session_path=tmp_path / "session.json")

    assert connect.accepted is False
    assert "MISSING_PROFILE_FIELD: trust_material_ref" in connect.errors
    assert "UNSUPPORTED_ADAPTER_PROTOCOL_VERSION: 4.19.unsupported" in connect.errors


def test_candidate_readiness_requires_startup_packet_and_self_check_evidence(tmp_path):
    api = _api(tmp_path)
    assert api.connect(_write_profile(tmp_path), session_path=tmp_path / "session.json").accepted is True
    assert api.register(tmp_path / "session.json").accepted is True

    result = api.submit_readiness(tmp_path / "session.json", startup_packet_ref="", self_check_evidence_ref="")

    assert result.accepted is False
    assert "MISSING_STARTUP_PACKET_REF" in result.errors
    assert "MISSING_SELF_CHECK_EVIDENCE_REF" in result.errors


def test_candidate_heartbeat_rejects_identity_mismatch_or_sequence_regression(tmp_path):
    api = _connect_ready_api(tmp_path)

    first = api.heartbeat(tmp_path / "session.json", sequence=2, observed_state={"runtime_instance_id": "jarvis-runtime-001"})
    mismatch = api.heartbeat(tmp_path / "session.json", sequence=3, observed_state={"runtime_instance_id": "other-runtime"})
    regression = api.heartbeat(tmp_path / "session.json", sequence=1, observed_state={"runtime_instance_id": "jarvis-runtime-001"})

    assert first.accepted is True
    assert mismatch.accepted is False
    assert "HEARTBEAT_RUNTIME_IDENTITY_MISMATCH" in mismatch.errors
    assert regression.accepted is False
    assert "HEARTBEAT_SEQUENCE_REGRESSION" in regression.errors


def test_candidate_await_assignment_only_accepts_allowlisted_subjects(tmp_path):
    broker = InMemoryAssignmentBroker(assignments=[_assignment(assignment_subject="nexus.other.assignment.001")])
    api = _connect_ready_api(tmp_path, broker=broker)

    result = api.await_assignment(tmp_path / "session.json")

    assert result.accepted is False
    assert "ASSIGNMENT_SUBJECT_NOT_ALLOWED: nexus.other.assignment.001" in result.errors


def test_candidate_ack_requires_validated_assignment(tmp_path):
    lifecycle = InMemoryLifecycleProvider(leases={"lease-001": _lease()})
    api = _connect_ready_api(tmp_path, lifecycle=lifecycle)

    result = api.ack_assignment(tmp_path / "session.json", _assignment(), now_at=NOW)

    assert result.accepted is True
    assert result.payload["event"]["event_type"] == "assignment_ack"


def test_candidate_progress_and_evidence_require_active_assignment(tmp_path):
    api = _connect_ready_api(tmp_path)

    progress = api.report_progress(tmp_path / "session.json", assignment_id="assignment-001", progress_ref="progress://001")
    evidence = api.report_evidence(tmp_path / "session.json", assignment_id="assignment-001", evidence_ref="evidence://001")

    assert progress.accepted is False
    assert "ASSIGNMENT_NOT_ACTIVE: assignment-001" in progress.errors
    assert evidence.accepted is False
    assert "ASSIGNMENT_NOT_ACTIVE: assignment-001" in evidence.errors


def test_candidate_result_candidate_requires_active_assignment_and_evidence(tmp_path):
    lifecycle = InMemoryLifecycleProvider(leases={"lease-001": _lease()})
    api = _connect_ready_api(tmp_path, lifecycle=lifecycle)
    assert api.ack_assignment(tmp_path / "session.json", _assignment(), now_at=NOW).accepted is True

    result = api.report_result_candidate(tmp_path / "session.json", assignment_id="assignment-001", result_ref="result://candidate", evidence_ref="evidence://result")

    assert result.accepted is True
    assert result.payload["event"]["event_type"] == "result_candidate"
    assert result.payload["event"]["status"] == "candidate"
    assert result.payload["event"]["not_business_completion"] is True


def test_candidate_offline_requires_final_evidence_ref(tmp_path):
    api = _connect_ready_api(tmp_path)

    result = api.offline(tmp_path / "session.json", final_evidence_ref="")

    assert result.accepted is False
    assert "OFFLINE_REQUIRES_FINAL_EVIDENCE_REF" in result.errors


def test_candidate_cli_commands_emit_non_secret_json_status(tmp_path, capsys):
    profile = _write_profile(tmp_path)
    session = tmp_path / "session.json"

    code = main(["connect", "--profile", str(profile), "--session", str(session)])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["accepted"] is True
    assert output["operation"] == "connect"
    assert "token" not in json.dumps(output).lower()
    assert "password" not in json.dumps(output).lower()
