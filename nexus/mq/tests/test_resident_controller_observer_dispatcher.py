from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.eligibility_reservation_policy import RuntimeEligibilityDecision, RuntimeReservationLease
from nexus.mq.resident_controller.dispatcher import (
    ResidentControllerDispatchRequest,
    ResidentControllerDispatchPolicy,
    ResidentControllerSubjectPolicy,
    evaluate_resident_dispatch,
)
from nexus.mq.resident_controller.observer import evaluate_runtime_observation


NOW = "2026-05-25T00:00:00+00:00"


def _record(**overrides):
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
        "heartbeat_ttl_seconds": 30,
        "last_heartbeat_at": "2026-05-24T23:59:45+00:00",
        "current_assignment_refs": [],
        "protocol_versions_supported": ["4.19"],
        "trust_material_ref": "trust://jarvis",
        "startup_packet_ref": "startup://jarvis/run-001",
        "readiness_evidence_ref": "evidence://jarvis/readiness",
        "startup_packet_expires_at": "2026-05-25T01:00:00+00:00",
        "created_at": NOW,
        "updated_at": NOW,
    }
    data.update(overrides)
    return AgentRegistryRecord(**data)


def _subject_policy():
    return ResidentControllerSubjectPolicy(
        namespace="nexus.4_19.wbs7_19_14",
        run_id="run-001",
        allowed_agents=["jarvis"],
        publish_allowlist=["nexus.4_19.wbs7_19_14.*.assignment"],
    )


def _dispatch_request(**overrides):
    data = {
        "assignment_id": "assign-001",
        "idempotency_key": "idem-001",
        "run_id": "run-001",
        "wbs_id": "7.19.14.5",
        "target_agent_id": "jarvis",
        "target_runtime_instance_id": "jarvis-runtime-001",
        "assignment_kind": "non_business_probe",
        "command": "bounded_assignment",
        "source_authority_ref": "review-evidence/nova/uat-auth.md",
        "no_go_scope_ref": "no-go://7.19.14.5",
        "lifecycle_decision_id": "decision-001",
        "reservation_lease_id": "lease-001",
        "not_business_completion": True,
    }
    data.update(overrides)
    return ResidentControllerDispatchRequest(**data)


def _decision(**overrides):
    data = {
        "decision_id": "decision-001",
        "request_id": "eligibility-001",
        "dispatch_run_id": "run-001",
        "assignment_id": "assign-001",
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
        "assignment_id": "assign-001",
        "dispatch_run_id": "run-001",
        "target_runtime_instance_id": "jarvis-runtime-001",
        "active": True,
        "status": "active",
        "expires_at": "2026-05-25T00:01:00+00:00",
        "policy_hash": "policy-hash-001",
        "idempotency_key": "idem-001",
    }
    data.update(overrides)
    return RuntimeReservationLease(**data)


def test_resident_controller_observer_marks_stale_runtime_ineligible():
    observation = evaluate_runtime_observation(
        _record(last_heartbeat_at="2026-05-24T23:58:00+00:00"),
        now_at=NOW,
    )

    assert observation.dispatch_eligible is False
    assert observation.presence_state == "stale"
    assert "HEARTBEAT_STALE" in observation.errors


def test_resident_controller_dispatch_requires_non_business_scope():
    decision = evaluate_resident_dispatch(
        request=_dispatch_request(assignment_kind="business_task", not_business_completion=False),
        runtime=_record(),
        subject_policy=_subject_policy(),
        policy=ResidentControllerDispatchPolicy(dispatch_enabled=True, uat_authorized=True),
        now_at=NOW,
        lifecycle_decision=_decision(),
        reservation_lease=_lease(),
    )

    assert decision.accepted is False
    assert decision.published is False
    assert "BUSINESS_EXECUTION_NOT_AUTHORIZED" in decision.errors


def test_resident_controller_duplicate_replay_same_idempotency_key_suppressed():
    decision = evaluate_resident_dispatch(
        request=_dispatch_request(),
        runtime=_record(),
        subject_policy=_subject_policy(),
        policy=ResidentControllerDispatchPolicy(dispatch_enabled=True, uat_authorized=True),
        now_at=NOW,
        prior_idempotency_keys={"idem-001"},
        lifecycle_decision=_decision(),
        reservation_lease=_lease(),
    )

    assert decision.accepted is True
    assert decision.published is False
    assert decision.subject == "nexus.4_19.wbs7_19_14.run-001.jarvis.assignment"
    assert decision.duplicate_suppressed is True
    assert "DUPLICATE_ASSIGNMENT_SUPPRESSED" in decision.errors


def test_resident_controller_default_dispatch_policy_accepts_wbs_7_19_15_2():
    subject_policy = ResidentControllerSubjectPolicy(
        namespace="nexus.4_19.wbs7_19_15",
        run_id="run-7152",
        allowed_agents=["jarvis"],
        publish_allowlist=["nexus.4_19.wbs7_19_15.*.assignment"],
    )
    request = _dispatch_request(
        run_id="run-7152",
        wbs_id="7.19.15.2",
        assignment_kind="synthetic_business_command_acceptance",
        no_go_scope_ref="no-go://wbs-7.19.15.2",
    )
    runtime = _record(authority_scopes=["wbs://7.19.15.2"])

    decision = evaluate_resident_dispatch(
        request=request,
        runtime=runtime,
        subject_policy=subject_policy,
        policy=ResidentControllerDispatchPolicy(dispatch_enabled=True, uat_authorized=True),
        now_at=NOW,
        lifecycle_decision=_decision(dispatch_run_id="run-7152"),
        reservation_lease=_lease(dispatch_run_id="run-7152"),
    )

    assert decision.accepted is True
    assert decision.subject == "nexus.4_19.wbs7_19_15.run-7152.jarvis.assignment"
