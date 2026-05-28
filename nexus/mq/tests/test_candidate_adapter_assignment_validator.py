import pytest

from nexus.mq.candidate_adapter_assignment_validator import (
    CandidateAssignmentEvent,
    CandidateReservationLease,
    validate_candidate_assignment,
)
from nexus.mq.candidate_adapter_profile_loader import CANDIDATE_ADAPTER_PROTOCOL_VERSION
from nexus.mq.candidate_adapter_session_store import CandidateAdapterSession


NOW = "2026-05-26T12:00:00+00:00"
RUN_ID = "uat-7-19-14-phase3-20260527T151120Z-nova"
BASE_SUBJECT = f"nexus.4_19.wbs7_19_14.{RUN_ID}.jarvis"
CANONICAL_ASSIGNMENT_SUBJECT = f"{BASE_SUBJECT}.assignment"
RUNTIME_SCOPED_ASSIGNMENT_ALIAS = f"{BASE_SUBJECT}.jarvis-runtime-001.assignment"


def _session(**overrides):
    data = {
        "session_id": "session-001",
        "agent_id": "jarvis",
        "runtime_instance_id": "jarvis-runtime-001",
        "owner_principal_id": "principal:jarvis-owner",
        "runtime_type": "candidate",
        "adapter_protocol_version": CANDIDATE_ADAPTER_PROTOCOL_VERSION,
        "broker_profile_ref": "broker-profile://nexus-distributed-uat",
        "broker_url": "nats://192.168.31.124:7422",
        "authority_scopes": ["workflow.command"],
        "capabilities": ["implementation"],
        "no_go_scope": ["no business execution"],
        "allowed_message_families": ["assignment", "evidence"],
        "allowed_subject_patterns": [CANONICAL_ASSIGNMENT_SUBJECT],
        "evidence_output_ref": "evidence://candidate-adapter/jarvis",
        "profile_digest": "digest-001",
        "registration_ref": "registry://candidate/jarvis/jarvis-runtime-001",
        "startup_packet_ref": "startup-packet://jarvis",
        "readiness_evidence_ref": "evidence://readiness/jarvis",
        "last_heartbeat_sequence": 1,
        "lifecycle_state": "idle",
    }
    data.update(overrides)
    return CandidateAdapterSession(**data)


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
        "revoked": False,
    }
    data.update(overrides)
    return CandidateReservationLease(**data)


def test_candidate_ack_requires_active_lease_and_matching_decision():
    result = validate_candidate_assignment(_assignment(), session=_session(), lease=_lease(), now_at=NOW)

    assert result.accepted is True
    assert result.errors == []


@pytest.mark.parametrize(
    "event,error",
    [
        (_assignment(lifecycle_decision_id=""), "MISSING_LIFECYCLE_DECISION_ID"),
        (_assignment(lifecycle_decision_id="decision-other"), "LIFECYCLE_DECISION_ID_MISMATCH"),
        (_assignment(reservation_lease_id=""), "MISSING_RESERVATION_LEASE_ID"),
        (_assignment(reservation_lease_id="lease-other"), "RESERVATION_LEASE_ID_MISMATCH"),
    ],
)
def test_candidate_ack_rejects_missing_or_mismatched_decision_and_lease(event, error):
    result = validate_candidate_assignment(event, session=_session(), lease=_lease(), now_at=NOW)

    assert result.accepted is False
    assert error in result.errors


@pytest.mark.parametrize(
    "lease,error",
    [
        (_lease(active=False), "RESERVATION_LEASE_INACTIVE"),
        (_lease(revoked=True), "RESERVATION_LEASE_REVOKED"),
        (_lease(expires_at="2026-05-26T11:59:59+00:00"), "RESERVATION_LEASE_EXPIRED"),
    ],
)
def test_candidate_ack_rejects_expired_revoked_or_inactive_lease(lease, error):
    result = validate_candidate_assignment(_assignment(), session=_session(), lease=lease, now_at=NOW)

    assert result.accepted is False
    assert error in result.errors


def test_candidate_ack_rejects_missing_idempotency_key():
    result = validate_candidate_assignment(_assignment(idempotency_key=""), session=_session(), lease=_lease(), now_at=NOW)

    assert result.accepted is False
    assert "MISSING_IDEMPOTENCY_KEY" in result.errors


def test_candidate_ack_rejects_subject_outside_profile_allowlist():
    result = validate_candidate_assignment(
        _assignment(assignment_subject="nexus.other.assignment.001"),
        session=_session(),
        lease=_lease(),
        now_at=NOW,
    )

    assert result.accepted is False
    assert "ASSIGNMENT_SUBJECT_NOT_ALLOWED: nexus.other.assignment.001" in result.errors


def test_candidate_ack_rejects_runtime_scoped_alias_even_with_observation_pattern():
    result = validate_candidate_assignment(
        _assignment(assignment_subject=RUNTIME_SCOPED_ASSIGNMENT_ALIAS),
        session=_session(allowed_subject_patterns=[f"{BASE_SUBJECT}.>"]),
        lease=_lease(),
        now_at=NOW,
    )

    assert result.accepted is False
    assert "ASSIGNMENT_SUBJECT_RUNTIME_ALIAS_DIAGNOSTIC_ONLY" in result.errors


def test_candidate_ack_rejects_wrong_runtime_payload():
    result = validate_candidate_assignment(
        _assignment(runtime_instance_id="other-runtime"),
        session=_session(),
        lease=_lease(),
        now_at=NOW,
    )

    assert result.accepted is False
    assert "ASSIGNMENT_RUNTIME_ID_MISMATCH" in result.errors
    assert "LEASE_RUNTIME_ID_MISMATCH" in result.errors


def test_candidate_ack_rejects_missing_not_business_completion_flag():
    result = validate_candidate_assignment(
        _assignment(not_business_completion=False),
        session=_session(),
        lease=_lease(),
        now_at=NOW,
    )

    assert result.accepted is False
    assert "ASSIGNMENT_CANNOT_BE_BUSINESS_COMPLETION" in result.errors


def test_candidate_ack_rejects_protocol_mismatch():
    result = validate_candidate_assignment(
        _assignment(adapter_protocol_version="4.19.unsupported"),
        session=_session(),
        lease=_lease(),
        now_at=NOW,
    )

    assert result.accepted is False
    assert "ADAPTER_PROTOCOL_VERSION_MISMATCH" in result.errors


def test_candidate_ack_rejects_ready_without_heartbeat():
    result = validate_candidate_assignment(
        _assignment(),
        session=_session(last_heartbeat_sequence=0, lifecycle_state="ready"),
        lease=_lease(),
        now_at=NOW,
    )

    assert result.accepted is False
    assert "MISSING_HEARTBEAT_FRESHNESS" in result.errors
    assert "SESSION_NOT_READY_FOR_ASSIGNMENT_ACK: ready" in result.errors


def test_candidate_ack_rejects_stale_session():
    result = validate_candidate_assignment(_assignment(), session=_session(lifecycle_state="stale"), lease=_lease(), now_at=NOW)

    assert result.accepted is False
    assert "SESSION_NOT_ACCEPTING_ASSIGNMENTS: stale" in result.errors


def test_candidate_drain_blocks_new_assignment_intake():
    result = validate_candidate_assignment(_assignment(), session=_session(lifecycle_state="draining"), lease=_lease(), now_at=NOW)

    assert result.accepted is False
    assert "SESSION_NOT_ACCEPTING_ASSIGNMENTS: draining" in result.errors


def test_candidate_ack_rejects_duplicate_non_idempotent_assignment():
    session = _session(active_assignment_refs=["assignment-001"], active_idempotency_keys=["idem-other"])

    result = validate_candidate_assignment(_assignment(), session=session, lease=_lease(), now_at=NOW)

    assert result.accepted is False
    assert "DUPLICATE_ASSIGNMENT_IDEMPOTENCY_CONFLICT" in result.errors
