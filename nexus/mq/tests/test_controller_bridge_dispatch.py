from nexus.mq.controller_bridge_dispatch import ControllerBridgeDispatchController
from nexus.mq.controller_bridge_models import Layer1ApprovedDecision, RuntimeResultCandidate
from nexus.mq.controller_bridge_state_store import ControllerBridgeStateStore
from nexus.mq.durable_state import DurableStateStore
from nexus.mq.eligibility_reservation_policy import RuntimeEligibilityDecision, RuntimeReservationLease


NOW = "2026-05-27T12:00:00+00:00"
CANONICAL_ASSIGNMENT_SUBJECT = "nexus.4_19.wbs7_19_14.run-001.jarvis.assignment"
RUNTIME_SCOPED_ASSIGNMENT_ALIAS = "nexus.4_19.wbs7_19_14.run-001.jarvis.jarvis-runtime-001.assignment"
WBS_7_19_15_ASSIGNMENT_SUBJECT = (
    "nexus.4_19.wbs7_19_15.wbs-7-19-15-2-jarvis-business-command-20260603T081653Z.jarvis.assignment"
)
THUNDER_ASSIGNMENT_SUBJECT = (
    "nexus.4_19.wbs7_19_15.wbs-7-19-15-3-thunder-codex-app-business-command-20260603T081653Z.thunder_codex_app.assignment"
)


def _store(tmp_path):
    return ControllerBridgeStateStore(DurableStateStore(str(tmp_path / "bridge.sqlite3")))


def _controller(tmp_path):
    return ControllerBridgeDispatchController(state_store=_store(tmp_path))


def _decision(**overrides):
    data = {
        "decision_id": "decision-001",
        "decision_authority_ref": "review://nova/controller-bridge",
        "owner_principal_id": "principal://alex",
        "work_class": "non_business_probe",
        "source_refs": {"shared_docs_commit": "c3ef7b3", "pre_edit_head": "a6b6943"},
        "dispatch_packet_ref": "dispatch-packet://controller-bridge/run-001",
        "target_agent_id": "jarvis",
        "target_runtime_instance_id": "jarvis-runtime-001",
        "target_runtime_role": "implementation_agent",
        "allowed_runtime_roles": ["implementation_agent"],
        "required_capability": "implementation",
        "required_authority_scope": "workflow.command",
        "required_privacy_scope": "project",
        "allowed_task_boundary": "implementation",
        "required_protocol_version": "4.19.candidate_adapter.v1",
        "no_go_scope": ["no business execution", "no private-agent invocation"],
        "evidence_required": ["dispatch", "lifecycle", "lease", "mq", "runtime", "result"],
        "idempotency_key": "idem-001",
        "expires_at": "2026-05-27T12:10:00+00:00",
    }
    data.update(overrides)
    return Layer1ApprovedDecision(**data)


def _lifecycle_decision(**overrides):
    data = {
        "decision_id": "runtime-decision-001",
        "request_id": "eligibility-001",
        "dispatch_run_id": "run-001",
        "assignment_id": "assignment-001",
        "target_agent_id": "jarvis",
        "target_runtime_instance_id": "jarvis-runtime-001",
        "accepted": True,
        "policy_hash": "policy-hash-001",
        "idempotency_key": "idem-001",
        "evidence_refs": ["evidence://runtime-lifecycle/decision/runtime-decision-001"],
        "valid_until": "2026-05-27T12:00:30+00:00",
        "runtime_role": "implementation_agent",
        "runtime_owner": "principal://jarvis",
    }
    data.update(overrides)
    return RuntimeEligibilityDecision(**data)


def _lease(**overrides):
    data = {
        "lease_id": "lease-001",
        "lifecycle_decision_id": "runtime-decision-001",
        "assignment_id": "assignment-001",
        "dispatch_run_id": "run-001",
        "target_runtime_instance_id": "jarvis-runtime-001",
        "active": True,
        "status": "active",
        "expires_at": "2026-05-27T12:01:00+00:00",
        "policy_hash": "policy-hash-001",
        "idempotency_key": "idem-001",
        "release_required_by": "2026-05-27T12:00:15+00:00",
        "runtime_role": "implementation_agent",
        "runtime_owner": "principal://jarvis",
    }
    data.update(overrides)
    return RuntimeReservationLease(**data)


def _source_bound_run(controller):
    result = controller.create_run(
        decision=_decision(),
        dispatch_run_id="run-001",
        assignment_id="assignment-001",
        now_at=NOW,
    )
    assert result.accepted is True
    return result.payload["run"]


def _prepare_valid_publish(controller):
    _source_bound_run(controller)
    controller.state_store.record_lifecycle_decision(_lifecycle_decision())
    controller.state_store.record_reservation_lease(_lease())


def _publish(controller, **overrides):
    data = {
        "dispatch_run_id": "run-001",
        "assignment_id": "assignment-001",
        "lifecycle_decision_id": "runtime-decision-001",
        "reservation_lease_id": "lease-001",
        "runtime_instance_id": "jarvis-runtime-001",
        "idempotency_key": "idem-001",
        "subject": CANONICAL_ASSIGNMENT_SUBJECT,
        "now_at": NOW,
    }
    data.update(overrides)
    return controller.publish_assignment(**data)


def test_dispatch_validate_intent_rejects_missing_decision(tmp_path):
    controller = _controller(tmp_path)

    result = controller.validate_intent(None, now_at=NOW)

    assert result.accepted is False
    assert "MISSING_DECISION" in result.errors


def test_dispatch_validate_intent_rejects_missing_source_authority(tmp_path):
    controller = _controller(tmp_path)

    result = controller.validate_intent(_decision(source_refs={}, decision_authority_ref=""), now_at=NOW)

    assert result.accepted is False
    assert "MISSING_SOURCE_AUTHORITY" in result.errors
    assert "MISSING_SOURCE_REFS" in result.errors


def test_assignment_publish_blocks_missing_lease(tmp_path):
    controller = _controller(tmp_path)
    _source_bound_run(controller)
    controller.state_store.record_lifecycle_decision(_lifecycle_decision())

    result = _publish(controller)

    assert result.accepted is False
    assert "MISSING_RESERVATION_LEASE" in result.errors


def test_assignment_publish_blocks_expired_lease(tmp_path):
    controller = _controller(tmp_path)
    _source_bound_run(controller)
    controller.state_store.record_lifecycle_decision(_lifecycle_decision())
    controller.state_store.record_reservation_lease(_lease(expires_at="2026-05-27T11:59:59+00:00"))

    result = _publish(controller)

    assert result.accepted is False
    assert "RESERVATION_LEASE_EXPIRED" in result.errors


def test_assignment_publish_blocks_mismatched_lease(tmp_path):
    controller = _controller(tmp_path)
    _source_bound_run(controller)
    controller.state_store.record_lifecycle_decision(_lifecycle_decision())
    controller.state_store.record_reservation_lease(_lease(dispatch_run_id="other-run"))

    result = _publish(controller)

    assert result.accepted is False
    assert "LEASE_DISPATCH_RUN_ID_MISMATCH" in result.errors


def test_duplicate_replay_same_idempotency_suppressed_after_lifecycle_validation(tmp_path):
    controller = _controller(tmp_path)
    _prepare_valid_publish(controller)

    first = _publish(controller)
    second = _publish(controller)

    assert first.accepted is True
    assert first.duplicate_suppressed is False
    assert second.accepted is True
    assert second.duplicate_suppressed is True
    assert "DUPLICATE_ASSIGNMENT_SUPPRESSED" in second.errors


def test_duplicate_replay_with_mismatched_decision_or_lease_blocks(tmp_path):
    controller = _controller(tmp_path)
    _prepare_valid_publish(controller)

    first = _publish(controller)
    second = _publish(controller, lifecycle_decision_id="runtime-decision-other")

    assert first.accepted is True
    assert second.accepted is False
    assert second.duplicate_suppressed is False
    assert "LIFECYCLE_DECISION_ID_MISMATCH" in second.errors


def test_assignment_publish_rejects_runtime_scoped_assignment_alias(tmp_path):
    controller = _controller(tmp_path)
    _prepare_valid_publish(controller)

    result = _publish(controller, subject=RUNTIME_SCOPED_ASSIGNMENT_ALIAS)

    assert result.accepted is False
    assert "PUBLISH_SUBJECT_RUNTIME_ALIAS_DIAGNOSTIC_ONLY" in result.errors


def test_assignment_publish_blocks_wrong_runtime_payload_with_canonical_subject(tmp_path):
    controller = _controller(tmp_path)
    _prepare_valid_publish(controller)

    result = _publish(controller, runtime_instance_id="other-runtime")

    assert result.accepted is False
    assert "RUNTIME_INSTANCE_ID_MISMATCH" in result.errors
    assert "DECISION_RUNTIME_ID_MISMATCH" in result.errors
    assert "LEASE_RUNTIME_ID_MISMATCH" in result.errors


def test_wrong_runtime_result_rejected(tmp_path):
    controller = _controller(tmp_path)
    _prepare_valid_publish(controller)
    _publish(controller)

    result = controller.record_result_candidate(
        RuntimeResultCandidate(
            dispatch_run_id="run-001",
            assignment_id="assignment-001",
            runtime_instance_id="other-runtime",
            decision_id="runtime-decision-001",
            lease_id="lease-001",
            result_ref="result://candidate/001",
            evidence_refs=["evidence://candidate/result/001"],
        )
    )

    assert result.accepted is False
    assert "RESULT_RUNTIME_ID_MISMATCH" in result.errors


def test_assignment_publish_with_valid_lease_creates_request(tmp_path):
    controller = _controller(tmp_path)
    _prepare_valid_publish(controller)

    result = _publish(controller)

    assert result.accepted is True
    assert result.payload["assignment_publish_request"].lifecycle_decision_id == "runtime-decision-001"
    assert result.payload["assignment_publish_request"].reservation_lease_id == "lease-001"


def test_assignment_publish_accepts_wbs_7_19_15_namespace(tmp_path):
    dispatch_run_id = "wbs-7-19-15-2-jarvis-business-command-20260603T081653Z"
    controller = _controller(tmp_path)
    create = controller.create_run(
        decision=_decision(dispatch_packet_ref=f"dispatch-packet://controller-bridge/{dispatch_run_id}"),
        dispatch_run_id=dispatch_run_id,
        assignment_id="assignment-001",
        now_at=NOW,
    )
    assert create.accepted is True
    controller.state_store.record_lifecycle_decision(_lifecycle_decision(dispatch_run_id=dispatch_run_id))
    controller.state_store.record_reservation_lease(_lease(dispatch_run_id=dispatch_run_id))

    result = _publish(
        controller,
        dispatch_run_id=dispatch_run_id,
        subject=WBS_7_19_15_ASSIGNMENT_SUBJECT,
    )

    assert result.accepted is True
    assert result.payload["assignment_publish_request"].subject == WBS_7_19_15_ASSIGNMENT_SUBJECT


def test_assignment_publish_accepts_thunder_codex_app_agent_subject(tmp_path):
    dispatch_run_id = "wbs-7-19-15-3-thunder-codex-app-business-command-20260603T081653Z"
    controller = _controller(tmp_path)
    create = controller.create_run(
        decision=_decision(
            dispatch_packet_ref=f"dispatch-packet://controller-bridge/{dispatch_run_id}",
            target_agent_id="thunder_codex_app",
        ),
        dispatch_run_id=dispatch_run_id,
        assignment_id="assignment-001",
        now_at=NOW,
    )
    assert create.accepted is True
    controller.state_store.record_lifecycle_decision(
        _lifecycle_decision(dispatch_run_id=dispatch_run_id, target_agent_id="thunder_codex_app")
    )
    controller.state_store.record_reservation_lease(_lease(dispatch_run_id=dispatch_run_id))

    result = _publish(
        controller,
        dispatch_run_id=dispatch_run_id,
        subject=THUNDER_ASSIGNMENT_SUBJECT,
    )

    assert result.accepted is True
    assert result.payload["assignment_publish_request"].subject == THUNDER_ASSIGNMENT_SUBJECT


def test_controller_init_not_public_runtime_prerequisite(tmp_path):
    controller = _controller(tmp_path)

    result = controller.create_run(
        decision=_decision(evidence_required=["dispatch", "lifecycle", "lease"]),
        dispatch_run_id="run-001",
        assignment_id="assignment-001",
        now_at=NOW,
    )

    assert result.accepted is True
    assert "controller.init" not in result.payload["run"].evidence_required


def test_controller_does_not_mutate_registration_or_readiness(tmp_path):
    controller = _controller(tmp_path)
    _source_bound_run(controller)

    class RuntimeLifecycleProbe:
        def __init__(self):
            self.query_calls = 0
            self.mutating_calls = []

        def query_eligibility(self, request, *, now_at):
            self.query_calls += 1
            return _lifecycle_decision(request_id=request.request_id)

        def register_runtime(self, *args, **kwargs):
            self.mutating_calls.append("register_runtime")

        def submit_readiness(self, *args, **kwargs):
            self.mutating_calls.append("submit_readiness")

        def record_heartbeat(self, *args, **kwargs):
            self.mutating_calls.append("record_heartbeat")

    probe = RuntimeLifecycleProbe()

    result = controller.request_eligibility("run-001", runtime_lifecycle=probe, now_at=NOW)

    assert result.accepted is True
    assert probe.query_calls == 1
    assert probe.mutating_calls == []
