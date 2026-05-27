from nexus.mq.runtime_lifecycle_controller import (
    RuntimeEligibilityRequest,
    RuntimeLifecycleController,
    RuntimeLifecyclePolicy,
    RuntimeRegistrationRequest,
)


NOW = "2026-05-27T07:00:00+00:00"
READY_EXPIRES = "2026-05-27T08:00:00+00:00"


def _registration(**overrides):
    data = {
        "agent_id": "jarvis",
        "runtime_instance_id": "jarvis-runtime-001",
        "owner_principal_id": "principal://jarvis",
        "runtime_type": "candidate",
        "role": "implementation_agent",
        "capabilities": ["implementation"],
        "authority_scopes": ["workflow.command"],
        "privacy_scopes": ["project"],
        "allowed_task_boundaries": ["implementation"],
        "no_go_scope": ["no business execution", "no private-agent invocation"],
        "protocol_versions_supported": ["4.19.candidate_adapter.v1"],
        "trust_material_ref": "trust://jarvis",
        "profile_ref": "profile://jarvis/real-agent",
        "evidence_refs": ["evidence://register/jarvis"],
    }
    data.update(overrides)
    return RuntimeRegistrationRequest(**data)


def _eligibility_request(**overrides):
    data = {
        "request_id": "eligibility-001",
        "dispatch_run_id": "run-001",
        "assignment_id": "assignment-001",
        "idempotency_key": "idem-001",
        "source_authority_ref": "review://nova/real-agent-go",
        "target_agent_id": "jarvis",
        "target_runtime_instance_id": "jarvis-runtime-001",
        "required_capability": "implementation",
        "required_authority_scope": "workflow.command",
        "required_privacy_scope": "project",
        "allowed_task_boundary": "implementation",
        "no_go_scope": ["no business execution", "no private-agent invocation"],
        "required_protocol_version": "4.19.candidate_adapter.v1",
        "policy_hash": "policy-hash-001",
    }
    data.update(overrides)
    return RuntimeEligibilityRequest(**data)


def _ready_controller(policy=None):
    controller = RuntimeLifecycleController(policy=policy or RuntimeLifecyclePolicy())
    controller.register_runtime(_registration(), now_at=NOW)
    controller.submit_readiness(
        runtime_instance_id="jarvis-runtime-001",
        startup_packet_ref="startup://jarvis/run-001",
        readiness_evidence_ref="evidence://jarvis/readiness",
        startup_packet_expires_at=READY_EXPIRES,
        now_at=NOW,
    )
    controller.record_heartbeat(
        runtime_instance_id="jarvis-runtime-001",
        sequence=1,
        observed_at=NOW,
        load_score=0.1,
        accepting_new_work=True,
    )
    return controller


def test_runtime_lifecycle_register_ready_heartbeat_idle_flow():
    controller = _ready_controller()

    record = controller.get_runtime("jarvis-runtime-001")
    decision = controller.evaluate_eligibility(_eligibility_request(), now_at=NOW)

    assert controller.policy.heartbeat_interval_seconds == 15
    assert controller.policy.heartbeat_ttl_seconds == 60
    assert controller.policy.lease_ttl_seconds == 60
    assert controller.policy.assignment_timeout_seconds == 30
    assert record.lifecycle_state == "idle"
    assert decision.accepted is True
    assert decision.decision_id
    lease = controller.reserve_runtime(decision, assignment_id="assignment-001", now_at=NOW)
    assert lease.active is True
    assert lease.lease_id
    assert lease.lifecycle_decision_id == decision.decision_id
    assert decision.valid_until == "2026-05-27T07:00:30+00:00"
    assert lease.release_required_by == "2026-05-27T07:00:15+00:00"
    assert controller.get_runtime("jarvis-runtime-001").lifecycle_state == "reserved"


def test_runtime_lifecycle_heartbeat_never_unlocks_readiness():
    controller = RuntimeLifecycleController(policy=RuntimeLifecyclePolicy())
    controller.register_runtime(_registration(), now_at=NOW)
    controller.record_heartbeat(
        runtime_instance_id="jarvis-runtime-001",
        sequence=1,
        observed_at=NOW,
    )

    decision = controller.evaluate_eligibility(_eligibility_request(), now_at=NOW)

    assert decision.accepted is False
    assert "RUNTIME_NOT_READY" in decision.errors
    assert "READINESS_EVIDENCE_MISSING" in decision.errors


def test_runtime_control_pause_suspend_drain_revoke_blocks_dispatch():
    for action, expected_state in [
        ("pause", "paused"),
        ("suspend", "suspended"),
        ("drain", "draining"),
        ("revoke", "revoked"),
    ]:
        controller = _ready_controller()
        result = controller.apply_lifecycle_control(
            runtime_instance_id="jarvis-runtime-001",
            action=action,
            reason_ref=f"control://{action}",
            now_at=NOW,
        )

        decision = controller.evaluate_eligibility(_eligibility_request(), now_at=NOW)

        assert result.accepted is True
        assert controller.get_runtime("jarvis-runtime-001").lifecycle_state == expected_state
        assert decision.accepted is False
        assert f"LIFECYCLE_STATE_BLOCKS_ASSIGNMENT: {expected_state}" in decision.errors


def test_runtime_lifecycle_stale_heartbeat_blocks_eligibility():
    controller = _ready_controller()

    decision = controller.evaluate_eligibility(
        _eligibility_request(),
        now_at="2026-05-27T07:01:01+00:00",
    )

    assert decision.accepted is False
    assert "HEARTBEAT_STALE" in decision.errors


def test_runtime_query_eligibility_blocks_no_registered_runtime():
    controller = RuntimeLifecycleController(policy=RuntimeLifecyclePolicy())

    decision = controller.query_eligibility(_eligibility_request(), now_at=NOW)

    assert decision.accepted is False
    assert "RUNTIME_NOT_REGISTERED" in decision.errors


def test_runtime_ack_consumes_lease():
    controller = _ready_controller()
    decision = controller.query_eligibility(_eligibility_request(), now_at=NOW)
    lease = controller.reserve_capacity(decision, assignment_id="assignment-001", now_at=NOW)
    record = controller.get_runtime("jarvis-runtime-001")

    assert lease.lease_id in record.active_reservation_lease_ids
    assert record.active_assignment_ids == []

    consumed = controller.consume_reservation(lease.lease_id, consumed_at=NOW)
    record = controller.get_runtime("jarvis-runtime-001")
    blocked = controller.evaluate_eligibility(
        _eligibility_request(request_id="eligibility-002", assignment_id="assignment-002", idempotency_key="idem-002"),
        now_at=NOW,
    )

    assert consumed.status == "consumed"
    assert consumed.active is False
    assert controller.lease_status(lease.lease_id, now_at=NOW).status == "consumed"
    assert lease.lease_id not in record.active_reservation_lease_ids
    assert "assignment-001" in record.active_assignment_ids
    assert blocked.accepted is False
    assert "RUNTIME_CAPACITY_EXHAUSTED" in blocked.errors


def test_runtime_release_and_revoke_reservation():
    controller = _ready_controller()
    decision = controller.query_eligibility(_eligibility_request(), now_at=NOW)
    released_lease = controller.reserve_capacity(decision, assignment_id="assignment-001", now_at=NOW)

    released = controller.release_reservation(released_lease.lease_id, released_at=NOW, reason_ref="drain://run-001")
    released_record = controller.get_runtime("jarvis-runtime-001")
    post_release = controller.evaluate_eligibility(
        _eligibility_request(request_id="eligibility-002", assignment_id="assignment-002", idempotency_key="idem-002"),
        now_at=NOW,
    )

    assert released.status == "released"
    assert released.release_reason_ref == "drain://run-001"
    assert released_lease.lease_id not in released_record.active_reservation_lease_ids
    assert released_record.active_assignment_ids == []
    assert released_record.lifecycle_state == "idle"
    assert post_release.accepted is True

    controller = _ready_controller()
    decision = controller.query_eligibility(_eligibility_request(), now_at=NOW)
    revoked_lease = controller.reserve_capacity(decision, assignment_id="assignment-001", now_at=NOW)

    revoked = controller.revoke_reservation(revoked_lease.lease_id, revoked_at=NOW, reason_ref="control://revoke")
    revoked_record = controller.get_runtime("jarvis-runtime-001")

    assert revoked.status == "revoked"
    assert revoked.revoked is True
    assert revoked_lease.lease_id not in revoked_record.active_reservation_lease_ids
    assert revoked_record.lifecycle_state == "idle"


def test_runtime_release_after_consumed_assignment_restores_eligibility():
    controller = _ready_controller()
    decision = controller.query_eligibility(_eligibility_request(), now_at=NOW)
    lease = controller.reserve_capacity(decision, assignment_id="assignment-001", now_at=NOW)
    controller.consume_reservation(lease.lease_id, consumed_at=NOW)

    released = controller.release_reservation(lease.lease_id, released_at=NOW, reason_ref="result://assignment-001")
    record = controller.get_runtime("jarvis-runtime-001")
    post_release = controller.evaluate_eligibility(
        _eligibility_request(request_id="eligibility-002", assignment_id="assignment-002", idempotency_key="idem-002"),
        now_at=NOW,
    )

    assert released.status == "released"
    assert record.active_assignment_ids == []
    assert record.active_reservation_lease_ids == []
    assert record.lifecycle_state == "idle"
    assert post_release.accepted is True


def test_runtime_expired_reservation_reconciles_capacity_and_allows_new_eligibility():
    controller = _ready_controller(policy=RuntimeLifecyclePolicy(lease_ttl_seconds=10))
    decision = controller.query_eligibility(_eligibility_request(), now_at=NOW)
    lease = controller.reserve_capacity(decision, assignment_id="assignment-001", now_at=NOW)

    expired = controller.lease_status(lease.lease_id, now_at="2026-05-27T07:00:11+00:00")
    record = controller.get_runtime("jarvis-runtime-001")
    post_expiry = controller.evaluate_eligibility(
        _eligibility_request(request_id="eligibility-002", assignment_id="assignment-002", idempotency_key="idem-002"),
        now_at="2026-05-27T07:00:11+00:00",
    )

    assert expired.status == "expired"
    assert lease.lease_id not in record.active_reservation_lease_ids
    assert record.active_assignment_ids == []
    assert record.lifecycle_state == "idle"
    assert post_expiry.accepted is True
