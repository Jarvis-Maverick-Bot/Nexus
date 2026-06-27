from __future__ import annotations

import pytest

from nexus.governance.errors import ErrorCode
from nexus.governance.delivery_contracts import (
    validate_pr_mapping,
    validate_runtime_authorization,
    validate_task_card,
    validate_work_item,
)

from .fixtures.delivery_contracts import (
    valid_agent_record,
    valid_assignment_record,
    valid_delivery_project,
    valid_evidence_record,
    valid_owner_uat_decision,
    valid_pr_mapping,
    valid_run_record,
    valid_runtime_authorization,
    valid_task_card,
    valid_validation_evidence_record,
    valid_work_item,
)


def test_work_item_accepts_complete_ready_to_review_path_with_present_evidence() -> None:
    item = valid_work_item(status="review", evidence=valid_evidence_record(state="present"))

    result = validate_work_item(item)

    assert result.accepted is True


def test_task_card_rejects_missing_required_fields_by_name() -> None:
    task_card = valid_task_card(background="", goal="", scope=(), validation_commands=())

    result = validate_task_card(task_card)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_WORKPACKET_INVALID
    assert result.missing_fields == ("background", "goal", "scope", "validation_commands")


@pytest.mark.parametrize(
    "unsafe_path",
    (
        ".env",
        "private/session/token.txt",
        "cache/runtime.log",
        "state/nexus.sqlite",
        "node_modules/package/index.js",
        "apps/l1gov-desktop-client/src-tauri/gen/schema.json",
        ".edc-build/output.json",
        ".git/config",
    ),
)
def test_task_card_rejects_unsafe_file_and_worktree_boundaries(unsafe_path: str) -> None:
    task_card = valid_task_card(file_boundaries=("nexus/governance/delivery_contracts.py", unsafe_path))

    result = validate_task_card(task_card)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert unsafe_path in result.invalid_items


def test_work_item_rejects_done_without_owner_uat_acceptance() -> None:
    item = valid_work_item(
        status="done",
        evidence=valid_evidence_record(state="present"),
        owner_uat=valid_owner_uat_decision(state="awaiting_owner"),
    )

    result = validate_work_item(item)

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
    assert "done requires owner UAT accepted_by_owner or not_applicable" in result.blocked_reasons


def test_work_item_rejects_parallel_fanout_without_reducer_owner() -> None:
    item = valid_work_item(parallel_fanout_active=True, reducer_owner="")

    result = validate_work_item(item)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_WORKPACKET_INVALID
    assert "parallel fan-out requires reducer_owner" in result.blocked_reasons


def test_runtime_authorization_requires_named_command_and_authority_ref() -> None:
    authorization = valid_runtime_authorization(state="authorized_for_named_command", named_command="", authority_ref="")

    result = validate_runtime_authorization(authorization)

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
    assert result.missing_fields == ("named_command", "authority_ref")


def test_pr_mapping_rejects_internal_and_github_number_confusion() -> None:
    mapping = valid_pr_mapping(internal_id="27", github_pr_number=27)

    result = validate_pr_mapping(mapping)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_RECORD_INVALID
    assert "internal_id must use EDC-PR-###" in result.blocked_reasons
    assert "internal_id must not equal GitHub PR number" in result.blocked_reasons


@pytest.mark.parametrize("status", ("review", "uat", "done"))
@pytest.mark.parametrize("evidence_state", ("missing", "stale"))
def test_work_item_rejects_review_uat_done_without_fresh_evidence(status: str, evidence_state: str) -> None:
    item = valid_work_item(
        status=status,
        evidence=valid_evidence_record(state=evidence_state),
        owner_uat=valid_owner_uat_decision(state="accepted_by_owner"),
    )

    result = validate_work_item(item)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_RECORD_INVALID
    assert f"{status} requires present, failed, or not_run_by_scope evidence" in result.blocked_reasons


@pytest.mark.parametrize(
    ("overrides", "blocked_reason"),
    (
        (
            {"assignment": valid_assignment_record(work_item_id="EDC-PR-999")},
            "assignment.work_item_id must match work_item.work_item_id",
        ),
        (
            {"assignment": valid_assignment_record(agent_id="other-agent")},
            "assignment.agent_id must match agent.agent_id",
        ),
        (
            {"agent": valid_agent_record(current_assignment_id="other-assignment")},
            "agent.current_assignment_id must match assignment.assignment_id",
        ),
        (
            {"assignment": valid_assignment_record(branch="other-branch")},
            "assignment.branch must match project.active_branch",
        ),
        (
            {"assignment": valid_assignment_record(worktree_path=r"D:\Projects\Nexus\.worktrees\other")},
            "assignment.worktree_path must match project.worktree_path",
        ),
        (
            {"pr_mapping": valid_pr_mapping(internal_id="EDC-PR-999")},
            "pr_mapping.internal_id must match work_item.work_item_id",
        ),
        (
            {"run": valid_run_record(work_item_id="EDC-PR-999")},
            "run.work_item_id must match work_item.work_item_id",
        ),
        (
            {"run": valid_run_record(branch="other-branch")},
            "run.branch must match project.active_branch",
        ),
        (
            {"run": valid_run_record(worktree_path=r"D:\Projects\Nexus\.worktrees\other")},
            "run.worktree_path must match project.worktree_path",
        ),
        (
            {
                "evidence": valid_evidence_record(evidence_id="evidence-a"),
                "validation": valid_validation_evidence_record(evidence=valid_evidence_record(evidence_id="evidence-b")),
            },
            "validation.evidence.evidence_id must match work_item.evidence.evidence_id",
        ),
    ),
)
def test_work_item_rejects_aggregate_record_mismatches(
    overrides: dict[str, object],
    blocked_reason: str,
) -> None:
    item = valid_work_item(**overrides)

    result = validate_work_item(item)

    assert result.accepted is False
    assert blocked_reason in result.blocked_reasons


def test_work_item_accepts_matching_optional_run_record() -> None:
    project = valid_delivery_project()
    item = valid_work_item(
        project=project,
        run=valid_run_record(branch=project.active_branch, worktree_path=project.worktree_path),
    )

    result = validate_work_item(item)

    assert result.accepted is True
