from nexus.mq.structured_task_models import (
    RuntimeEligibilitySnapshot,
    TaskEnvelope,
    TaskUnit,
)
from nexus.mq.structured_task_policy import (
    build_decomposition_plan,
    filter_route_candidates,
    resolve_source_authority,
)


def _envelope(**overrides):
    data = dict(
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
    data.update(overrides)
    return TaskEnvelope(**data)


def _unit(**overrides):
    data = dict(
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
    data.update(overrides)
    return TaskUnit(**data)


def _snapshot(candidates):
    return RuntimeEligibilitySnapshot(
        snapshot_id="snapshot-001",
        collected_at="2026-05-23T00:00:00+00:00",
        projection_version="v1",
        candidate_owners=candidates,
        capability_claims={},
        authority_claims={},
        readiness_state={},
        presence_state={},
        route_availability={},
        freshness_result="fresh",
        excluded_candidates=[],
    )


def _eligible_owner(owner_id="thunder", verifier_id="nova"):
    return {
        "owner_id": owner_id,
        "verifier_id": verifier_id,
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


def test_missing_authority_fails_closed():
    result = resolve_source_authority(
        input_kind="wbs_row",
        source_refs=[],
        source_hash="sha256:source",
        policy_hash="sha256:policy",
    )

    assert result.ok is False
    assert "MISSING_SOURCE_AUTHORITY" in result.errors


def test_decomposition_from_approved_wbs_row():
    result = build_decomposition_plan(
        envelope=_envelope(),
        child_specs=[{"task_id": "task-child-001", "title": "Child", "objective": "Build"}],
    )

    assert result.ok is True
    assert result.plan.generated_tasks[0].task_id == "task-child-001"
    assert result.plan.validation_result == "validated"


def test_blocked_dependency_blocks_route():
    result = build_decomposition_plan(
        envelope=_envelope(dependencies=["blocked:7.19.6"]),
        child_specs=[{"task_id": "task-child-001", "title": "Child", "objective": "Build"}],
    )

    assert result.ok is False
    assert "DEPENDENCY_BLOCKED" in result.errors


def test_route_candidate_filtering():
    result = filter_route_candidates(
        task_unit=_unit(),
        snapshot=_snapshot([_eligible_owner(), {**_eligible_owner("jarvis"), "readiness": "not_ready"}]),
        required_capability="code_edit",
        required_authority_scope="implementation",
    )

    assert result.ok is True
    assert result.selected_owner_id == "thunder"
    assert result.eligible_owner_ids == ["thunder"]


def test_no_eligible_route_blocks():
    result = filter_route_candidates(
        task_unit=_unit(),
        snapshot=_snapshot([{**_eligible_owner("jarvis"), "freshness": "stale"}]),
        required_capability="code_edit",
        required_authority_scope="implementation",
    )

    assert result.ok is False
    assert "BLOCKED_NO_ELIGIBLE_AGENT" in result.errors


def test_ambiguous_owner_escalates():
    result = filter_route_candidates(
        task_unit=_unit(),
        snapshot=_snapshot([_eligible_owner("thunder-a"), _eligible_owner("thunder-b")]),
        required_capability="code_edit",
        required_authority_scope="implementation",
    )

    assert result.ok is False
    assert "BLOCKED_AMBIGUOUS_OWNER" in result.errors


def test_agent_access_snapshot_is_not_governance_authority():
    result = filter_route_candidates(
        task_unit=_unit(source_refs=[]),
        snapshot=_snapshot([_eligible_owner()]),
        required_capability="code_edit",
        required_authority_scope="implementation",
    )

    assert result.ok is False
    assert "MISSING_TASK_SOURCE_REFS" in result.errors
