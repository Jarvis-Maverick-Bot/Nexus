import pytest

from nexus.mq.candidate_adapter_assignment_validator import CandidateAssignmentEvent
from nexus.mq.candidate_adapter_event_mapper import (
    build_candidate_action_event,
    map_assignment_to_candidate_event,
)
from nexus.mq.candidate_adapter_profile_loader import CANDIDATE_ADAPTER_PROTOCOL_VERSION
from nexus.mq.candidate_adapter_session_store import CandidateAdapterSession


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
        "allowed_subject_patterns": ["nexus.candidate.jarvis.assignment.*"],
        "evidence_output_ref": "evidence://candidate-adapter/jarvis",
        "profile_digest": "digest-001",
        "lifecycle_state": "ready",
    }
    data.update(overrides)
    return CandidateAdapterSession(**data)


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
        "payload": {
            "task_ref": "task://001",
            "safe_input": {"title": "Implement bounded adapter"},
            "raw_envelope": {"internal": "do-not-expose"},
            "nats_subject": "internal.subject",
            "reply_to": "internal.reply",
        },
    }
    data.update(overrides)
    return CandidateAssignmentEvent(**data)


def test_assignment_event_hides_raw_nexus_message_internals():
    event = map_assignment_to_candidate_event(_assignment(), session=_session())

    assert event.event_type == "assignment_available"
    assert event.payload == {"task_ref": "task://001", "safe_input": {"title": "Implement bounded adapter"}}
    assert "raw_envelope" not in event.to_dict()["payload"]
    assert "nats_subject" not in event.to_dict()["payload"]
    assert "reply_to" not in event.to_dict()["payload"]


def test_ack_progress_evidence_and_result_candidate_map_to_candidate_safe_events():
    session = _session(active_assignment_refs=["assignment-001"])

    ack = build_candidate_action_event("assignment_ack", session=session, assignment_id="assignment-001", evidence_refs=["evidence://ack"])
    progress = build_candidate_action_event("progress", session=session, assignment_id="assignment-001", payload={"status": "running"}, evidence_refs=["evidence://progress"])
    evidence = build_candidate_action_event("evidence", session=session, assignment_id="assignment-001", evidence_refs=["evidence://artifact"])
    result = build_candidate_action_event("result_candidate", session=session, assignment_id="assignment-001", payload={"summary_ref": "result://candidate"})

    assert [event.event_type for event in (ack, progress, evidence, result)] == [
        "assignment_ack",
        "progress",
        "evidence",
        "result_candidate",
    ]
    assert all(event.not_business_completion is True for event in (ack, progress, evidence, result))


def test_result_candidate_is_not_business_acceptance():
    session = _session(active_assignment_refs=["assignment-001"])

    event = build_candidate_action_event(
        "result_candidate",
        session=session,
        assignment_id="assignment-001",
        payload={"business_acceptance": True},
    )

    assert event.status == "candidate"
    assert event.payload["business_acceptance"] is False
    assert event.not_business_completion is True


def test_rejected_assignment_maps_reason_and_evidence_ref():
    event = build_candidate_action_event(
        "assignment_rejected",
        session=_session(),
        assignment_id="assignment-001",
        payload={"reason": "LEASE_EXPIRED"},
        evidence_refs=["evidence://reject"],
    )

    assert event.status == "rejected"
    assert event.payload["reason"] == "LEASE_EXPIRED"
    assert event.evidence_refs == ["evidence://reject"]


def test_offline_requires_final_evidence_ref():
    with pytest.raises(ValueError) as excinfo:
        build_candidate_action_event("offline", session=_session(), evidence_refs=[])

    assert "OFFLINE_REQUIRES_FINAL_EVIDENCE_REF" in str(excinfo.value)
