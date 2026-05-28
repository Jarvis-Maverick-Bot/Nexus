import json
import hashlib
from pathlib import Path

from nexus.mq.candidate_adapter_api import (
    CandidateAdapterApi,
    CandidateAdapterProviders,
    InMemoryAssignmentBroker,
    InMemoryLifecycleProvider,
)
from nexus.mq.candidate_adapter_assignment_validator import CandidateAssignmentEvent, CandidateReservationLease
from nexus.mq.candidate_adapter_cli import main
from nexus.mq.candidate_adapter_event_mapper import RAW_INTERNAL_PAYLOAD_KEYS
from nexus.mq.candidate_adapter_profile_loader import (
    CANDIDATE_ADAPTER_PROFILE_SCHEMA_VERSION,
    CANDIDATE_ADAPTER_PROTOCOL_VERSION,
)
from nexus.mq.candidate_adapter_session_store import CandidateAdapterSessionStore


NOW = "2026-05-26T12:00:00+00:00"
RUN_ID = "uat-7-19-14-phase3-20260527T151120Z-nova"
BASE_SUBJECT = f"nexus.4_19.wbs7_19_14.{RUN_ID}.jarvis"
CANONICAL_ASSIGNMENT_SUBJECT = f"{BASE_SUBJECT}.assignment"
RUNTIME_SCOPED_ASSIGNMENT_ALIAS = f"{BASE_SUBJECT}.jarvis-runtime-001.assignment"


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
        "allowed_subject_patterns": [CANONICAL_ASSIGNMENT_SUBJECT],
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
    heartbeat = api.heartbeat(tmp_path / "session.json", sequence=1, observed_state={"runtime_instance_id": "jarvis-runtime-001"})
    assert heartbeat.accepted is True
    return api


def _assignment(**overrides):
    data = {
        "assignment_id": "assignment-001",
        "idempotency_key": "idem-001",
        "lifecycle_decision_id": "decision-001",
        "reservation_lease_id": "lease-001",
        "assignment_subject": CANONICAL_ASSIGNMENT_SUBJECT,
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


def test_candidate_await_assignment_rejects_runtime_scoped_alias_before_candidate_output(tmp_path):
    profile = _write_profile(tmp_path, allowed_subject_patterns=[f"{BASE_SUBJECT}.>"])
    broker = InMemoryAssignmentBroker(assignments=[_assignment(assignment_subject=RUNTIME_SCOPED_ASSIGNMENT_ALIAS)])
    api = _api(tmp_path, broker=broker)
    assert api.connect(profile, session_path=tmp_path / "session.json").accepted is True
    assert api.register(tmp_path / "session.json").accepted is True
    assert api.submit_readiness(
        tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
    ).accepted is True
    assert api.heartbeat(tmp_path / "session.json", sequence=1, observed_state={"runtime_instance_id": "jarvis-runtime-001"}).accepted is True

    result = api.await_assignment(tmp_path / "session.json")

    assert result.accepted is False
    assert "ASSIGNMENT_SUBJECT_RUNTIME_ALIAS_DIAGNOSTIC_ONLY" in result.errors
    assert result.payload == {}


def test_candidate_await_assignment_serialized_result_hides_raw_assignment_payload_internals(tmp_path):
    broker = InMemoryAssignmentBroker(assignments=[_assignment(payload=_nested_raw_payload())])
    api = _connect_ready_api(tmp_path, broker=broker)

    result = api.await_assignment(tmp_path / "session.json")
    output = result.to_dict()

    assert result.accepted is True
    assignment = output["payload"]["assignment"]
    assert assignment["assignment_id"] == "assignment-001"
    assert assignment["idempotency_key"] == "idem-001"
    assert assignment["lifecycle_decision_id"] == "decision-001"
    assert assignment["reservation_lease_id"] == "lease-001"
    assert assignment["runtime_instance_id"] == "jarvis-runtime-001"
    assert assignment["adapter_protocol_version"] == CANDIDATE_ADAPTER_PROTOCOL_VERSION
    assert assignment["no_go_scope"] == ["no business execution"]
    assert assignment["payload"]["safe_input"]["title"] == "safe title"
    assert assignment["payload"]["safe_input"]["items"][0] == {"value": "keep"}
    assert assignment["payload"]["safe_input"]["items"][1] == {"nested": {"keep": "yes"}}
    _assert_no_raw_internal_keys(output)


def test_candidate_await_assignment_requires_register_readiness_and_heartbeat(tmp_path):
    broker = InMemoryAssignmentBroker(assignments=[_assignment()])
    api = _api(tmp_path, broker=broker)
    assert api.connect(_write_profile(tmp_path), session_path=tmp_path / "session.json").accepted is True

    connected = api.await_assignment(tmp_path / "session.json")
    assert connected.accepted is False
    assert "MISSING_REGISTRATION_REF" in connected.errors
    assert "SESSION_NOT_READY_FOR_ASSIGNMENT_INTAKE: connected" in connected.errors

    assert api.register(tmp_path / "session.json").accepted is True
    registered = api.await_assignment(tmp_path / "session.json")
    assert registered.accepted is False
    assert "MISSING_STARTUP_PACKET_REF" in registered.errors
    assert "SESSION_NOT_READY_FOR_ASSIGNMENT_INTAKE: registered" in registered.errors

    assert api.submit_readiness(
        tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
    ).accepted is True
    ready_without_heartbeat = api.await_assignment(tmp_path / "session.json")
    assert ready_without_heartbeat.accepted is False
    assert "MISSING_HEARTBEAT_FRESHNESS" in ready_without_heartbeat.errors
    assert "SESSION_NOT_READY_FOR_ASSIGNMENT_INTAKE: ready" in ready_without_heartbeat.errors


def test_candidate_await_assignment_rejects_stale_draining_and_offline_sessions(tmp_path):
    broker = InMemoryAssignmentBroker(assignments=[_assignment()])
    api = _connect_ready_api(tmp_path, broker=broker)
    store = CandidateAdapterSessionStore(tmp_path / "session.json")

    session = store.load()
    session.lifecycle_state = "stale"
    store.save(session)
    stale = api.await_assignment(tmp_path / "session.json")
    assert stale.accepted is False
    assert "SESSION_NOT_ACCEPTING_ASSIGNMENTS: stale" in stale.errors

    session.lifecycle_state = "draining"
    store.save(session)
    draining = api.await_assignment(tmp_path / "session.json")
    assert draining.accepted is False
    assert "SESSION_NOT_ACCEPTING_ASSIGNMENTS: draining" in draining.errors

    session.lifecycle_state = "offline"
    store.save(session)
    offline = api.await_assignment(tmp_path / "session.json")
    assert offline.accepted is False
    assert "SESSION_NOT_ACCEPTING_ASSIGNMENTS: offline" in offline.errors


def test_candidate_ack_requires_validated_assignment(tmp_path):
    lifecycle = InMemoryLifecycleProvider(leases={"lease-001": _lease()})
    api = _connect_ready_api(tmp_path, lifecycle=lifecycle)

    result = api.ack_assignment(tmp_path / "session.json", _assignment(), now_at=NOW)

    assert result.accepted is True
    assert result.payload["event"]["event_type"] == "assignment_ack"


def test_candidate_ack_duplicate_same_idempotency_suppressed_without_second_event(tmp_path):
    broker = InMemoryAssignmentBroker()
    lifecycle = InMemoryLifecycleProvider(leases={"lease-001": _lease()})
    api = _connect_ready_api(tmp_path, broker=broker, lifecycle=lifecycle)

    first = api.ack_assignment(tmp_path / "session.json", _assignment(), now_at=NOW)
    second = api.ack_assignment(tmp_path / "session.json", _assignment(), now_at=NOW)

    assert first.accepted is True
    assert second.accepted is True
    assert second.payload["duplicate_suppressed"] is True
    assert "DUPLICATE_ASSIGNMENT_SUPPRESSED" in second.errors
    assert len(broker.published_events) == 1


def test_candidate_ack_requires_register_readiness_and_heartbeat(tmp_path):
    lifecycle = InMemoryLifecycleProvider(leases={"lease-001": _lease()})
    api = _api(tmp_path, lifecycle=lifecycle)
    assert api.connect(_write_profile(tmp_path), session_path=tmp_path / "session.json").accepted is True

    connected = api.ack_assignment(tmp_path / "session.json", _assignment(), now_at=NOW)
    assert connected.accepted is False
    assert "MISSING_REGISTRATION_REF" in connected.errors
    assert "SESSION_NOT_READY_FOR_ASSIGNMENT_ACK: connected" in connected.errors

    assert api.register(tmp_path / "session.json").accepted is True
    registered = api.ack_assignment(tmp_path / "session.json", _assignment(), now_at=NOW)
    assert registered.accepted is False
    assert "MISSING_STARTUP_PACKET_REF" in registered.errors
    assert "SESSION_NOT_READY_FOR_ASSIGNMENT_ACK: registered" in registered.errors

    assert api.submit_readiness(
        tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
    ).accepted is True
    ready_without_heartbeat = api.ack_assignment(tmp_path / "session.json", _assignment(), now_at=NOW)
    assert ready_without_heartbeat.accepted is False
    assert "MISSING_HEARTBEAT_FRESHNESS" in ready_without_heartbeat.errors
    assert "SESSION_NOT_READY_FOR_ASSIGNMENT_ACK: ready" in ready_without_heartbeat.errors


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


def test_candidate_cli_ack_accepts_deterministic_lease_json_and_unblocks_post_assignment_path(tmp_path, capsys):
    profile = _write_profile(tmp_path)
    session = tmp_path / "session.json"
    assignment_path = tmp_path / "assignment.json"
    lease_path = tmp_path / "lease.json"
    assignment_path.write_text(json.dumps(_assignment().to_dict()), encoding="utf-8")
    lease_path.write_text(json.dumps(_lease().to_dict()), encoding="utf-8")

    assert main(["connect", "--profile", str(profile), "--session", str(session)]) == 0
    capsys.readouterr()
    assert main(["register", "--session", str(session)]) == 0
    capsys.readouterr()
    assert main(
        [
            "ready",
            "--session",
            str(session),
            "--startup-packet-ref",
            "startup-packet://jarvis",
            "--self-check-evidence-ref",
            "evidence://readiness/jarvis",
        ]
    ) == 0
    capsys.readouterr()
    assert main(["heartbeat", "--session", str(session), "--sequence", "1", "--runtime-instance-id", "jarvis-runtime-001"]) == 0
    capsys.readouterr()

    ack_code = main(["ack", "--session", str(session), "--assignment-json", str(assignment_path), "--lease-json", str(lease_path)])
    ack_output = json.loads(capsys.readouterr().out)
    assert ack_code == 0
    assert ack_output["accepted"] is True
    assert ack_output["payload"]["event"]["event_type"] == "assignment_ack"

    progress_code = main(["progress", "--session", str(session), "--assignment-id", "assignment-001", "--progress-ref", "progress://001"])
    progress_output = json.loads(capsys.readouterr().out)
    assert progress_code == 0
    assert progress_output["accepted"] is True

    evidence_code = main(["evidence", "--session", str(session), "--assignment-id", "assignment-001", "--evidence-ref", "evidence://001"])
    evidence_output = json.loads(capsys.readouterr().out)
    assert evidence_code == 0
    assert evidence_output["accepted"] is True

    result_code = main(
        [
            "result",
            "--session",
            str(session),
            "--assignment-id",
            "assignment-001",
            "--result-ref",
            "result://candidate",
            "--evidence-ref",
            "evidence://result",
        ]
    )
    result_output = json.loads(capsys.readouterr().out)
    assert result_code == 0
    assert result_output["accepted"] is True
    assert result_output["payload"]["event"]["status"] == "candidate"


def test_candidate_cli_await_assignment_output_hides_raw_assignment_payload_internals(tmp_path, capsys, monkeypatch):
    import nexus.mq.candidate_adapter_cli as cli

    profile = _write_profile(tmp_path)
    session = tmp_path / "session.json"
    assignment = _assignment(payload=_nested_raw_payload())

    assert main(["connect", "--profile", str(profile), "--session", str(session)]) == 0
    capsys.readouterr()
    assert main(["register", "--session", str(session)]) == 0
    capsys.readouterr()
    assert main(
        [
            "ready",
            "--session",
            str(session),
            "--startup-packet-ref",
            "startup-packet://jarvis",
            "--self-check-evidence-ref",
            "evidence://readiness/jarvis",
        ]
    ) == 0
    capsys.readouterr()
    assert main(["heartbeat", "--session", str(session), "--sequence", "1", "--runtime-instance-id", "jarvis-runtime-001"]) == 0
    capsys.readouterr()

    monkeypatch.setattr(cli, "InMemoryAssignmentBroker", lambda: InMemoryAssignmentBroker(assignments=[assignment]))
    await_code = main(["await-assignment", "--session", str(session)])
    output = json.loads(capsys.readouterr().out)

    assert await_code == 0
    assert output["accepted"] is True
    assert output["payload"]["assignment"]["assignment_id"] == "assignment-001"
    assert output["payload"]["assignment"]["lifecycle_decision_id"] == "decision-001"
    assert output["payload"]["assignment"]["reservation_lease_id"] == "lease-001"
    assert output["payload"]["assignment"]["payload"]["safe_input"]["title"] == "safe title"
    _assert_no_raw_internal_keys(output)


def test_candidate_adapter_evidence_manifest_uses_relative_existing_paths_and_current_hashes():
    evidence_dir = (
        Path(__file__).resolve().parents[3]
        / "evidence"
        / "4.19"
        / "candidate-adapter"
        / "implementation-2026-05-26-thunder"
    )
    manifest = evidence_dir / "SHA256SUMS.txt"

    assert manifest.exists()
    lines = [line for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    for line in lines:
        expected, relative_path = line.split("  ", 1)
        assert not Path(relative_path).is_absolute()
        target = evidence_dir / relative_path
        assert target.exists()
        content = target.read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(content).hexdigest() == expected


def _nested_raw_payload():
    return {
        "safe_input": {
            "title": "safe title",
            "raw_envelope": {"transport": "hidden"},
            "headers": {"x-nexus": "hidden"},
            "items": [
                {"value": "keep", "nats_subject": "internal.subject"},
                {"nested": {"keep": "yes", "reply_to": "internal.reply"}},
            ],
            "message_package": {"payload": "hidden"},
        },
        "raw_message": {"hidden": True},
        "safe_ref": "candidate-safe://ref",
    }


def _assert_no_raw_internal_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            assert key not in RAW_INTERNAL_PAYLOAD_KEYS
            _assert_no_raw_internal_keys(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_raw_internal_keys(item)
