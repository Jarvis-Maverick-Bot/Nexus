from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.eligibility_reservation_policy import RuntimeEligibilityDecision, RuntimeReservationLease
from nexus.mq.resident_controller.dispatcher import (
    ResidentControllerDispatchPolicy,
    ResidentControllerDispatchRequest,
    ResidentControllerSubjectPolicy,
    evaluate_resident_dispatch,
)


NOW = "2026-05-27T07:00:00+00:00"


def _runtime(**overrides):
    data = {
        "agent_id": "jarvis",
        "runtime_instance_id": "jarvis-runtime-001",
        "role": "implementation_agent",
        "owner_principal_id": "principal://jarvis",
        "runtime_type": "agent",
        "channel_bindings": ["nats"],
        "capabilities": ["controlled_uat_handoff_receive"],
        "authority_scopes": ["wbs://7.19.14.5"],
        "allowed_task_boundaries": ["non_business_probe"],
        "initialization_status": "ready",
        "registry_status": "active",
        "presence_state": "idle",
        "heartbeat_ttl_seconds": 60,
        "last_heartbeat_at": NOW,
        "current_assignment_refs": [],
        "protocol_versions_supported": ["4.19"],
        "trust_material_ref": "trust://jarvis",
        "startup_packet_ref": "startup://jarvis/run-001",
        "readiness_evidence_ref": "evidence://jarvis/readiness",
        "startup_packet_expires_at": "2026-05-27T08:00:00+00:00",
        "created_at": NOW,
        "updated_at": NOW,
    }
    data.update(overrides)
    return AgentRegistryRecord(**data)


def _request(**overrides):
    data = {
        "assignment_id": "assignment-001",
        "idempotency_key": "idem-001",
        "run_id": "run-001",
        "wbs_id": "7.19.14.5",
        "target_agent_id": "jarvis",
        "target_runtime_instance_id": "jarvis-runtime-001",
        "assignment_kind": "non_business_probe",
        "command": "bounded_assignment",
        "source_authority_ref": "review://nova/real-agent-go",
        "no_go_scope_ref": "no-go://real-agent",
        "lifecycle_decision_id": "decision-001",
        "reservation_lease_id": "lease-001",
        "not_business_completion": True,
    }
    data.update(overrides)
    return ResidentControllerDispatchRequest(**data)


def _subject_policy():
    return ResidentControllerSubjectPolicy(
        namespace="nexus.4_19.real_agent",
        run_id="run-001",
        allowed_agents=["jarvis"],
        publish_allowlist=["nexus.4_19.real_agent.*.assignment"],
    )


def _policy():
    return ResidentControllerDispatchPolicy(dispatch_enabled=True, uat_authorized=True)


def _decision(**overrides):
    data = {
        "decision_id": "decision-001",
        "request_id": "eligibility-001",
        "dispatch_run_id": "run-001",
        "assignment_id": "assignment-001",
        "target_agent_id": "jarvis",
        "target_runtime_instance_id": "jarvis-runtime-001",
        "accepted": True,
        "policy_hash": "policy-hash-001",
        "idempotency_key": "idem-001",
        "evidence_refs": ["evidence://decision/001"],
    }
    data.update(overrides)
    return RuntimeEligibilityDecision(**data)


def _lease(**overrides):
    data = {
        "lease_id": "lease-001",
        "lifecycle_decision_id": "decision-001",
        "assignment_id": "assignment-001",
        "dispatch_run_id": "run-001",
        "target_runtime_instance_id": "jarvis-runtime-001",
        "active": True,
        "status": "active",
        "expires_at": "2026-05-27T07:01:00+00:00",
        "policy_hash": "policy-hash-001",
        "idempotency_key": "idem-001",
    }
    data.update(overrides)
    return RuntimeReservationLease(**data)


def test_assignment_publish_requires_active_reservation_lease():
    decision = evaluate_resident_dispatch(
        request=_request(),
        runtime=_runtime(),
        subject_policy=_subject_policy(),
        policy=_policy(),
        now_at=NOW,
        lifecycle_decision=_decision(),
        reservation_lease=_lease(),
    )

    assert decision.accepted is True
    assert decision.published is False
    assert decision.lifecycle_decision_id == "decision-001"
    assert decision.reservation_lease_id == "lease-001"


def test_dispatch_blocks_missing_lifecycle_identity_before_duplicate_suppression():
    decision = evaluate_resident_dispatch(
        request=_request(lifecycle_decision_id="", reservation_lease_id=""),
        runtime=_runtime(),
        subject_policy=_subject_policy(),
        policy=_policy(),
        now_at=NOW,
        prior_idempotency_keys={"idem-001"},
        lifecycle_decision=None,
        reservation_lease=None,
    )

    assert decision.accepted is False
    assert decision.duplicate_suppressed is False
    assert "MISSING_LIFECYCLE_DECISION_ID" in decision.errors
    assert "MISSING_RESERVATION_LEASE_ID" in decision.errors
    assert "MISSING_LIFECYCLE_DECISION" in decision.errors
    assert "MISSING_RESERVATION_LEASE" in decision.errors


def test_dispatch_duplicate_replay_suppressed_only_after_lifecycle_validation():
    decision = evaluate_resident_dispatch(
        request=_request(),
        runtime=_runtime(),
        subject_policy=_subject_policy(),
        policy=_policy(),
        now_at=NOW,
        prior_idempotency_keys={"idem-001"},
        lifecycle_decision=_decision(),
        reservation_lease=_lease(),
    )

    assert decision.accepted is True
    assert decision.duplicate_suppressed is True
    assert "DUPLICATE_ASSIGNMENT_SUPPRESSED" in decision.errors


def test_heartbeat_or_route_ready_cannot_unlock_assignment_without_lifecycle_lease():
    decision = evaluate_resident_dispatch(
        request=_request(),
        runtime=_runtime(),
        subject_policy=_subject_policy(),
        policy=_policy(),
        now_at=NOW,
        lifecycle_decision=None,
        reservation_lease=None,
    )

    assert decision.accepted is False
    assert "MISSING_LIFECYCLE_DECISION" in decision.errors
    assert "MISSING_RESERVATION_LEASE" in decision.errors
