from __future__ import annotations

import json
import re
from pathlib import Path

from .fixtures.client_test_surface import DESKTOP_APP_ROOT, DESKTOP_FIXTURE_PATH


REQUIRED_VIEW_IDS = (
    "work_items",
    "work_item_detail",
    "agents",
    "runtime_worktrees",
    "evidence_runs",
    "pr_uat_closeout",
    "inbox_attention",
    "settings_boundaries",
)

REQUIRED_WORK_ITEM_IDS = (
    "EDC-PR-006",
    "EDC-PR-007",
    "EDC-PR-008",
    "EDC-PR-009",
    "EDC-PR-010",
    "EDC-PR-011",
)
REQUIRED_AGENT_ROLES = (
    "codex_planning",
    "codex_execution",
    "reviewer_reducer",
    "owner_uat",
)

REQUIRED_RUNTIME_WORKTREE_IDS = (
    "EDC-PR-006",
    "EDC-PR-007",
    "EDC-PR-008",
    "EDC-PR-009",
)

REQUIRED_EVIDENCE_RUN_IDS = (
    "EDC-PR-006",
    "EDC-PR-007",
    "EDC-PR-008",
    "EDC-PR-009",
    "EDC-PR-010",
    "EDC-PR-011",
)
REQUIRED_PR_STACK_IDS = (
    "EDC-PR-001",
    "EDC-PR-002",
    "EDC-PR-003",
    "EDC-PR-004",
    "EDC-PR-005",
    "EDC-PR-006",
    "EDC-PR-007",
    "EDC-PR-008",
    "EDC-PR-009",
    "EDC-PR-010",
    "EDC-PR-011",
)
REQUIRED_ATTENTION_IDS = (
    "owner_uat_needed",
    "merge_blocked",
    "runtime_startup_separate_authorization",
    "dependency_install_not_authorized",
    "broker_nats_mutation_blocked",
    "live_dispatch_blocked",
)

REQUIRED_BOUNDARY_IDS = (
    "planning_execution_role_boundary",
    "openclaw_private_material_exclusion",
    "nexus_local_test_vs_openclaw_live_nats",
    "worktree_location_policy",
    "evidence_before_claim",
    "pr_mapping_separation",
    "no_owner_uat_automation",
)
REQUIRED_TASK_CARD_FIELDS = (
    "goal",
    "scope_summary",
    "non_goals",
    "editable_boundary",
    "validation_commands",
    "risks",
    "write_back_location",
)

REQUIRED_DESKTOP_FILES = (
    "package.json",
    "package-lock.json",
    ".gitignore",
    "README.md",
    "src/index.html",
    "src/main.js",
    "src/styles.css",
    "src/fixtures/edc_workbench_shell_state.json",
    "src-tauri/Cargo.toml",
    "src-tauri/tauri.conf.json",
    "src-tauri/icons/icon.ico",
    "src-tauri/src/main.rs",
)


def read_app_file(relative_path: str) -> str:
    return (DESKTOP_APP_ROOT / relative_path).read_text(encoding="utf-8")


def load_fixture() -> dict[str, object]:
    return json.loads(DESKTOP_FIXTURE_PATH.read_text(encoding="utf-8"))


def test_workbench_shell_files_exist_under_approved_boundary() -> None:
    for relative_path in REQUIRED_DESKTOP_FILES:
        path = DESKTOP_APP_ROOT / relative_path
        assert path.exists(), relative_path
        assert path.is_file(), relative_path
        assert path.stat().st_size > 0, relative_path

    assert DESKTOP_APP_ROOT.as_posix().endswith("apps/l1gov-desktop-client")


def test_workbench_fixture_declares_shell_scope_and_safety_boundaries() -> None:
    fixture = load_fixture()

    assert fixture["read_model_id"] == "edc-workbench-shell-2026-06-27"
    assert fixture["surface"] == "Nexus Agent Coding Team Workbench"
    assert fixture["fixture_only"] is True
    assert fixture["non_authoritative"] is True
    assert fixture["live_execution_invoked"] is False
    assert fixture["runtime_startup_allowed"] is False
    assert fixture["dependency_install_allowed"] is False
    assert fixture["broker_mutation_allowed"] is False
    assert fixture["live_dispatch_allowed"] is False
    assert fixture["canonical_mutation_allowed"] is False
    assert fixture["owner_uat_accepted"] is False
    assert fixture["uat_pass_claimed"] is False
    assert fixture["merge_approved"] is False
    assert fixture["production_readiness_claimed"] is False
    assert fixture["live_readiness_claimed"] is False
    assert fixture["owner_uat_after"] == "EDC-PR-010"


def test_workbench_fixture_maps_edc_ids_separately_from_github_pr_numbers() -> None:
    fixture = load_fixture()
    mappings = fixture["pr_mappings"]

    for mapping in mappings:
        assert re.fullmatch(r"EDC-PR-\d{3}", mapping["internal_id"])
        assert str(mapping["internal_id"]) != str(mapping["github_pr_number"])

    by_id = {mapping["internal_id"]: mapping for mapping in mappings}
    assert by_id["EDC-PR-006"]["github_pr_number"] == 32
    assert by_id["EDC-PR-007"]["github_pr_number"] == 33
    assert by_id["EDC-PR-007"]["github_pr_label"] == "#33"
    assert by_id["EDC-PR-007"]["status"] == "draft_pr_open"
    assert by_id["EDC-PR-007"]["branch"] == "codex/edc-pr-007-desktop-workbench-shell"
    assert by_id["EDC-PR-007"]["base_commit"] == "d6a8b55"
    assert by_id["EDC-PR-008"]["github_pr_number"] == 34
    assert by_id["EDC-PR-008"]["github_pr_label"] == "#34"
    assert by_id["EDC-PR-008"]["status"] == "draft_pr_open"
    assert by_id["EDC-PR-008"]["branch"] == "codex/edc-pr-008-work-items-surface"
    assert by_id["EDC-PR-008"]["base_commit"] == "e14d71e"
    assert by_id["EDC-PR-010"]["github_pr_number"] == 36
    assert by_id["EDC-PR-010"]["github_pr_label"] == "#36"
    assert by_id["EDC-PR-010"]["status"] == "draft_pr_open"
    assert by_id["EDC-PR-004"]["baseline_role"] == "superseded_prototype"
    assert by_id["EDC-PR-005"]["baseline_role"] == "superseded_prototype"
    assert all(mapping["baseline_role"] != "uat_baseline" for mapping in mappings)


def test_workbench_fixture_has_required_views_without_hash_navigation() -> None:
    fixture = load_fixture()
    views = fixture["views"]
    view_ids = tuple(view["id"] for view in views)

    assert view_ids == REQUIRED_VIEW_IDS
    for view in views:
        assert view["implementation_pr"] in {"EDC-PR-008", "EDC-PR-009", "EDC-PR-010"}
        assert view["readiness_state"] in {
            "implemented",
            "in_review",
            "planned",
            "blocked_until_later_slice",
            "shell_only",
        }
        assert view["nav_target"] == view["id"]
        assert not view["nav_target"].startswith("#")
        assert "anchor" not in view["navigation_semantics"]
        assert "scroll" not in view["navigation_semantics"]


def test_workbench_first_screen_and_renderer_use_real_view_switching() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")

    assert "Nexus Agent Coding Team Workbench" in html
    assert "Nexus L1 Governance UX Test Surface" not in html
    assert "L1GOV-SLICE-012" not in html
    assert 'fetch("./fixtures/edc_workbench_shell_state.json")' in main_js
    assert "activeViewId" in main_js
    assert "renderActiveView" in main_js
    assert "renderWorkItemsBoard" in main_js
    assert "renderWorkItemDetail" in main_js
    assert "selectWorkItem" in main_js
    assert "selectView" in main_js
    assert "scrollIntoView" not in main_js
    assert "location.hash" not in main_js
    assert 'href="#' not in html

    for view_id in REQUIRED_VIEW_IDS:
        assert f'data-view-id="{view_id}"' in html


def test_workbench_fixture_contains_work_item_board_and_detail_records() -> None:
    fixture = load_fixture()
    work_items = fixture["work_items"]
    by_id = {item["internal_id"]: item for item in work_items}

    assert tuple(by_id) == REQUIRED_WORK_ITEM_IDS
    assert fixture["selected_work_item_id"] == "EDC-PR-011"

    for item in work_items:
        assert re.fullmatch(r"EDC-PR-\d{3}", item["internal_id"])
        assert str(item["internal_id"]) != str(item["github_pr_number"])
        assert item["status"] in {"review", "running", "planned"}
        assert item["lane"] in {"draft_pr_open", "in_progress", "planned"}
        assert item["readiness_state"] in {"validated", "in_review", "planned", "blocked"}
        assert item["evidence_state"] in {"present", "not_run_by_scope", "missing"}
        assert item["owner_uat_state"] in {"not_applicable", "not_ready", "awaiting_owner"}
        assert item["runtime_authorization_state"] in {"not_required", "hold"}

        task_card = item["task_card"]
        for field in REQUIRED_TASK_CARD_FIELDS:
            assert task_card[field], f"{item['internal_id']} missing task card {field}"

    assert by_id["EDC-PR-006"]["github_pr_number"] == 32
    assert by_id["EDC-PR-007"]["github_pr_number"] == 33
    assert by_id["EDC-PR-008"]["github_pr_number"] == 34
    assert by_id["EDC-PR-008"]["github_pr_label"] == "#34"
    assert by_id["EDC-PR-008"]["branch"] == "codex/edc-pr-008-work-items-surface"
    assert by_id["EDC-PR-008"]["worktree"].endswith(".worktrees\\edc-pr-008-work-items-surface")
    assert by_id["EDC-PR-008"]["base_commit"] == "e14d71e"
    assert by_id["EDC-PR-009"]["lane"] == "draft_pr_open"
    assert by_id["EDC-PR-009"]["github_pr_number"] == 35
    assert by_id["EDC-PR-009"]["github_pr_label"] == "#35"
    assert by_id["EDC-PR-009"]["branch"] == "codex/edc-pr-009-agents-runtime-worktrees"
    assert by_id["EDC-PR-009"]["worktree"].endswith(".worktrees\\edc-pr-009-agents-runtime-worktrees")
    assert by_id["EDC-PR-009"]["base_commit"] == "a2a9778"
    assert by_id["EDC-PR-010"]["github_pr_number"] == 36
    assert by_id["EDC-PR-010"]["github_pr_label"] == "#36"
    assert by_id["EDC-PR-010"]["owner_uat_state"] == "awaiting_owner"
    assert by_id["EDC-PR-011"]["github_pr_number"] == 37
    assert by_id["EDC-PR-011"]["github_pr_label"] == "#37"
    assert by_id["EDC-PR-011"]["branch"] == "codex/edc-pr-011-agent-runtime-command-drafts"
    assert by_id["EDC-PR-011"]["worktree"].endswith(".worktrees\\edc-pr-011-agent-runtime-command-drafts")
    assert by_id["EDC-PR-011"]["base_commit"] == "dd4f9b0"
    assert by_id["EDC-PR-011"]["owner_uat_state"] == "awaiting_owner"


def test_workbench_work_items_and_detail_have_distinct_render_targets() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")

    for element_id in (
        "work-items-region",
        "work-item-board",
        "work-item-detail-region",
        "detail-internal-id",
        "detail-goal",
        "detail-scope",
        "detail-boundaries",
        "detail-validation",
        "detail-evidence",
        "detail-pr-mapping",
        "detail-risk-list",
        "detail-writeback",
    ):
        assert f'id="{element_id}"' in html

    assert "selectedWorkItemId" in main_js
    assert "state.selectedWorkItemId = workItemId" in main_js
    assert "data-work-item-id" in main_js
    assert "state.workItemsById[state.selectedWorkItemId]" in main_js
    assert '$("work-items-region").hidden = regionName !== "work_items"' in main_js
    assert '$("work-item-detail-region").hidden = regionName !== "work_item_detail"' in main_js
    assert '$("placeholder-region").hidden = regionName !== "placeholder"' in main_js
    assert '! ["work_items", "work_item_detail"].includes(regionName)' not in main_js
    assert '!["work_items", "work_item_detail"].includes(regionName)' not in main_js
    assert "button.innerHTML" not in main_js
    assert "append(topRow, title, stateMeta, branchMeta)" in main_js


def test_workbench_fixture_contains_agent_team_records_and_boundaries() -> None:
    fixture = load_fixture()
    agents = fixture["agents"]
    by_role = {agent["role_id"]: agent for agent in agents}

    assert tuple(by_role) == REQUIRED_AGENT_ROLES
    assert by_role["codex_planning"]["current_assignment_id"] == "EDC-PR-009-planning-review"
    assert by_role["codex_execution"]["current_assignment_id"] == "EDC-PR-009-implementation"
    assert by_role["reviewer_reducer"]["reducer_owner_for"] == ["EDC-PR-009"]
    assert by_role["owner_uat"]["availability"] == "after_edc_pr_010"

    for agent in agents:
        assert agent["display_name"]
        assert agent["authority_note"]
        assert agent["allowed_actions"]
        assert agent["forbidden_actions"]
        assert "live_dispatch" in agent["forbidden_actions"]
        assert "credential_access" in agent["forbidden_actions"]
        assert "private_session_access" in agent["forbidden_actions"]

    assert "owner_uat_acceptance" not in by_role["codex_execution"]["allowed_actions"]
    assert "automated_validation" not in by_role["owner_uat"]["allowed_actions"]


def test_workbench_fixture_contains_runtime_worktree_records_and_nats_boundary() -> None:
    fixture = load_fixture()
    runtime_records = fixture["runtime_worktrees"]
    by_id = {record["internal_id"]: record for record in runtime_records}

    assert tuple(by_id) == REQUIRED_RUNTIME_WORKTREE_IDS
    assert by_id["EDC-PR-008"]["github_pr_number"] == 34
    assert by_id["EDC-PR-009"]["github_pr_number"] == 35
    assert by_id["EDC-PR-009"]["github_pr_label"] == "#35"
    assert by_id["EDC-PR-009"]["branch"] == "codex/edc-pr-009-agents-runtime-worktrees"
    assert by_id["EDC-PR-009"]["worktree"].endswith(".worktrees\\edc-pr-009-agents-runtime-worktrees")
    assert by_id["EDC-PR-009"]["base_commit"] == "a2a9778"
    assert by_id["EDC-PR-009"]["current_slice"] is True

    for record in runtime_records:
        assert record["runtime_authorization_state"] in {"hold", "not_required"}
        assert record["startup_allowed"] is False
        assert record["dependency_install_allowed"] is False
        assert record["broker_mutation_allowed"] is False
        assert record["live_dispatch_allowed"] is False
        assert record["cleanup_allowed"] is False
        assert record["safety_state"] in {"inspection_only", "runtime_hold"}

    nats = fixture["nats_boundary"]
    assert nats["local_test"]["nats"] == "127.0.0.1:7422"
    assert nats["local_test"]["monitor"] == "http://127.0.0.1:8422/varz"
    assert nats["local_test"]["use_allowed"] is False
    assert nats["openclaw_live"]["nats"] == "127.0.0.1:4222"
    assert nats["openclaw_live"]["use_allowed"] is False
    assert nats["openclaw_live"]["mutation_allowed"] is False


def test_workbench_agents_and_runtime_views_have_dedicated_render_targets() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")

    for element_id in (
        "agents-region",
        "agent-team-list",
        "runtime-worktrees-region",
        "runtime-worktree-list",
        "nats-boundary",
    ):
        assert f'id="{element_id}"' in html

    assert "renderAgentsView" in main_js
    assert "renderRuntimeWorktreesView" in main_js
    assert '$("agents-region").hidden = regionName !== "agents"' in main_js
    assert '$("runtime-worktrees-region").hidden = regionName !== "runtime_worktrees"' in main_js
    assert "state.agentsByRole" in main_js
    assert "state.runtimeWorktreesById" in main_js

def test_workbench_shell_exposes_global_context_and_blocked_authority() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")
    fixture = load_fixture()

    for element_id in (
        "project-name",
        "project-path",
        "branch-context",
        "worktree-context",
        "internal-sequence",
        "pr-mapping-list",
        "authority-chips",
        "view-title",
        "view-purpose",
        "view-owner",
        "safety-list",
    ):
        assert f'id="{element_id}"' in html

    assert fixture["base_decision"]["continue_from"] == "EDC-PR-006 / GitHub PR #32"
    assert fixture["base_decision"]["bypass"] == ["EDC-PR-004 / GitHub PR #30", "EDC-PR-005 / GitHub PR #31"]
    assert "runtime_hold" in main_js
    assert "dependency_install_not_authorized" in main_js
    assert "broker_nats_mutation_blocked" in main_js
    assert "live_dispatch_blocked" in main_js


def test_workbench_desktop_files_do_not_contain_live_execution_paths() -> None:
    scanned_files = [
        DESKTOP_APP_ROOT / "src/index.html",
        DESKTOP_APP_ROOT / "src/main.js",
        DESKTOP_APP_ROOT / "src/styles.css",
        DESKTOP_FIXTURE_PATH,
        DESKTOP_APP_ROOT / "src-tauri/src/main.rs",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in scanned_files)
    forbidden_terms = (
        "invoke(",
        "@tauri-apps/api",
        "websocket",
        "localstorage",
        "sessionstorage",
        "indexeddb",
        "private-agent invocation",
        "dispatch execution",
        "controller call",
        "route activation",
        "adapter transport activation",
        "production readiness claimed",
        "uat pass claimed",
        "merge approved",
        "owner uat accepted",
    )

    for term in forbidden_terms:
        assert term not in combined, term

    assert "fixture-only" in combined
    assert "non-authoritative" in combined
    assert "runtime hold" in combined


def test_workbench_scope_does_not_mutate_root_package_managers() -> None:
    root_files = {path.name for path in Path.cwd().iterdir() if path.is_file()}
    assert "package.json" not in root_files
    assert "package-lock.json" not in root_files


def test_workbench_app_ignores_local_toolchain_and_build_outputs() -> None:
    gitignore = read_app_file(".gitignore")

    for pattern in (
        "node_modules/",
        "src-tauri/target/",
        "src-tauri/gen/",
        ".toolchain/",
        "dist/",
        ".tmp-render/",
    ):
        assert pattern in gitignore


def test_workbench_fixture_contains_evidence_run_records_and_gates() -> None:
    fixture = load_fixture()
    records = fixture["evidence_runs"]
    by_id = {record["internal_id"]: record for record in records}

    assert tuple(by_id) == REQUIRED_EVIDENCE_RUN_IDS
    assert by_id["EDC-PR-010"]["github_pr_number"] == 36
    assert by_id["EDC-PR-010"]["github_pr_label"] == "#36"
    assert by_id["EDC-PR-010"]["status"] == "not_run"
    assert by_id["EDC-PR-010"]["evidence_state"] == "not_run_by_scope"
    assert by_id["EDC-PR-010"]["not_run_reason"]
    assert by_id["EDC-PR-011"]["github_pr_number"] == 37
    assert by_id["EDC-PR-011"]["github_pr_label"] == "#37"
    assert by_id["EDC-PR-011"]["status"] == "not_run"
    assert by_id["EDC-PR-011"]["evidence_state"] == "not_run_by_scope"
    assert by_id["EDC-PR-011"]["not_run_reason"]

    for record in records:
        assert re.fullmatch(r"EDC-PR-\d{3}", record["internal_id"])
        assert record["command"]
        assert record["status"] in {"passed", "not_run"}
        assert record["evidence_state"] in {"present", "not_run_by_scope"}
        if record["status"] == "passed":
            assert record["evidence_ref"]
        if record["evidence_state"] == "not_run_by_scope":
            assert record["not_run_reason"]


def test_workbench_fixture_contains_pr_uat_closeout_without_acceptance_claims() -> None:
    fixture = load_fixture()
    pr_stack = fixture["pr_stack"]
    by_id = {record["internal_id"]: record for record in pr_stack}
    owner = fixture["owner_uat_decision"]
    recommendation = fixture["closeout_recommendation"]

    assert tuple(by_id) == REQUIRED_PR_STACK_IDS
    assert by_id["EDC-PR-004"]["baseline_role"] == "superseded_prototype"
    assert by_id["EDC-PR-005"]["baseline_role"] == "superseded_prototype"
    assert by_id["EDC-PR-009"]["github_pr_number"] == 35
    assert by_id["EDC-PR-010"]["github_pr_number"] == 36
    assert by_id["EDC-PR-010"]["github_pr_label"] == "#36"
    assert by_id["EDC-PR-010"]["status"] == "draft_pr_open"
    assert all(str(record["internal_id"]) != str(record["github_pr_number"]) for record in pr_stack)
    assert all(record["baseline_role"] != "uat_baseline" for record in pr_stack)

    assert owner["state"] == "awaiting_owner"
    assert owner["decision_ref"] == ""
    assert owner["acceptance_claimed"] is False
    assert owner["uat_pass_claimed"] is False
    assert recommendation["state"] == "prepared_blocked_awaiting_owner"
    assert recommendation["merge_ready"] is False
    assert recommendation["production_ready"] is False
    assert recommendation["live_ready"] is False
    assert recommendation["closeout_accepted"] is False


def test_workbench_fixture_contains_inbox_attention_and_settings_boundaries() -> None:
    fixture = load_fixture()
    attention = {item["id"]: item for item in fixture["inbox_attention"]}
    boundaries = {item["id"]: item for item in fixture["settings_boundaries"]}

    assert tuple(attention) == REQUIRED_ATTENTION_IDS
    assert tuple(boundaries) == REQUIRED_BOUNDARY_IDS
    for item in attention.values():
        assert item["state"] in {"blocked", "hold", "needs_owner", "needs_planning"}
        assert item["read_only"] is True
    for boundary in boundaries.values():
        assert boundary["summary"]
        assert boundary["allowed"]
        assert boundary["blocked"]

    assert boundaries["openclaw_private_material_exclusion"]["blocked"]
    assert boundaries["nexus_local_test_vs_openclaw_live_nats"]["local_test_nats"] == "127.0.0.1:7422"
    assert boundaries["nexus_local_test_vs_openclaw_live_nats"]["openclaw_live_nats"] == "127.0.0.1:4222"
    assert boundaries["nexus_local_test_vs_openclaw_live_nats"]["openclaw_live_mutable"] is False


def test_workbench_closeout_views_have_dedicated_render_targets() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")

    for element_id in (
        "evidence-runs-region",
        "evidence-run-list",
        "pr-uat-closeout-region",
        "pr-stack-list",
        "owner-uat-decision",
        "closeout-recommendation",
        "inbox-attention-region",
        "attention-list",
        "settings-boundaries-region",
        "boundary-list",
    ):
        assert f'id="{element_id}"' in html

    assert "renderEvidenceRunsView" in main_js
    assert "renderPrUatCloseoutView" in main_js
    assert "renderInboxAttentionView" in main_js
    assert "renderSettingsBoundariesView" in main_js
    assert '$("evidence-runs-region").hidden = regionName !== "evidence_runs"' in main_js
    assert '$("pr-uat-closeout-region").hidden = regionName !== "pr_uat_closeout"' in main_js
    assert '$("inbox-attention-region").hidden = regionName !== "inbox_attention"' in main_js
    assert '$("settings-boundaries-region").hidden = regionName !== "settings_boundaries"' in main_js


def test_workbench_fixture_contains_edc_pr_011_command_draft_projection() -> None:
    fixture = load_fixture()
    mappings = {mapping["internal_id"]: mapping for mapping in fixture["pr_mappings"]}

    assert mappings["EDC-PR-011"]["github_pr_number"] == 37
    assert mappings["EDC-PR-011"]["github_pr_label"] == "#37"
    assert mappings["EDC-PR-011"]["status"] == "draft_pr_open"
    assert fixture["project"]["current_internal_sequence"] == "EDC-PR-011"
    assert fixture["selected_work_item_id"] == "EDC-PR-011"

    assert fixture["agent_definitions"]
    assert fixture["runtime_providers"]
    assert fixture["runtime_instances"]
    assert fixture["run_sessions"]
    assert fixture["command_drafts"]
    assert fixture["dispatch_candidate_projection"]
    assert fixture["handoff_preview"]


def test_workbench_fixture_separates_agent_runtime_provider_instance_and_session() -> None:
    fixture = load_fixture()
    agent_ids = {agent["agent_id"] for agent in fixture["agent_definitions"]}
    provider_ids = {provider["provider_id"] for provider in fixture["runtime_providers"]}
    runtime_ids = {runtime["runtime_instance_id"] for runtime in fixture["runtime_instances"]}
    session_ids = {session["run_session_id"] for session in fixture["run_sessions"]}

    assert agent_ids.isdisjoint(provider_ids)
    assert agent_ids.isdisjoint(runtime_ids)
    assert agent_ids.isdisjoint(session_ids)
    assert runtime_ids.isdisjoint(session_ids)

    codex_provider = next(provider for provider in fixture["runtime_providers"] if provider["provider_family"] == "codex")
    assert codex_provider["executable"] is False
    openclaw = next(provider for provider in fixture["runtime_providers"] if provider["provider_family"] == "openclaw")
    assert openclaw["executable"] is False
    assert openclaw["blocked_reason"]


def test_workbench_fixture_contains_safe_command_drafts_only() -> None:
    fixture = load_fixture()
    allowed_command_types = {
        "evaluate_assignment_candidate",
        "prepare_execution_handoff_draft",
        "request_owner_uat_decision_draft",
        "refresh_projection_draft",
        "record_validation_evidence_draft",
    }

    for draft in fixture["command_drafts"]:
        assert draft["command_type"] in allowed_command_types
        assert draft["draft_only"] is True
        assert draft["non_authoritative"] is True
        assert draft["live_dispatch_claimed"] is False
        assert draft["runtime_startup_claimed"] is False
        assert draft["dependency_install_claimed"] is False
        assert draft["broker_mutation_claimed"] is False
        assert draft["merge_claimed"] is False
        assert draft["owner_uat_acceptance_claimed"] is False
        assert draft["production_readiness_claimed"] is False
        assert draft["live_readiness_claimed"] is False
        assert "live_dispatch" in draft["blocked_authorities"]
        assert draft["handoff_preview_ref"]
        assert draft["write_back_location"]
        assert draft["evidence_requirements"]


def test_workbench_ui_exposes_draft_operational_controls_without_runtime_calls() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")

    for element_id in (
        "detail-command-drafts",
        "command-draft-list",
        "selected-command-draft-detail",
        "handoff-preview",
        "dispatch-candidate-projection",
        "agent-definition-list",
        "runtime-provider-list",
        "runtime-instance-list",
        "run-session-list",
    ):
        assert f'id="{element_id}"' in html

    assert "Evaluate assignment" in html
    assert "Prepare handoff draft" in html
    assert "Request owner decision draft" in html
    assert "renderCommandDrafts" in main_js
    assert "selectCommandDraft" in main_js
    assert "selectCommandDraftByType" in main_js
    assert "document.querySelectorAll(\".draft-action[data-command-type]\")" in main_js
    assert "button.addEventListener(\"click\", () => selectCommandDraftByType(button.dataset.commandType))" in main_js
    assert "button.setAttribute(\"aria-pressed\", selected ? \"true\" : \"false\")" in main_js
    assert "renderSelectedCommandDraftDetail" in main_js
    assert "renderSelectedCommandDraftDetail(selectedDraft)" in main_js
    assert "previewValidation.replaceChildren(...createTextList(preview?.validation_commands))" in main_js
    assert "previewBlocked" not in main_js
    assert "selectedDraft.required_approvals" in main_js
    assert "selectedDraft.blocked_authorities" in main_js
    assert "selectedDraft.evidence_requirements" in main_js
    assert "selectedDraft.target_agent_id" in main_js
    assert "selectedDraft.target_runtime_instance_id" in main_js
    assert "invoke(" not in main_js
    assert "fetch(" not in main_js.replace('fetch("./fixtures/edc_workbench_shell_state.json")', "")
    assert "WebSocket" not in main_js
