from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .kernel import AggregateState, GovernanceKernel, KernelRecord
from .no_go import NoGoBoundaryPolicy
from .projections import ProjectionSnapshot, build_projection_snapshot
from .schemas import ActorRef, CommandEnvelope
from .service_facade import GovernanceServiceFacade, ServiceCommandOutcome
from .source_authority import SourceAuthorityManifest
from .workspace_init import (
    GovernanceSurfaceIndex,
    WorkspaceInitOutputBase,
    WorkspaceManifest,
    validate_workspace_manifest,
)


AUTHORITY_REFS: tuple[str, ...] = (
    "WBS V0.6",
    "L1.11.12",
    "REAL_UAT:TestProject",
)
PROJECT_MARKER = ".nexus-real-uat-project"
INIT_FIELD_SPECS: tuple[dict[str, str], ...] = (
    {
        "key": "project_charter",
        "field": "Project charter",
        "heading": "Project Charter",
        "path_attr": "charter_path",
    },
    {
        "key": "stakeholder_authority",
        "field": "Stakeholder authority",
        "heading": "Stakeholder Authority",
        "path_attr": "stakeholder_authority_path",
    },
    {"key": "scope", "field": "Scope", "heading": "Scope", "path_attr": "planning_scope_path"},
    {
        "key": "requirements",
        "field": "Requirements",
        "heading": "Requirements",
        "path_attr": "planning_requirements_path",
    },
    {"key": "risks", "field": "Risks", "heading": "Risks", "path_attr": "planning_risk_path"},
    {
        "key": "dependencies",
        "field": "Dependencies",
        "heading": "Dependencies",
        "path_attr": "planning_dependency_path",
    },
    {
        "key": "backlog_wbs",
        "field": "Backlog/WBS",
        "heading": "Backlog WBS",
        "path_attr": "planning_backlog_wbs_path",
    },
    {
        "key": "execution_plan",
        "field": "Execution plan",
        "heading": "Execution Plan",
        "path_attr": "planning_execution_plan_path",
    },
)


@dataclass(frozen=True)
class RealTestProjectResult:
    project_name: str
    project_id: str
    workspace_id: str
    project_root: Path
    workspace_root: Path
    canonical_records_path: Path
    projection_path: Path
    desktop_state_path: Path
    kernel_state: AggregateState
    service_outcome: ServiceCommandOutcome


@dataclass(frozen=True)
class CleanupResult:
    removed: bool
    project_root: Path


def create_real_test_project(*, root: Path | str, project_name: str = "TestProject") -> RealTestProjectResult:
    project_slug = _slug(project_name)
    root_path = Path(root).resolve()
    project_root = root_path / project_slug
    workspace_root = project_root / "workspace"
    _prepare_project_root(project_root)

    surface_index = _create_workspace_surfaces(workspace_root)
    manifest = _workspace_manifest(project_name, project_slug, workspace_root, surface_index)
    validation = validate_workspace_manifest(manifest)
    if not validation.accepted:
        raise ValueError(f"workspace manifest rejected: {validation.to_evidence()}")

    actor = ActorRef(actor_id="alex:real-uat", role="uat")
    kernel = _kernel_ready_for_workspace_init(actor)
    service = GovernanceServiceFacade(
        source_manifest=_source_authority_manifest(),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=kernel,
    )
    command = _submit_workspace_init_command(
        actor=actor,
        workspace_id=manifest.workspace_id,
        manifest_ref=manifest.manifest_id,
        validation_report_ref=manifest.validation_report_ref,
        expected_version=kernel.state.version,
        idempotency_key=f"real-uat-submit-{project_slug}",
    )
    service_outcome = service.handle(command, intent={"action": "real_uat_workspace_init"})
    if service_outcome.status != "accepted":
        raise ValueError(f"service command rejected: {service_outcome.to_evidence()}")

    canonical_records_path = project_root / "canonical-records.json"
    projection_path = project_root / "projection.json"
    desktop_state_path = project_root / "desktop-state.json"
    projection = _build_real_projection(project_name, manifest, kernel)
    _write_json(
        canonical_records_path,
        {
            "project_name": project_name,
            "project_id": f"project:{project_slug}",
            "workspace_id": manifest.workspace_id,
            "kernel_state": _aggregate_state_to_json(kernel.state),
            "records": [_record_to_json(record) for record in kernel.records],
            "service_outcome": service_outcome.to_evidence(),
            "workspace_manifest": _manifest_to_json(manifest),
            "generated_at": _now(),
        },
    )
    _write_json(projection_path, projection.to_evidence())
    _write_json(
        desktop_state_path,
        _desktop_state(
            project_name=project_name,
            manifest=manifest,
            projection=projection,
            kernel=kernel,
            service_outcome=service_outcome,
            canonical_records_path=canonical_records_path,
            projection_path=projection_path,
        ),
    )
    return RealTestProjectResult(
        project_name=project_name,
        project_id=f"project:{project_slug}",
        workspace_id=manifest.workspace_id,
        project_root=project_root,
        workspace_root=workspace_root,
        canonical_records_path=canonical_records_path,
        projection_path=projection_path,
        desktop_state_path=desktop_state_path,
        kernel_state=kernel.state,
        service_outcome=service_outcome,
    )


def load_real_test_project_state(path: Path | str) -> dict[str, Any]:
    state = json.loads(Path(path).read_text(encoding="utf-8"))
    if state.get("source_mode") != "real_test_project" or state.get("fixture_only") is not False:
        raise ValueError("desktop state is not a real TestProject state")
    return state


def cleanup_real_test_project(*, project_root: Path | str) -> CleanupResult:
    root = Path(project_root).resolve()
    if not root.exists():
        return CleanupResult(False, root)
    marker = root / PROJECT_MARKER
    if not marker.exists():
        raise ValueError("refusing cleanup without real UAT project marker")
    shutil.rmtree(root)
    return CleanupResult(True, root)


def save_real_test_project_init(
    *,
    root: Path | str,
    project_name: str = "TestProject",
    init_values: dict[str, Any],
) -> dict[str, Any]:
    project_slug = _slug(project_name)
    project_root = Path(root).resolve() / project_slug
    marker = project_root / PROJECT_MARKER
    if not marker.exists():
        raise ValueError("real TestProject must exist before saving init draft")

    missing = tuple(spec["key"] for spec in INIT_FIELD_SPECS if not str(init_values.get(spec["key"], "")).strip())
    if missing:
        raise ValueError(f"missing init fields: {', '.join(missing)}")

    workspace_root = project_root / "workspace"
    surface_index = _surface_index_for_workspace(workspace_root)
    normalized_values = {spec["key"]: str(init_values[spec["key"]]).strip() for spec in INIT_FIELD_SPECS}
    for spec in INIT_FIELD_SPECS:
        target = Path(getattr(surface_index, spec["path_attr"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# {spec['heading']}\n\n{normalized_values[spec['key']]}\n", encoding="utf-8")

    init_draft_path = workspace_root / "initiation" / "project-init-draft.json"
    _write_json(
        init_draft_path,
        {
            "project_name": project_name,
            "project_id": f"project:{project_slug}",
            "workspace_id": f"workspace:{project_slug}",
            "init_values": normalized_values,
            "status": "drafted_local",
            "non_authoritative": True,
            "generated_at": _now(),
        },
    )

    desktop_state_path = project_root / "desktop-state.json"
    state = load_real_test_project_state(desktop_state_path)
    requirements = _init_requirements_from_surface(surface_index, status="drafted")
    state["display_state"]["init_status"] = "drafted_local"
    state["display_state"]["init_values"] = normalized_values
    state["display_state"]["init_requirements"] = requirements
    state["display_state"]["notes"] = tuple(state["display_state"].get("notes", ())) + (
        f"Project init draft saved locally: {init_draft_path}",
        "Init draft still requires Governance Service routing before canonical change.",
    )
    state["projection"]["payload"]["init_status"] = "drafted_local"
    state["projection"]["payload"]["init_requirements"] = requirements
    state["projection"]["payload"]["project_init_draft_path"] = str(init_draft_path)
    _write_json(Path(state["projection_path"]), state["projection"])
    _write_json(desktop_state_path, state)
    return state


def default_real_uat_root(repo_root: Path | str | None = None) -> Path:
    root = Path(repo_root).resolve() if repo_root else _find_repo_root(Path.cwd())
    return root / "verification" / "4.21" / "real-uat"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local 4.21 real TestProject UAT operations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--root", type=Path, default=None)
    create_parser.add_argument("--project-name", default="TestProject")
    create_parser.add_argument("--repo-root", type=Path, default=None)

    read_parser = subparsers.add_parser("read")
    read_parser.add_argument("--root", type=Path, default=None)
    read_parser.add_argument("--project-name", default="TestProject")
    read_parser.add_argument("--repo-root", type=Path, default=None)

    cleanup_parser = subparsers.add_parser("cleanup")
    cleanup_parser.add_argument("--root", type=Path, default=None)
    cleanup_parser.add_argument("--project-name", default="TestProject")
    cleanup_parser.add_argument("--repo-root", type=Path, default=None)

    save_init_parser = subparsers.add_parser("save-init")
    save_init_parser.add_argument("--root", type=Path, default=None)
    save_init_parser.add_argument("--project-name", default="TestProject")
    save_init_parser.add_argument("--repo-root", type=Path, default=None)
    save_init_parser.add_argument("--payload-json", required=True)

    args = parser.parse_args(argv)
    root = args.root or default_real_uat_root(args.repo_root)
    project_root = Path(root).resolve() / _slug(args.project_name)
    if args.command == "create":
        result = create_real_test_project(root=root, project_name=args.project_name)
        print(json.dumps(_result_to_json(result), indent=2, sort_keys=True))
        return 0
    if args.command == "read":
        print(json.dumps(load_real_test_project_state(project_root / "desktop-state.json"), indent=2, sort_keys=True))
        return 0
    if args.command == "cleanup":
        result = cleanup_real_test_project(project_root=project_root)
        print(json.dumps({"removed": result.removed, "project_root": str(result.project_root)}, sort_keys=True))
        return 0
    if args.command == "save-init":
        state = save_real_test_project_init(
            root=root,
            project_name=args.project_name,
            init_values=json.loads(args.payload_json),
        )
        print(json.dumps(state, indent=2, sort_keys=True))
        return 0
    raise ValueError(f"unknown command: {args.command}")


def _prepare_project_root(project_root: Path) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / PROJECT_MARKER).write_text("real-uAT-test-project\n".lower(), encoding="utf-8")


def _create_workspace_surfaces(workspace_root: Path) -> GovernanceSurfaceIndex:
    surface_index = _surface_index_for_workspace(workspace_root)
    for raw_path in surface_index.required_paths():
        path = Path(raw_path)
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {path.stem}\n\nGenerated for real TestProject UAT.\n", encoding="utf-8")
        else:
            path.mkdir(parents=True, exist_ok=True)
    return surface_index


def _surface_index_for_workspace(workspace_root: Path) -> GovernanceSurfaceIndex:
    return GovernanceSurfaceIndex(
        surface_index_id="surface-index-testproject",
        workspace_root=str(workspace_root),
        readme_path=str(workspace_root / "README.md"),
        charter_path=str(workspace_root / "initiation" / "project-charter-stub.md"),
        stakeholder_authority_path=str(workspace_root / "initiation" / "stakeholder-authority-seed.md"),
        evidence_path=str(workspace_root / "evidence"),
        decision_log_path=str(workspace_root / "decisions"),
        feedback_path=str(workspace_root / "feedback"),
        review_evidence_path=str(workspace_root / "review-evidence"),
        planning_scope_path=str(workspace_root / "planning" / "scope.placeholder.md"),
        planning_requirements_path=str(workspace_root / "planning" / "requirements.placeholder.md"),
        planning_risk_path=str(workspace_root / "planning" / "risk.placeholder.md"),
        planning_dependency_path=str(workspace_root / "planning" / "dependencies.placeholder.md"),
        planning_backlog_wbs_path=str(workspace_root / "planning" / "backlog-wbs.placeholder.md"),
        planning_execution_plan_path=str(workspace_root / "planning" / "execution-plan.placeholder.md"),
    )


def _workspace_manifest(
    project_name: str,
    project_slug: str,
    workspace_root: Path,
    surface_index: GovernanceSurfaceIndex,
) -> WorkspaceManifest:
    seed_items = (
        _init_item("ProjectCharterStub", "seed", project_slug),
        _init_item("StakeholderAuthoritySeed", "seed", project_slug),
        _init_item("EvidencePathSeed", "structural", project_slug),
        _init_item("DecisionLogSeed", "structural", project_slug),
        _init_item("FeedbackPathSeed", "structural", project_slug),
        _init_item("PlanningSurfacePlaceholder", "structural", project_slug),
    )
    return WorkspaceManifest(
        manifest_id=f"manifest-{project_slug}",
        workspace_id=f"workspace:{project_slug}",
        workspace_root=str(workspace_root),
        manifest_version=1,
        created_paths=surface_index.required_paths(),
        seed_items=seed_items,
        template_profile_ref="workspace-template:standard-init:v1",
        validation_report_ref=f"validation-{project_slug}",
        baseline_entry_command_ref=f"cmd-submit-{project_slug}",
        kernel_record_ref=None,
        status="validated",
        source_refs=AUTHORITY_REFS,
        surface_index=surface_index,
    )


def _init_item(item_type: str, status: str, project_slug: str) -> WorkspaceInitOutputBase:
    return WorkspaceInitOutputBase(
        item_id=f"{item_type.lower()}-{project_slug}",
        item_type=item_type,
        project_id=f"project:{project_slug}",
        workspace_id=f"workspace:{project_slug}",
        source_authority_refs=AUTHORITY_REFS,
        status=status,
        owning_component="Workspace Init",
        consumer_component_refs=("Governance Service", "Desktop UAT"),
        notes="real TestProject UAT seed",
    )


def _kernel_ready_for_workspace_init(actor: ActorRef) -> GovernanceKernel:
    kernel = GovernanceKernel()
    prelude = (
        ("InitializeAuthority", 0, "real-uat-authority"),
        ("MarkKernelReady", 1, "real-uat-kernel-ready"),
        ("RefreshProjectionCheckpoint", 2, "real-uat-projection-contract"),
    )
    for command_type, expected_version, idempotency_key in prelude:
        result = kernel.apply(
            CommandEnvelope(
                command_type=command_type,
                actor=actor,
                authority_refs=AUTHORITY_REFS,
                expected_version=expected_version,
                idempotency_key=idempotency_key,
                payload={"source_refs": AUTHORITY_REFS, "test_environment": True},
            )
        )
        if not result.accepted:
            raise ValueError(f"kernel prelude rejected {command_type}: {result.to_evidence()}")
    return kernel


def _submit_workspace_init_command(
    *,
    actor: ActorRef,
    workspace_id: str,
    manifest_ref: str,
    validation_report_ref: str,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="SubmitWorkspaceInitRecord",
        actor=actor,
        authority_refs=AUTHORITY_REFS,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        payload={
            "expected_kernel_version": expected_version,
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "manifest_ref": manifest_ref,
            "source_refs": AUTHORITY_REFS,
            "target_ref": "layer1-governance",
            "expected_state": "projection_contract_ready",
            "validation_report_ref": validation_report_ref,
            "workspace_id": workspace_id,
            "authorization_source": "Nova-approved-baseline",
        },
        affects_state=True,
        command_id=f"cmd:{idempotency_key}",
        target_ref="layer1-governance",
        expected_state="projection_contract_ready",
        source_refs=AUTHORITY_REFS,
        authorization_source="Nova-approved-baseline",
    )


def _build_real_projection(
    project_name: str,
    manifest: WorkspaceManifest,
    kernel: GovernanceKernel,
) -> ProjectionSnapshot:
    last_record_id = kernel.state.last_record_id or "none"
    return build_projection_snapshot(
        projection_type="mission-control",
        workspace_id=manifest.workspace_id,
        source_checkpoint=last_record_id,
        payload={
            "project_name": project_name,
            "workspace_id": manifest.workspace_id,
            "workspace_root": manifest.workspace_root,
            "init_requirements": _init_requirements(manifest),
            "kernel_state": kernel.state.state,
            "kernel_version": kernel.state.version,
            "kernel_record_count": len(kernel.records),
            "last_record_id": last_record_id,
            "service_state": "real local test",
            "sync_state": "projection current",
            "blocked_items": 0,
            "active_slice": "L1GOV-SLICE-012-REAL-UAT",
        },
        authority_refs=AUTHORITY_REFS,
    )


def _desktop_state(
    *,
    project_name: str,
    manifest: WorkspaceManifest,
    projection: ProjectionSnapshot,
    kernel: GovernanceKernel,
    service_outcome: ServiceCommandOutcome,
    canonical_records_path: Path,
    projection_path: Path,
) -> dict[str, Any]:
    return {
        "slice_id": "L1GOV-SLICE-012",
        "source_mode": "real_test_project",
        "fixture_only": False,
        "non_authoritative": True,
        "live_execution_invoked": False,
        "canonical_authority": "GovernanceKernel",
        "service_boundary": "GovernanceService",
        "canonical_records_path": str(canonical_records_path),
        "projection_path": str(projection_path),
        "projection": projection.to_evidence(),
        "service_outcome": service_outcome.to_evidence(),
        "stale_refresh": {"states": ("stale", "rebuilding", "current")},
        "display_state": {
            "workspace_name": project_name,
            "freshness_index": 2,
            "init_status": "draft_required",
            "init_requirements": _init_requirements(manifest),
            "project_summary": {
                "accepted_slices": 12,
                "active_slice": "L1GOV-SLICE-012-REAL-UAT",
                "blocked_items": 0,
                "canonical_records": len(kernel.records),
            },
            "modules": {
                "mission_control": {
                    "title": "Mission Control",
                    "summary": "Real TestProject projection loaded from local Governance Service output.",
                },
                "project_init": {
                    "title": "Project Init",
                    "summary": "Required initialization info is seeded in the workspace and must route through Governance Service.",
                },
                "standardization": {
                    "title": "Standardization",
                    "summary": "Pending later UAT; no local approval or baseline promotion.",
                },
                "monitor_hitl": {
                    "title": "Monitor/HITL",
                    "summary": "Direct UI approval remains blocked; decisions must route through Monitor/HITL.",
                },
                "delivery_feedback": {
                    "title": "Delivery Feedback",
                    "summary": "No closeout claim is made.",
                },
                "notes_evidence": {
                    "title": "Notes Evidence",
                    "summary": "Real UAT evidence is written under verification/4.21/real-uat.",
                },
            },
            "workspaces": (
                {"id": manifest.workspace_id, "label": project_name, "freshness": "current"},
            ),
            "notes": (
                f"Kernel canonical record: {kernel.state.last_record_id}",
                f"Projection checkpoint: {projection.source_checkpoint}",
                "Desktop state is non-authoritative and read-only.",
                "Runs local test bridge only.",
            ),
            "service_state": "real local test",
            "sync_state": "projection current",
        },
        "future_integration_boundary": {
            "daemon_controller_bridge": "disabled_future_boundary",
            "can_execute_live_calls": False,
        },
    }


def _init_requirements(manifest: WorkspaceManifest) -> tuple[dict[str, str], ...]:
    return _init_requirements_from_surface(manifest.surface_index, status="needs_input")


def _init_requirements_from_surface(
    surface: GovernanceSurfaceIndex, *, status: str
) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "field": spec["field"],
            "status": status,
            "path": getattr(surface, spec["path_attr"]),
        }
        for spec in INIT_FIELD_SPECS
    )


def _source_authority_manifest() -> SourceAuthorityManifest:
    return SourceAuthorityManifest(
        parent_solution_design_version="V0.8.5",
        wbs_version="V0.6",
        accepted_subtopics=tuple(f"L1.11.{index}" for index in range(1, 11)),
        integration_review_version="V0.2",
        integration_review_status="Accepted",
        final_assessment_disposition="READY_FOR_IMPLEMENTATION_TASK_PACKAGE_PREPARATION",
        direct_coding_disposition="NO_GO_FOR_DIRECT_CODING",
        slice001_package_decision="APPROVE_FIRST_SLICE_TASK_PACKAGE",
        slice001_authorization_decision="AUTHORIZE_SLICE_001_IMPLEMENTATION",
        required_commits=("7e2774d", "1c29365", "fce663a", "70ba8aa", "4dfd3d8", "f9eaa5b"),
        shared_docs_remote="git@github.com:Nova-Mini/Nova-Jarvis-Shared-Docs.git",
        source_root="D:/Nova-Jarvis-Shared-Docs",
    )


def _manifest_to_json(manifest: WorkspaceManifest) -> dict[str, Any]:
    return {
        "manifest_id": manifest.manifest_id,
        "workspace_id": manifest.workspace_id,
        "workspace_root": manifest.workspace_root,
        "manifest_version": manifest.manifest_version,
        "status": manifest.status,
        "source_refs": list(manifest.source_refs),
        "created_paths": list(manifest.created_paths),
    }


def _aggregate_state_to_json(state: AggregateState) -> dict[str, Any]:
    return {
        "aggregate_id": state.aggregate_id,
        "state": state.state,
        "version": state.version,
        "last_record_id": state.last_record_id,
        "authority_refs": list(state.authority_refs),
    }


def _record_to_json(record: KernelRecord) -> dict[str, Any]:
    return {
        "record_id": record.record_id,
        "aggregate_id": record.aggregate_id,
        "previous_version": record.previous_version,
        "version": record.version,
        "previous_state": record.previous_state,
        "new_state": record.new_state,
        "command_type": record.command_type,
        "payload": record.payload,
        "authority_refs": list(record.authority_refs),
        "actor_id": record.actor_id,
    }


def _result_to_json(result: RealTestProjectResult) -> dict[str, Any]:
    return {
        "project_name": result.project_name,
        "project_id": result.project_id,
        "workspace_id": result.workspace_id,
        "project_root": str(result.project_root),
        "workspace_root": str(result.workspace_root),
        "canonical_records_path": str(result.canonical_records_path),
        "projection_path": str(result.projection_path),
        "desktop_state_path": str(result.desktop_state_path),
        "kernel_state": _aggregate_state_to_json(result.kernel_state),
        "service_outcome": result.service_outcome.to_evidence(),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "nexus" / "governance").exists() and (candidate / ".git").exists():
            return candidate
    return current


def _slug(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    slug = "-".join(part for part in slug.split("-") if part)
    if not slug:
        raise ValueError("project_name must contain at least one alphanumeric character")
    return slug


def _now() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
