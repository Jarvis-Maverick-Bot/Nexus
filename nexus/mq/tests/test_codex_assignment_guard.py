from nexus.mq.codex_assignment_guard import (
    CodexAssignmentAdapterMetadata,
    evaluate_codex_assignment_intake,
)
from nexus.mq.tests.test_codex_runtime_adapter import EXPIRES, NOW, _registration
from nexus.mq.codex_runtime_adapter import build_codex_registry_record


def _record():
    return build_codex_registry_record(registration=_registration(), now_at=NOW)


def _metadata(**overrides):
    data = {
        "assignment_id": "assign-codex-001",
        "run_id": "run-codex-001",
        "task_id": "task-codex-001",
        "packet_id": "packet-codex-001",
        "packet_version": "v1",
        "target_agent_id": "codex-thunder",
        "target_runtime_instance_id": "codex-runtime-001",
        "assignment_kind": "bounded_implementation_candidate",
        "business_execution_allowed": False,
        "source_refs": ["wbs://7.19.13"],
        "source_hashes": ["sha256:authority"],
        "workspace_ref": "workspace://nexus",
        "repo_ref": "repo://nexus",
        "branch_or_worktree_policy_ref": "branch-policy://codex/wbs-7-19-13",
        "allowed_write_surfaces": ["nexus/mq/codex_*.py"],
        "prohibited_write_surfaces": ["config/**"],
        "allowed_tools": ["git", "pytest"],
        "required_commands": ["python -m pytest nexus/mq/tests/test_codex_*.py -q"],
        "evidence_requirements": ["focused tests", "secret scan"],
        "no_go_scope": ["no live worker start", "no credential mutation"],
        "stop_conditions": ["source authority mismatch"],
        "timeout_policy_ref": "timeout-policy://non-live",
        "retry_policy_ref": "retry-policy://3.5",
        "startup_packet_ref": "startup-packet://codex/001",
        "readiness_evidence_ref": "evidence://codex/readiness/001",
        "created_at": NOW,
        "expires_at": EXPIRES,
    }
    data.update(overrides)
    return CodexAssignmentAdapterMetadata(**data)


def test_codex_assignment_intake_accepts_bounded_non_business_candidate():
    decision = evaluate_codex_assignment_intake(
        metadata=_metadata(),
        record=_record(),
        now_at=NOW,
    )

    assert decision.accepted is True
    assert decision.intake is not None
    assert decision.intake.state == "accepted"
    assert decision.intake.not_business_completion is True


def test_codex_assignment_intake_rejects_business_execution_by_default():
    decision = evaluate_codex_assignment_intake(
        metadata=_metadata(assignment_kind="business_task", business_execution_allowed=True),
        record=_record(),
        now_at=NOW,
    )

    assert decision.accepted is False
    assert "CODEX_BUSINESS_EXECUTION_NOT_AUTHORIZED" in decision.errors


def test_codex_assignment_intake_rejects_mismatched_runtime_and_missing_source():
    decision = evaluate_codex_assignment_intake(
        metadata=_metadata(target_runtime_instance_id="other-runtime", source_refs=[]),
        record=_record(),
        now_at=NOW,
    )

    assert decision.accepted is False
    assert "CODEX_TARGET_RUNTIME_MISMATCH" in decision.errors
    assert "MISSING_CODEX_ASSIGNMENT_FIELD: source_refs" in decision.errors


def test_codex_assignment_intake_rejects_disallowed_write_surface_overlap():
    decision = evaluate_codex_assignment_intake(
        metadata=_metadata(allowed_write_surfaces=["config/**"], prohibited_write_surfaces=["config/**"]),
        record=_record(),
        now_at=NOW,
    )

    assert decision.accepted is False
    assert "CODEX_ALLOWED_WRITE_SURFACE_OVERLAPS_PROHIBITED" in decision.errors


def test_codex_assignment_intake_suppresses_duplicate_idempotency():
    first = evaluate_codex_assignment_intake(metadata=_metadata(), record=_record(), now_at=NOW)
    replay = evaluate_codex_assignment_intake(
        metadata=_metadata(),
        record=_record(),
        now_at=NOW,
        prior_intakes={first.intake.idempotency_key: first.intake.intake_id},
    )

    assert replay.accepted is True
    assert replay.intake is None
    assert replay.duplicate_suppressed is True
    assert replay.errors == ["CODEX_DUPLICATE_ASSIGNMENT_SUPPRESSED"]
