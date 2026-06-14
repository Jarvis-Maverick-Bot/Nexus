from __future__ import annotations

import json
from pathlib import Path

from .fixtures.client_test_surface import DESKTOP_APP_ROOT, DESKTOP_FIXTURE_PATH


REQUIRED_DESKTOP_FILES = (
    "package.json",
    "package-lock.json",
    "README.md",
    "src/index.html",
    "src/main.js",
    "src/styles.css",
    "src/fixtures/slice012_desktop_state.json",
    "src-tauri/Cargo.toml",
    "src-tauri/tauri.conf.json",
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

    for element_id in (
        "workspace-picker",
        "mission-control",
        "module-navigation",
        "inspector",
        "status-bar",
        "notes-evidence",
        "command-draft-preview",
        "service-rejection",
        "no-go-block",
        "stale-refresh",
    ):
        assert f'id="{element_id}"' in html

    for hook in (
        "openWorkspacePicker",
        "selectModule",
        "showCommandDraftPreview",
        "showServiceRejection",
        "showNoGoBlock",
        "cycleStaleRefresh",
        "renderFutureIntegrationBoundary",
    ):
        assert hook in main_js


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
        "invoke(",
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

    assert "kernel and governance service remain authority" in combined
    assert "desktop app is non-authoritative" in combined


def test_slice012_desktop_scope_does_not_mutate_root_package_managers() -> None:
    root_files = {path.name for path in Path.cwd().iterdir() if path.is_file()}
    assert "package.json" not in root_files
    assert "package-lock.json" not in root_files
