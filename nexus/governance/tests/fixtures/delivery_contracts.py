from __future__ import annotations

from nexus.governance.delivery_contracts import (
    AgentRecord,
    AssignmentRecord,
    DeliveryProject,
    EvidenceRecord,
    OwnerUatDecision,
    PrMapping,
    RunRecord,
    RuntimeAuthorization,
    TaskCard,
    ValidationEvidenceRecord,
    WorkItem,
)


SOURCE_REFS = (
    "docs/codex/SPEC.md",
    "docs/codex/UX_SPEC.md",
    "docs/codex/PR_PLAN.md",
)
PROJECT_ID = "nexus-edc"
WORK_ITEM_ID = "EDC-PR-002"


def valid_delivery_project(**overrides: object) -> DeliveryProject:
    values = {
        "project_id": PROJECT_ID,
        "repo_root": r"D:\Projects\Nexus",
        "default_base_branch": "codex/edc-governance-desktop",
        "active_branch": "codex/edc-pr-002-delivery-domain-contracts",
        "worktree_path": r"D:\Projects\Nexus\.worktrees\edc-pr-002-delivery-domain-contracts",
        "validation_entrypoints": ("python -m pytest nexus/governance/tests",),
        "evidence_locations": ("verification/4.21/edc-pr-002",),
        "source_refs": SOURCE_REFS,
    }
    values.update(overrides)
    return DeliveryProject(**values)


def valid_task_card(**overrides: object) -> TaskCard:
    values = {
        "background": "EDC-PR-001 created the delivery console target.",
        "goal": "Define durable delivery domain contracts.",
        "scope": ("nexus/governance/delivery_contracts.py",),
        "non_goals": ("desktop UI", "runtime startup"),
        "file_boundaries": ("nexus/governance/delivery_contracts.py", "nexus/governance/tests/test_delivery_domain_contracts.py"),
        "acceptance_criteria": ("domain contracts validate work item readiness",),
        "validation_commands": ("python -m pytest nexus/governance/tests/test_delivery_domain_contracts.py -q",),
        "risks": ("over-specifying handoff serialization",),
        "write_back_location": "Planning thread 019f07b2-8968-7891-bd41-aed6f25a651c",
    }
    values.update(overrides)
    return TaskCard(**values)


def valid_agent_record(**overrides: object) -> AgentRecord:
    values = {
        "agent_id": "codex-execution",
        "role": "Codex Execution",
        "availability": "available",
        "current_assignment_id": "assign-edc-pr-002",
        "last_report_ref": "report:edc-pr-001-closeout",
        "blockers": (),
        "allowed_actions": ("edit_governance_contracts", "run_pytest"),
    }
    values.update(overrides)
    return AgentRecord(**values)


def valid_assignment_record(**overrides: object) -> AssignmentRecord:
    values = {
        "assignment_id": "assign-edc-pr-002",
        "work_item_id": WORK_ITEM_ID,
        "agent_id": "codex-execution",
        "branch": "codex/edc-pr-002-delivery-domain-contracts",
        "worktree_path": r"D:\Projects\Nexus\.worktrees\edc-pr-002-delivery-domain-contracts",
        "editable_scope": ("nexus/governance/**",),
        "allowed_actions": ("edit_governance_contracts", "run_pytest"),
        "forbidden_actions": ("runtime_startup", "dependency_install"),
        "reducer_owner": "",
    }
    values.update(overrides)
    return AssignmentRecord(**values)



def valid_run_record(**overrides: object) -> RunRecord:
    values = {
        "run_id": "run-edc-pr-002",
        "work_item_id": WORK_ITEM_ID,
        "status": "review",
        "branch": "codex/edc-pr-002-delivery-domain-contracts",
        "worktree_path": r"D:\Projects\Nexus\.worktrees\edc-pr-002-delivery-domain-contracts",
        "files_touched": ("nexus/governance/delivery_contracts.py",),
        "validation_commands": ("python -m pytest nexus/governance/tests/test_delivery_domain_contracts.py -q",),
        "command_results": ("20 passed",),
        "blockers": (),
        "completion_report_ref": "report:edc-pr-002",
    }
    values.update(overrides)
    return RunRecord(**values)
def valid_runtime_authorization(**overrides: object) -> RuntimeAuthorization:
    values = {
        "state": "not_required",
        "named_command": "",
        "authority_ref": "",
        "source_ref": "docs/codex/SCOPE.md",
    }
    values.update(overrides)
    return RuntimeAuthorization(**values)


def valid_evidence_record(**overrides: object) -> EvidenceRecord:
    values = {
        "evidence_id": "evidence-edc-pr-002-tests",
        "state": "present",
        "command": "python -m pytest nexus/governance/tests/test_delivery_domain_contracts.py -q",
        "result_ref": "pytest:delivery-contracts",
        "source_refs": SOURCE_REFS,
    }
    values.update(overrides)
    return EvidenceRecord(**values)


def valid_validation_evidence_record(**overrides: object) -> ValidationEvidenceRecord:
    values = {
        "validation_id": "validation-edc-pr-002",
        "evidence": valid_evidence_record(),
        "validated_at": "2026-06-27T00:00:00Z",
        "validator": "codex-execution",
    }
    values.update(overrides)
    return ValidationEvidenceRecord(**values)


def valid_pr_mapping(**overrides: object) -> PrMapping:
    values = {
        "internal_id": WORK_ITEM_ID,
        "github_pr_number": None,
        "github_pr_url": "",
        "branch": "codex/edc-pr-002-delivery-domain-contracts",
        "status": "draft",
    }
    values.update(overrides)
    return PrMapping(**values)


def valid_owner_uat_decision(**overrides: object) -> OwnerUatDecision:
    values = {
        "state": "not_applicable",
        "owner_ref": "owner:alex",
        "decision_ref": "",
        "notes": "governance contracts only",
    }
    values.update(overrides)
    return OwnerUatDecision(**values)


def valid_work_item(**overrides: object) -> WorkItem:
    values = {
        "work_item_id": WORK_ITEM_ID,
        "title": "Delivery Domain Contracts",
        "status": "review",
        "task_card": valid_task_card(),
        "project": valid_delivery_project(),
        "agent": valid_agent_record(),
        "assignment": valid_assignment_record(),
        "runtime_authorization": valid_runtime_authorization(),
        "evidence": valid_evidence_record(),
        "validation": valid_validation_evidence_record(),
        "pr_mapping": valid_pr_mapping(),
        "owner_uat": valid_owner_uat_decision(),
        "parallel_fanout_active": False,
        "reducer_owner": "",
        "source_refs": SOURCE_REFS,
    }
    values.update(overrides)
    return WorkItem(**values)
