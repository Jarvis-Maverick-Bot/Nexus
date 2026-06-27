from __future__ import annotations

from nexus.governance.delivery_contracts import (
    EvidenceRecord,
    ValidationEvidenceRecord,
    WorkItem,
)
from nexus.governance.handoff_records import (
    ExecutionCompletionReport,
    PlanningExecutionHandoff,
    ValidationCommandResult,
)

from .delivery_contracts import (
    SOURCE_REFS,
    valid_agent_record,
    valid_assignment_record,
    valid_delivery_project,
    valid_evidence_record,
    valid_owner_uat_decision,
    valid_pr_mapping,
    valid_runtime_authorization,
    valid_task_card,
    valid_validation_evidence_record,
    valid_work_item,
)


WORK_ITEM_ID = "EDC-PR-003"
BRANCH = "codex/edc-pr-003-codex-handoff-loop"
WORKTREE_PATH = r"D:\Projects\Nexus\.worktrees\edc-pr-003-codex-handoff-loop"


def valid_handoff_work_item(**overrides: object) -> WorkItem:
    evidence = valid_evidence_record(evidence_id="evidence-edc-pr-003-tests")
    values = {
        "work_item_id": WORK_ITEM_ID,
        "title": "Codex Execution Handoff Loop",
        "status": "review",
        "task_card": valid_task_card(
            goal="Define durable handoff records.",
            scope=("nexus/governance/handoff_records.py",),
            file_boundaries=(
                "docs/codex/PR_PLAN.md",
                "nexus/governance/handoff_records.py",
                "nexus/governance/tests/fixtures/handoff_records.py",
                "nexus/governance/tests/test_handoff_records.py",
            ),
            validation_commands=("python -m pytest nexus/governance/tests/test_handoff_records.py -q",),
            risks=("over-tightening docs-only completion reports",),
        ),
        "project": valid_delivery_project(active_branch=BRANCH, worktree_path=WORKTREE_PATH),
        "agent": valid_agent_record(current_assignment_id="assign-edc-pr-003"),
        "assignment": valid_assignment_record(
            assignment_id="assign-edc-pr-003",
            work_item_id=WORK_ITEM_ID,
            branch=BRANCH,
            worktree_path=WORKTREE_PATH,
            editable_scope=("docs/codex/PR_PLAN.md", "nexus/governance/**"),
        ),
        "runtime_authorization": valid_runtime_authorization(source_ref="docs/codex/SCOPE.md"),
        "evidence": evidence,
        "validation": valid_validation_evidence_record(
            validation_id="validation-edc-pr-003",
            evidence=evidence,
        ),
        "pr_mapping": valid_pr_mapping(internal_id=WORK_ITEM_ID, branch=BRANCH),
        "owner_uat": valid_owner_uat_decision(),
        "source_refs": SOURCE_REFS,
    }
    values.update(overrides)
    return valid_work_item(**values)


def valid_handoff_packet(**overrides: object) -> PlanningExecutionHandoff:
    work_item = valid_handoff_work_item()
    values = {
        "handoff_id": "handoff-edc-pr-003",
        "work_item_id": WORK_ITEM_ID,
        "branch": BRANCH,
        "worktree_path": WORKTREE_PATH,
        "task_card": work_item.task_card,
        "assignment": work_item.assignment,
        "runtime_authorization": work_item.runtime_authorization,
        "editable_scope": work_item.assignment.editable_scope,
        "runtime_command_claims": (),
        "source_refs": SOURCE_REFS,
        "write_back_location": "Planning thread 019f07b2-8968-7891-bd41-aed6f25a651c",
    }
    values.update(overrides)
    return PlanningExecutionHandoff(**values)


def valid_validation_command_result(**overrides: object) -> ValidationCommandResult:
    values = {
        "command": "python -m pytest nexus/governance/tests/test_handoff_records.py -q",
        "exit_code": 0,
        "status": "passed",
        "evidence_state": "present",
        "evidence_ref": "pytest:handoff-records",
        "not_run_reason": "",
    }
    values.update(overrides)
    return ValidationCommandResult(**values)


def valid_completion_report(**overrides: object) -> ExecutionCompletionReport:
    values = {
        "report_id": "report-edc-pr-003",
        "handoff_id": "handoff-edc-pr-003",
        "work_item_id": WORK_ITEM_ID,
        "branch": BRANCH,
        "worktree_path": WORKTREE_PATH,
        "changed_files": (
            "docs/codex/PR_PLAN.md",
            "nexus/governance/handoff_records.py",
            "nexus/governance/tests/fixtures/handoff_records.py",
            "nexus/governance/tests/test_handoff_records.py",
        ),
        "validation_results": (valid_validation_command_result(),),
        "blockers": (),
        "residual_risks": ("Run lifecycle is still data-only in this slice.",),
        "pr_readiness": "ready_for_pr",
        "pr_mapping_ready": True,
        "runtime_command_claims": (),
        "owner_uat_state": "not_applicable",
        "source_refs": SOURCE_REFS,
        "report_ref": "Planning thread 019f07b2-8968-7891-bd41-aed6f25a651c",
    }
    values.update(overrides)
    return ExecutionCompletionReport(**values)


def stale_validation_record() -> ValidationCommandResult:
    return valid_validation_command_result(evidence_state="stale", evidence_ref="pytest:stale")


def missing_validation_record() -> ValidationCommandResult:
    return valid_validation_command_result(evidence_state="missing", evidence_ref="")


def not_run_by_scope_record() -> ValidationCommandResult:
    return valid_validation_command_result(
        exit_code=None,
        status="not_run",
        evidence_state="not_run_by_scope",
        evidence_ref="task-card:docs-only",
        not_run_reason="Task card did not authorize executable validation.",
    )


def work_item_with_evidence_state(state: str) -> WorkItem:
    evidence = EvidenceRecord(
        evidence_id=f"evidence-edc-pr-003-{state}",
        state=state,
        command="python -m pytest nexus/governance/tests/test_handoff_records.py -q",
        result_ref=f"pytest:{state}",
        source_refs=SOURCE_REFS,
    )
    return valid_handoff_work_item(
        evidence=evidence,
        validation=ValidationEvidenceRecord(
            validation_id=f"validation-edc-pr-003-{state}",
            evidence=evidence,
            validated_at="2026-06-27T00:00:00Z",
            validator="codex-execution",
        ),
    )
