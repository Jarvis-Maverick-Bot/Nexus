from __future__ import annotations

from nexus.governance.operational_commands import (
    AgentDefinitionRecord,
    DispatchCandidateProjection,
    HandoffDraftPreview,
    OperationalCommandDraft,
    RuntimeInstanceRecord,
    RuntimeProviderProfile,
    RunSessionRecord,
)


WORK_ITEM_ID = "EDC-PR-011"
GITHUB_PR_NUMBER = None


def agent_definition(**overrides):
    data = {
        "agent_id": "agent.codex.execution",
        "display_name": "Codex Execution",
        "role": "execution",
        "capability_tags": ("implementation", "validation", "handoff"),
        "authority_boundaries": ("explicit_task_card_only", "no_owner_uat_acceptance"),
        "source_refs": ("docs/codex/SPEC.md",),
    }
    data.update(overrides)
    return AgentDefinitionRecord(**data)


def runtime_provider(**overrides):
    data = {
        "provider_id": "runtime-provider.codex.local",
        "provider_family": "codex",
        "display_name": "Codex local runtime provider",
        "capability_tags": ("code_edit", "test_runner"),
        "executable": False,
        "blocked_reason": "EDC-PR-011 produces draft-only command intents.",
        "source_refs": ("nexus/mq/codex_runtime_adapter.py",),
    }
    data.update(overrides)
    return RuntimeProviderProfile(**data)


def runtime_instance(**overrides):
    data = {
        "runtime_instance_id": "runtime.codex.edc-pr-011.local",
        "provider_id": "runtime-provider.codex.local",
        "worktree_path": r"D:\Projects\Nexus\.worktrees\edc-pr-011-agent-runtime-command-drafts",
        "branch": "codex/edc-pr-011-agent-runtime-command-drafts",
        "status": "available_for_draft",
        "readiness_state": "inspection_only",
        "startup_allowed": False,
        "dependency_install_allowed": False,
        "broker_mutation_allowed": False,
        "live_dispatch_allowed": False,
        "source_refs": ("docs/codex/SCOPE.md",),
    }
    data.update(overrides)
    return RuntimeInstanceRecord(**data)


def run_session(**overrides):
    data = {
        "run_session_id": "run-session.edc-pr-011.preview",
        "work_item_id": WORK_ITEM_ID,
        "agent_id": "agent.codex.execution",
        "runtime_instance_id": "runtime.codex.edc-pr-011.local",
        "session_state": "draft_preview",
        "execution_state": "not_started",
        "evidence_ref": "not_run_by_scope:edc-pr-011-draft-only",
        "source_refs": ("nexus/governance/handoff_records.py",),
    }
    data.update(overrides)
    return RunSessionRecord(**data)


def command_draft(**overrides):
    data = {
        "draft_id": "draft.edc-pr-011.prepare-handoff",
        "command_type": "prepare_execution_handoff_draft",
        "work_item_id": WORK_ITEM_ID,
        "github_pr_number": GITHUB_PR_NUMBER,
        "target_agent_id": "agent.codex.execution",
        "target_runtime_instance_id": "runtime.codex.edc-pr-011.local",
        "run_session_id": "run-session.edc-pr-011.preview",
        "draft_only": True,
        "non_authoritative": True,
        "required_approvals": ("planning_review",),
        "blocked_authorities": (
            "live_dispatch",
            "runtime_startup",
            "dependency_install",
            "broker_nats_mutation",
            "merge_pr",
            "owner_uat_acceptance",
        ),
        "evidence_requirements": ("validation_commands", "completion_report"),
        "handoff_preview_ref": "handoff-preview.edc-pr-011.execution",
        "write_back_location": "Planning thread 019f07b2-8968-7891-bd41-aed6f25a651c",
        "source_refs": ("docs/codex/PR_PLAN.md", "nexus/governance/handoff_records.py"),
    }
    data.update(overrides)
    return OperationalCommandDraft(**data)


def dispatch_candidate(**overrides):
    data = {
        "candidate_id": "dispatch-candidate.edc-pr-011.execution",
        "work_item_id": WORK_ITEM_ID,
        "agent_id": "agent.codex.execution",
        "runtime_instance_id": "runtime.codex.edc-pr-011.local",
        "eligible": False,
        "blocked_reasons": ("draft_only", "live_dispatch_blocked"),
        "source_refs": ("nexus/mq/dispatch_eligibility.py",),
    }
    data.update(overrides)
    return DispatchCandidateProjection(**data)


def handoff_preview(**overrides):
    data = {
        "preview_id": "handoff-preview.edc-pr-011.execution",
        "work_item_id": WORK_ITEM_ID,
        "target_agent_id": "agent.codex.execution",
        "target_runtime_instance_id": "runtime.codex.edc-pr-011.local",
        "task_card_ref": "fixture://work_items/EDC-PR-011/task_card",
        "write_back_location": "Planning thread 019f07b2-8968-7891-bd41-aed6f25a651c",
        "validation_commands": ("python -m pytest nexus/governance/tests/test_operational_commands.py -q",),
        "source_refs": ("docs/codex/SPEC.md",),
    }
    data.update(overrides)
    return HandoffDraftPreview(**data)
