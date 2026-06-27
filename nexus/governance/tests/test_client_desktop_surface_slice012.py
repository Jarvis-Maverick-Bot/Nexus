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
    assert by_id["EDC-PR-007"]["github_pr_number"] is None
    assert by_id["EDC-PR-007"]["branch"] == "codex/edc-pr-007-desktop-workbench-shell"
    assert by_id["EDC-PR-007"]["base_commit"] == "d6a8b55"
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
        assert view["readiness_state"] in {"planned", "blocked_until_later_slice", "shell_only"}
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
    assert "fetch(\"./fixtures/edc_workbench_shell_state.json\")" in main_js
    assert "activeViewId" in main_js
    assert "renderActiveView" in main_js
    assert "selectView" in main_js
    assert "scrollIntoView" not in main_js
    assert "location.hash" not in main_js
    assert "href=\"#" not in html

    for view_id in REQUIRED_VIEW_IDS:
        assert f'data-view-id="{view_id}"' in html


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
