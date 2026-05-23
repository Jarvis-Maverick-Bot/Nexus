from nexus.mq.durable_state import DurableStateStore
from nexus.mq.structured_task_controller import (
    StructuredTaskControllerPolicy,
    prepare_owner_handoff,
)
from nexus.mq.structured_task_models import RuntimeEligibilitySnapshot, TaskEnvelope, TaskUnit


def _envelope():
    return TaskEnvelope(
        task_id="task-001",
        envelope_version="v1",
        run_id="run-001",
        objective="Implement controller",
        source_refs=["wbs://7.19.1"],
        source_hash="sha256:source",
        policy_hash="sha256:policy",
        role_target="implementer",
        required_capabilities=["code_edit"],
        dependencies=[],
        constraints=["no runtime start"],
        no_go_scope=["no business execution"],
        deliverables=["evidence"],
        stop_conditions=["blocked"],
        dispatch_mode="local_only",
        idempotency_key="idem-001",
    )


def _unit():
    return TaskUnit(
        task_id="task-001",
        parent_id=None,
        title="Task",
        objective="Objective",
        source_refs=["wbs://7.19.2"],
        source_hash="sha256:source",
        owner="thunder",
        verifier="nova",
        dependencies=[],
        priority="normal",
        status="validated",
        dod=["tests pass"],
        no_go_scope=["no live dispatch"],
        allowed_tools=["pytest"],
        allowed_write_surfaces=["nexus/mq/structured_task_*.py"],
        evidence_requirements=["log"],
        stop_conditions=["blocked"],
        escalation_conditions=["review"],
    )


def _snapshot():
    return RuntimeEligibilitySnapshot(
        snapshot_id="snapshot-001",
        collected_at="2026-05-23T00:00:00+00:00",
        projection_version="v1",
        candidate_owners=[
            {
                "owner_id": "thunder",
                "verifier_id": "nova",
                "runtime_id": "runtime-001",
                "capabilities": ["code_edit"],
                "authority_scopes": ["implementation"],
                "readiness": "ready",
                "freshness": "fresh",
                "capacity_available": True,
                "channel_available": True,
                "allowed_tools": ["pytest"],
                "allowed_write_surfaces": ["nexus/mq/structured_task_*.py"],
            }
        ],
        capability_claims={},
        authority_claims={},
        readiness_state={},
        presence_state={},
        route_availability={},
        freshness_result="fresh",
        excluded_candidates=[],
    )


def test_controller_default_policy_is_safe_off(tmp_path):
    result = prepare_owner_handoff(
        envelope=_envelope(),
        task_unit=_unit(),
        snapshot=_snapshot(),
        store=DurableStateStore(tmp_path / "state.sqlite"),
        policy=StructuredTaskControllerPolicy(),
    )

    assert result.ok is False
    assert "STRUCTURED_TASK_CONTROLLER_DISABLED" in result.errors


def test_controller_emits_packet_candidate_after_audit_write(tmp_path):
    result = prepare_owner_handoff(
        envelope=_envelope(),
        task_unit=_unit(),
        snapshot=_snapshot(),
        store=DurableStateStore(tmp_path / "state.sqlite"),
        policy=StructuredTaskControllerPolicy(controller_enabled=True),
    )

    assert result.ok is True
    assert result.packet.audit_ref.startswith("p5-")
    assert result.packet.not_business_completion is True
    assert result.dispatched is False


def test_controller_does_not_publish_or_define_transport(tmp_path):
    result = prepare_owner_handoff(
        envelope=_envelope(),
        task_unit=_unit(),
        snapshot=_snapshot(),
        store=DurableStateStore(tmp_path / "state.sqlite"),
        policy=StructuredTaskControllerPolicy(controller_enabled=True),
    )

    assert result.transport_message is None
    assert result.dispatched is False
