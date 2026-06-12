from __future__ import annotations

from nexus.governance.workspace_init import (
    GovernanceSurfaceIndex,
    InitiationTemplateSet,
    TemplateProfileSelection,
    WorkspaceInitOutputBase,
    WorkspaceManifest,
)


WORKSPACE_ROOT = ".governance/workspaces/ws-421"
SOURCE_REFS = ("WBS V0.6", "L1.11.2", "PR9:7007b4a")


def valid_surface_index(**overrides: str) -> GovernanceSurfaceIndex:
    values = {
        "surface_index_id": "surface-index-ws-421",
        "workspace_root": WORKSPACE_ROOT,
        "readme_path": f"{WORKSPACE_ROOT}/README.md",
        "charter_path": f"{WORKSPACE_ROOT}/initiation/project-charter-stub.md",
        "stakeholder_authority_path": f"{WORKSPACE_ROOT}/initiation/stakeholder-authority-seed.md",
        "evidence_path": f"{WORKSPACE_ROOT}/evidence/",
        "decision_log_path": f"{WORKSPACE_ROOT}/decisions/",
        "feedback_path": f"{WORKSPACE_ROOT}/feedback/",
        "review_evidence_path": f"{WORKSPACE_ROOT}/review-evidence/",
        "planning_scope_path": f"{WORKSPACE_ROOT}/planning/scope.placeholder.md",
        "planning_requirements_path": f"{WORKSPACE_ROOT}/planning/requirements.placeholder.md",
        "planning_risk_path": f"{WORKSPACE_ROOT}/planning/risk.placeholder.md",
        "planning_dependency_path": f"{WORKSPACE_ROOT}/planning/dependencies.placeholder.md",
        "planning_backlog_wbs_path": f"{WORKSPACE_ROOT}/planning/backlog-wbs.placeholder.md",
        "planning_execution_plan_path": f"{WORKSPACE_ROOT}/planning/execution-plan.placeholder.md",
    }
    values.update(overrides)
    return GovernanceSurfaceIndex(**values)


def valid_template_set(**overrides: object) -> InitiationTemplateSet:
    values = {
        "template_set_ref": "workspace-template:standard-init:v1",
        "required_templates": (
            "WorkspaceManifest",
            "GovernanceSurfaceIndex",
            "ProjectCharterStub",
            "StakeholderAuthoritySeed",
            "EvidencePathSeed",
            "DecisionLogSeed",
            "FeedbackPathSeed",
            "PlanningSurfacePlaceholder",
        ),
        "required_surfaces": valid_surface_index().required_surface_names(),
        "trim_rules": (),
        "source_refs": SOURCE_REFS,
    }
    values.update(overrides)
    return InitiationTemplateSet(**values)


def valid_profile_selection(**overrides: object) -> TemplateProfileSelection:
    values = {
        "profile_id": "standard-init",
        "profile_version": "v1",
        "profile_source_ref": "workspace-template:standard-init:v1",
        "trim_rules_applied": (),
        "required_surface_exceptions": (),
        "selection_reason": "standard governed initiation workspace",
    }
    values.update(overrides)
    return TemplateProfileSelection(**values)


def init_item(item_type: str, status: str, **content: object) -> WorkspaceInitOutputBase:
    return WorkspaceInitOutputBase(
        item_id=f"{item_type.lower()}-ws-421",
        item_type=item_type,
        project_id="project-421",
        workspace_id="ws-421",
        source_authority_refs=SOURCE_REFS,
        status=status,
        owning_component="Workspace Init",
        consumer_component_refs=("Project Standardization",),
        notes="slice 002 fixture",
        content=content,
    )


def valid_seed_items() -> tuple[WorkspaceInitOutputBase, ...]:
    return (
        init_item("ProjectCharterStub", "seed"),
        init_item("StakeholderAuthoritySeed", "seed"),
        init_item("EvidencePathSeed", "structural"),
        init_item("DecisionLogSeed", "structural"),
        init_item("FeedbackPathSeed", "structural"),
        init_item("PlanningSurfacePlaceholder", "structural"),
    )


def valid_manifest(**overrides: object) -> WorkspaceManifest:
    surface_index = overrides.pop("surface_index", valid_surface_index())
    values = {
        "manifest_id": "manifest-ws-421",
        "workspace_id": "ws-421",
        "workspace_root": WORKSPACE_ROOT,
        "manifest_version": 1,
        "created_paths": surface_index.required_paths(),
        "seed_items": valid_seed_items(),
        "template_profile_ref": "workspace-template:standard-init:v1",
        "validation_report_ref": "validation-ws-421",
        "baseline_entry_command_ref": "cmd-submit-ws-421",
        "kernel_record_ref": None,
        "status": "validated",
        "source_refs": SOURCE_REFS,
        "surface_index": surface_index,
    }
    values.update(overrides)
    return WorkspaceManifest(**values)
