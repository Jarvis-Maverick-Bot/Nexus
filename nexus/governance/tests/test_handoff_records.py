from __future__ import annotations

import pytest

from nexus.governance.errors import ErrorCode
from nexus.governance.handoff_records import (
    validate_completion_report,
    validate_handoff_packet,
)

from .fixtures.delivery_contracts import valid_task_card
from .fixtures.handoff_records import (
    BRANCH,
    WORKTREE_PATH,
    missing_validation_record,
    not_run_by_scope_record,
    stale_validation_record,
    valid_completion_report,
    valid_validation_command_result,
    valid_handoff_packet,
    valid_handoff_work_item,
)


def test_handoff_accepts_complete_work_item_task_packet() -> None:
    result = validate_handoff_packet(valid_handoff_packet(), work_item=valid_handoff_work_item())

    assert result.accepted is True


def test_handoff_rejects_incomplete_task_card() -> None:
    handoff = valid_handoff_packet(
        task_card=valid_task_card(background="", file_boundaries=(), validation_commands=())
    )

    result = validate_handoff_packet(handoff, work_item=valid_handoff_work_item())

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_WORKPACKET_INVALID
    assert result.missing_fields == ("background", "file_boundaries", "validation_commands")


def test_handoff_rejects_branch_worktree_mismatch() -> None:
    handoff = valid_handoff_packet(branch="codex/wrong-branch", worktree_path=r"D:\Projects\Nexus\.worktrees\wrong")

    result = validate_handoff_packet(handoff, work_item=valid_handoff_work_item())

    assert result.accepted is False
    assert "handoff.branch must match assignment.branch" in result.blocked_reasons
    assert "handoff.worktree_path must match assignment.worktree_path" in result.blocked_reasons
    assert "handoff.branch must match project.active_branch" in result.blocked_reasons
    assert "handoff.worktree_path must match project.worktree_path" in result.blocked_reasons


def test_handoff_rejects_unauthorized_runtime_command_claims() -> None:
    handoff = valid_handoff_packet(runtime_command_claims=("pnpm dev",))

    result = validate_handoff_packet(handoff, work_item=valid_handoff_work_item())

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert "runtime command claim requires authorized_for_named_command: pnpm dev" in result.blocked_reasons


def test_completion_report_accepts_valid_pr_readiness() -> None:
    result = validate_completion_report(
        valid_completion_report(),
        handoff=valid_handoff_packet(),
        work_item=valid_handoff_work_item(),
    )

    assert result.accepted is True


@pytest.mark.parametrize("validation_result", (missing_validation_record(), stale_validation_record()))
def test_completion_report_rejects_missing_or_stale_evidence_for_pr_readiness(validation_result) -> None:
    report = valid_completion_report(validation_results=(validation_result,))

    result = validate_completion_report(report, handoff=valid_handoff_packet(), work_item=valid_handoff_work_item())

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_RECORD_INVALID
    assert "PR readiness requires fresh evidence or explicit not_run_by_scope" in result.blocked_reasons




def test_completion_report_rejects_not_run_with_present_evidence_for_pr_readiness() -> None:
    report = valid_completion_report(
        validation_results=(
            valid_validation_command_result(status="not_run", exit_code=None, evidence_state="present"),
        )
    )

    result = validate_completion_report(report, handoff=valid_handoff_packet(), work_item=valid_handoff_work_item())

    assert result.accepted is False
    assert "not_run validation result requires not_run_by_scope evidence" in result.blocked_reasons


def test_completion_report_rejects_failed_validation_for_pr_readiness() -> None:
    report = valid_completion_report(
        validation_results=(
            valid_validation_command_result(status="failed", exit_code=1, evidence_state="failed", evidence_ref="pytest:failed"),
        )
    )

    result = validate_completion_report(report, handoff=valid_handoff_packet(), work_item=valid_handoff_work_item())

    assert result.accepted is False
    assert "PR readiness requires all validation commands to pass" in result.blocked_reasons


def test_completion_report_rejects_blockers_for_pr_readiness() -> None:
    report = valid_completion_report(blockers=("blocked by review",))

    result = validate_completion_report(report, handoff=valid_handoff_packet(), work_item=valid_handoff_work_item())

    assert result.accepted is False
    assert "PR readiness cannot be claimed while blockers are present" in result.blocked_reasons

def test_completion_report_accepts_not_run_by_scope_with_reason() -> None:
    report = valid_completion_report(validation_results=(not_run_by_scope_record(),))

    result = validate_completion_report(report, handoff=valid_handoff_packet(), work_item=valid_handoff_work_item())

    assert result.accepted is True


def test_completion_report_rejects_changed_files_outside_boundaries() -> None:
    report = valid_completion_report(changed_files=("apps/l1gov-desktop-client/src/App.tsx",))

    result = validate_completion_report(report, handoff=valid_handoff_packet(), work_item=valid_handoff_work_item())

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert result.invalid_items == ("apps/l1gov-desktop-client/src/App.tsx",)


def test_completion_report_rejects_missing_required_report_fields() -> None:
    report = valid_completion_report(changed_files=(), validation_results=(), report_ref="")

    result = validate_completion_report(report, handoff=valid_handoff_packet(), work_item=valid_handoff_work_item())

    assert result.accepted is False
    assert result.missing_fields == ("changed_files", "validation_results", "report_ref")


def test_completion_report_rejects_runtime_command_claim_without_authorization() -> None:
    report = valid_completion_report(runtime_command_claims=("nats broker restart",))

    result = validate_completion_report(report, handoff=valid_handoff_packet(), work_item=valid_handoff_work_item())

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert "runtime command claim requires authorized_for_named_command: nats broker restart" in result.blocked_reasons


def test_completion_report_rejects_owner_uat_acceptance_claim() -> None:
    report = valid_completion_report(owner_uat_state="accepted_by_owner")

    result = validate_completion_report(report, handoff=valid_handoff_packet(), work_item=valid_handoff_work_item())

    assert result.accepted is False
    assert result.blocked_reasons == ("completion report cannot claim owner UAT acceptance",)


def test_completion_report_rejects_handoff_and_work_item_mismatch() -> None:
    report = valid_completion_report(branch="codex/wrong-branch", worktree_path=r"D:\Projects\Nexus\.worktrees\wrong")

    result = validate_completion_report(report, handoff=valid_handoff_packet(), work_item=valid_handoff_work_item())

    assert result.accepted is False
    assert "report.branch must match handoff.branch" in result.blocked_reasons
    assert "report.worktree_path must match handoff.worktree_path" in result.blocked_reasons
    assert "report.branch must match project.active_branch" in result.blocked_reasons
    assert "report.worktree_path must match project.worktree_path" in result.blocked_reasons


def test_completion_report_rejects_branch_and_worktree_constants_when_wrong() -> None:
    assert BRANCH == "codex/edc-pr-003-codex-handoff-loop"
    assert WORKTREE_PATH.endswith(r".worktrees\edc-pr-003-codex-handoff-loop")
