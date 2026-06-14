from __future__ import annotations

import json
from pathlib import Path

from .fixtures.client_test_surface import DESKTOP_APP_ROOT, DESKTOP_FIXTURE_PATH


REQUIRED_DESKTOP_FILES = (
    "package.json",
    "package-lock.json",
    ".gitignore",
    "README.md",
    "src/index.html",
    "src/main.js",
    "src/styles.css",
    "src/fixtures/slice012_desktop_state.json",
    "src-tauri/Cargo.toml",
    "src-tauri/tauri.conf.json",
    "src-tauri/icons/icon.ico",
    "src-tauri/src/main.rs",
)


def read_app_file(relative_path: str) -> str:
    return (DESKTOP_APP_ROOT / relative_path).read_text(encoding="utf-8")


def load_fixture() -> dict[str, object]:
    return json.loads(DESKTOP_FIXTURE_PATH.read_text(encoding="utf-8"))


def test_slice012_desktop_app_files_exist_under_approved_boundary() -> None:
    for relative_path in REQUIRED_DESKTOP_FILES:
        path = DESKTOP_APP_ROOT / relative_path
        assert path.exists(), relative_path
        assert path.is_file(), relative_path
        assert path.stat().st_size > 0, relative_path

    assert DESKTOP_APP_ROOT.as_posix().endswith("apps/l1gov-desktop-client")


def test_slice012_tauri_metadata_is_windows_first_and_non_authoritative() -> None:
    package_json = json.loads(read_app_file("package.json"))
    tauri_config = json.loads(read_app_file("src-tauri/tauri.conf.json"))

    assert package_json["name"] == "@nexus/l1gov-desktop-client"
    assert package_json["private"] is True
    assert package_json["scripts"]["dev"] == "tauri dev"
    assert package_json["scripts"]["build"] == "tauri build"
    assert package_json["devDependencies"]["@tauri-apps/cli"].startswith("2.")

    assert tauri_config["productName"] == "Nexus L1 Governance UX Test Surface"
    assert tauri_config["app"]["windows"][0]["title"] == "Nexus L1 Governance UX Test Surface"
    assert tauri_config["bundle"]["active"] is False
    assert tauri_config["app"]["security"]["csp"] == "default-src 'self'"
    assert tauri_config["app"]["withGlobalTauri"] is True


def test_slice012_desktop_fixture_declares_scope_and_future_integration_boundary() -> None:
    fixture = load_fixture()

    assert fixture["slice_id"] == "L1GOV-SLICE-012"
    assert fixture["surface_form"] == "tauri_desktop_app_test_surface"
    assert fixture["runtime_choice"] == "tauri"
    assert fixture["windows_first"] is True
    assert fixture["macos_compatibility_considered"] is True
    assert fixture["non_authoritative"] is True
    assert fixture["canonical_authority"] == "GovernanceKernel"
    assert fixture["service_boundary"] == "GovernanceService"
    assert fixture["live_execution_invoked"] is False

    future_boundary = fixture["future_integration_boundary"]
    assert future_boundary["daemon_controller_bridge"] == "disabled_future_boundary"
    assert future_boundary["can_execute_live_calls"] is False
    assert future_boundary["uses_deterministic_fixtures_only"] is True


def test_slice012_desktop_surface_contains_required_operable_regions() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")
    top_actions = html.split('<section class="workspace-strip"', 1)[0]

    for element_id in (
        "workspace-picker",
        "workspace-overlay",
        "create-testproject",
        "cleanup-testproject",
        "project-init",
        "init-required-list",
        "init-workspace-root",
        "init-field-project-charter",
        "init-field-execution-plan",
        "save-init-draft",
        "draft-init-command",
        "mission-control",
        "module-navigation",
        "inspector",
        "status-bar",
        "service-chip",
        "real-uat-state",
        "notes-evidence",
        "command-draft-preview",
        "service-rejection",
        "no-go-block",
        "stale-refresh",
    ):
        assert f'id="{element_id}"' in html

    assert html.index('id="workspace-overlay"') < html.index('id="create-testproject"')
    assert html.index('id="workspace-overlay"') < html.index('id="cleanup-testproject"')
    assert 'id="create-testproject"' not in top_actions
    assert 'id="cleanup-testproject"' not in top_actions

    for hook in (
        "openWorkspacePicker",
        "renderProjectInit",
        "saveProjectInitDraft",
        "showInitCommandDraft",
        "selectModule",
        "showCommandDraftPreview",
        "showServiceRejection",
        "showNoGoBlock",
        "cycleStaleRefresh",
        "renderFutureIntegrationBoundary",
        "createRealTestProject",
        "loadRealProjectionState",
    ):
        assert hook in main_js


def test_slice012_renderer_prefers_real_projection_state_and_keeps_fixture_parser() -> None:
    fixture = load_fixture()
    main_js = read_app_file("src/main.js")

    assert "const state = {" not in main_js
    assert 'invoke("create_test_project"' in main_js
    assert 'invoke("read_test_project_projection"' in main_js
    assert "pendingRealUatState" in main_js
    assert "fetch(\"./fixtures/slice012_desktop_state.json\")" in main_js
    assert "loadFixtureState" in main_js
    assert "display_state" in fixture
    assert fixture["display_state"]["workspace_name"] == "4.21 Layer 1 Governance"


def test_slice012_footer_declares_real_local_test_status() -> None:
    html = read_app_file("src/index.html")

    assert 'id="service-state">real local test pending' in html
    assert "service fixture only" not in html
    assert "Service: connected" not in html
    assert "connected</strong>" not in html


def test_slice012_desktop_launch_and_macos_notes_are_present() -> None:
    readme = read_app_file("README.md")

    assert "Windows-first launch" in readme
    assert "npm run dev" in readme
    assert "macOS compatibility" in readme
    assert "not verified on macOS in this Windows run" in readme
    assert "PR #20 remains draft/reference only" in readme


def test_slice012_desktop_files_do_not_contain_live_execution_paths() -> None:
    scanned_files = [
        DESKTOP_APP_ROOT / "src/index.html",
        DESKTOP_APP_ROOT / "src/main.js",
        DESKTOP_APP_ROOT / "src/styles.css",
        DESKTOP_FIXTURE_PATH,
        DESKTOP_APP_ROOT / "src-tauri/src/main.rs",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in scanned_files)
    forbidden_terms = (
        "@tauri-apps/api",
        "http://",
        "https://",
        "websocket",
        "localstorage",
        "sessionstorage",
        "indexeddb",
        "private-agent invocation",
        "dispatch execution",
        "controller call",
        "route activation",
        "adapter transport activation",
        "owner-path call",
        "lower-layer submission",
        "production readiness",
        "continuity activation",
        "final pass claim",
    )

    for term in forbidden_terms:
        assert term not in combined, term

    assert 'invoke("create_test_project"' in combined
    assert 'invoke("read_test_project_projection"' in combined
    assert "kernel and governance service remain authority" in combined
    assert "non-authoritative" in combined


def test_slice012_desktop_scope_does_not_mutate_root_package_managers() -> None:
    root_files = {path.name for path in Path.cwd().iterdir() if path.is_file()}
    assert "package.json" not in root_files
    assert "package-lock.json" not in root_files


def test_slice012_desktop_app_ignores_local_toolchain_and_build_outputs() -> None:
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
