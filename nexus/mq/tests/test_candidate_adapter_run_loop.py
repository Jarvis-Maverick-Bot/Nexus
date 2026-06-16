from nexus.mq.candidate_adapter_api import (
    CandidateAdapterApi,
    CandidateAdapterProviders,
    InMemoryAssignmentBroker,
    InMemoryLifecycleProvider,
)
from nexus.mq.candidate_adapter_assignment_validator import CandidateAssignmentEvent, CandidateReservationLease
from nexus.mq.candidate_adapter_profile_loader import (
    CANDIDATE_ADAPTER_PROFILE_SCHEMA_VERSION,
    CANDIDATE_ADAPTER_PROTOCOL_VERSION,
)
from nexus.mq.candidate_adapter_run_loop import run_candidate_adapter_loop
from nexus.mq.candidate_adapter_session_store import CandidateAdapterSessionStore

import json


NOW = "2026-05-26T12:00:00+00:00"
RUN_ID = "uat-7-19-14-phase3-20260527T151120Z-nova"
BASE_SUBJECT = f"nexus.4_19.wbs7_19_14.{RUN_ID}.jarvis"
CANONICAL_ASSIGNMENT_SUBJECT = f"{BASE_SUBJECT}.assignment"
CANONICAL_DUPLICATE_REPLAY_SUBJECT = f"{CANONICAL_ASSIGNMENT_SUBJECT}.duplicate_replay"
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
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


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


def _api(tmp_path, *, assignments=None, leases=None):
    return CandidateAdapterApi(
        session_store=CandidateAdapterSessionStore(tmp_path / "session.json"),
        providers=CandidateAdapterProviders(
            broker=InMemoryAssignmentBroker(assignments=list(assignments or [])),
            lifecycle=InMemoryLifecycleProvider(leases=dict(leases or {})),
        ),
    )


def test_run_loop_connect_register_readiness_heartbeat_sequence(tmp_path):
    api = _api(tmp_path)

    result = run_candidate_adapter_loop(
        api,
        profile_path=_write_profile(tmp_path),
        session_path=tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
        heartbeat_sequence=1,
        now_at=NOW,
        max_assignments=0,
    )

    assert result.accepted is True
    assert result.trace == ["connect", "register", "ready", "heartbeat"]


def test_run_loop_await_assignment_ack_progress_evidence_result_candidate(tmp_path):
    api = _api(tmp_path, assignments=[_assignment()], leases={"lease-001": _lease()})

    result = run_candidate_adapter_loop(
        api,
        profile_path=_write_profile(tmp_path),
        session_path=tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
        heartbeat_sequence=1,
        now_at=NOW,
        max_assignments=1,
        progress_ref="progress://001",
        evidence_ref="evidence://001",
        result_ref="result://candidate",
        final_evidence_ref="evidence://offline",
    )

    assert result.accepted is True
    assert result.trace == [
        "connect",
        "register",
        "ready",
        "heartbeat",
        "await_assignment",
        "ack",
        "progress",
        "evidence",
        "result_candidate",
        "drain",
        "offline",
    ]
    assert result.not_business_completion is True


def test_run_loop_suppresses_duplicate_replay_without_second_workflow(tmp_path):
    api = _api(
        tmp_path,
        assignments=[
            _assignment(),
            _assignment(assignment_subject=CANONICAL_DUPLICATE_REPLAY_SUBJECT),
        ],
        leases={"lease-001": _lease()},
    )

    result = run_candidate_adapter_loop(
        api,
        profile_path=_write_profile(
            tmp_path,
            allowed_subject_patterns=[
                CANONICAL_ASSIGNMENT_SUBJECT,
                CANONICAL_DUPLICATE_REPLAY_SUBJECT,
            ],
        ),
        session_path=tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
        heartbeat_sequence=1,
        now_at=NOW,
        max_assignments=2,
        progress_ref="progress://001",
        evidence_ref="evidence://001",
        result_ref="result://candidate",
        final_evidence_ref="evidence://offline",
    )

    assert result.accepted is True
    assert result.trace == [
        "connect",
        "register",
        "ready",
        "heartbeat",
        "await_assignment",
        "ack",
        "progress",
        "evidence",
        "result_candidate",
        "await_assignment",
        "ack",
        "duplicate_replay_suppressed",
        "drain",
        "offline",
    ]
    assert api.providers.broker.await_calls == 2
    assert len(api.providers.broker.published_events) == 1


def test_run_loop_rejects_runtime_scoped_alias_before_ack(tmp_path):
    api = _api(
        tmp_path,
        assignments=[_assignment(assignment_subject=RUNTIME_SCOPED_ASSIGNMENT_ALIAS)],
        leases={"lease-001": _lease()},
    )

    result = run_candidate_adapter_loop(
        api,
        profile_path=_write_profile(tmp_path, allowed_subject_patterns=[f"{BASE_SUBJECT}.>"]),
        session_path=tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
        heartbeat_sequence=1,
        now_at=NOW,
        max_assignments=1,
    )

    assert result.accepted is False
    assert "ASSIGNMENT_SUBJECT_RUNTIME_ALIAS_DIAGNOSTIC_ONLY" in result.errors
    assert "ack" not in result.trace


def test_run_loop_rejects_assignment_before_ack_when_decision_missing(tmp_path):
    api = _api(tmp_path, assignments=[_assignment(lifecycle_decision_id="")], leases={"lease-001": _lease()})

    result = run_candidate_adapter_loop(
        api,
        profile_path=_write_profile(tmp_path),
        session_path=tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
        heartbeat_sequence=1,
        now_at=NOW,
        max_assignments=1,
    )

    assert result.accepted is False
    assert "MISSING_LIFECYCLE_DECISION_ID" in result.errors
    assert "ack" not in result.trace


def test_run_loop_rejects_assignment_before_ack_when_lease_missing(tmp_path):
    api = _api(tmp_path, assignments=[_assignment(reservation_lease_id="")], leases={})

    result = run_candidate_adapter_loop(
        api,
        profile_path=_write_profile(tmp_path),
        session_path=tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
        heartbeat_sequence=1,
        now_at=NOW,
        max_assignments=1,
    )

    assert result.accepted is False
    assert "MISSING_RESERVATION_LEASE_ID" in result.errors
    assert "ack" not in result.trace


def test_run_loop_uses_injected_fake_broker_and_lifecycle_provider(tmp_path):
    broker = InMemoryAssignmentBroker(assignments=[_assignment()])
    lifecycle = InMemoryLifecycleProvider(leases={"lease-001": _lease()})
    api = CandidateAdapterApi(
        session_store=CandidateAdapterSessionStore(tmp_path / "session.json"),
        providers=CandidateAdapterProviders(broker=broker, lifecycle=lifecycle),
    )

    result = run_candidate_adapter_loop(
        api,
        profile_path=_write_profile(tmp_path),
        session_path=tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
        heartbeat_sequence=1,
        now_at=NOW,
        max_assignments=1,
        progress_ref="progress://001",
        evidence_ref="evidence://001",
        result_ref="result://candidate",
        final_evidence_ref="evidence://offline",
    )

    assert result.accepted is True
    assert broker.await_calls == 1
    assert lifecycle.lookups == ["lease-001"]


def test_run_loop_drain_stops_new_assignment_intake(tmp_path):
    api = _api(tmp_path, assignments=[_assignment(), _assignment(assignment_id="assignment-002")], leases={"lease-001": _lease()})

    result = run_candidate_adapter_loop(
        api,
        profile_path=_write_profile(tmp_path),
        session_path=tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
        heartbeat_sequence=1,
        now_at=NOW,
        max_assignments=1,
        progress_ref="progress://001",
        evidence_ref="evidence://001",
        result_ref="result://candidate",
        final_evidence_ref="evidence://offline",
    )
    blocked = api.await_assignment(tmp_path / "session.json")

    assert result.accepted is True
    assert blocked.accepted is False
    assert "SESSION_NOT_ACCEPTING_ASSIGNMENTS: offline" in blocked.errors


def test_run_loop_offline_emits_final_evidence_ref(tmp_path):
    api = _api(tmp_path)

    result = run_candidate_adapter_loop(
        api,
        profile_path=_write_profile(tmp_path),
        session_path=tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
        heartbeat_sequence=1,
        now_at=NOW,
        max_assignments=0,
        final_evidence_ref="evidence://offline",
        offline_after_idle=True,
    )

    assert result.accepted is True
    assert "offline" in result.trace
    assert result.payload["offline_event"]["evidence_refs"] == ["evidence://offline"]


def test_run_loop_never_claims_business_acceptance_or_pass(tmp_path):
    api = _api(tmp_path, assignments=[_assignment()], leases={"lease-001": _lease()})

    result = run_candidate_adapter_loop(
        api,
        profile_path=_write_profile(tmp_path),
        session_path=tmp_path / "session.json",
        startup_packet_ref="startup-packet://jarvis",
        self_check_evidence_ref="evidence://readiness/jarvis",
        heartbeat_sequence=1,
        now_at=NOW,
        max_assignments=1,
        progress_ref="progress://001",
        evidence_ref="evidence://001",
        result_ref="result://candidate",
        final_evidence_ref="evidence://offline",
    )

    assert result.accepted is True
    assert result.not_business_completion is True
    assert "PASS" not in str(result.payload)
    assert "business_acceptance" not in str(result.payload)
