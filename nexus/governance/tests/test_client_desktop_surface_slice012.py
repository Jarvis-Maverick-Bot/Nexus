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


def test_cp001_shell_foundation_exposes_context_envelope_and_operation_host() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")

    for element_id in (
        "context-envelope",
        "context-project",
        "context-session",
        "context-agent",
        "context-source",
        "context-freshness",
        "context-live-invocation",
        "context-authority",
        "operation-panel-host",
        "operation-panel-title",
        "operation-panel-body",
        "operation-panel-status",
    ):
        assert f'id="{element_id}"' in html

    for hook in (
        "renderContextEnvelope",
        "PANEL_REGISTRY",
        "selectOperationPanel",
        "renderOperationPanel",
    ):
        assert hook in main_js


def test_cp001_visible_labels_migrate_to_main_cockpit_while_internal_keys_stay_compatible() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")
    fixture = load_fixture()

    assert ">Mission Control<" not in html
    assert 'aria-label="Mission Control"' not in html
    assert "Main Cockpit" in html
    assert "Active Session Cockpit" in main_js
    assert "mission_control" in main_js
    assert "mission_control" in fixture["display_state"]["modules"]
    assert fixture["display_state"]["modules"]["mission_control"]["title"] == "Main Cockpit"


def test_cp001_panel_registry_is_shell_only_and_fails_closed_for_unknown_routes() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")

    for route in (
        'data-panel-route="project_shell"',
        'data-panel-route="agent_shell"',
        'data-panel-route="mq_shell"',
        'data-panel-route="evidence_drawer"',
    ):
        assert route in html

    for panel_id in (
        "main_cockpit",
        "project_shell",
        "agent_shell",
        "mq_shell",
        "workspace_picker",
        "evidence_drawer",
        "status_toast",
    ):
        assert panel_id in main_js

    assert "ERR_INVALID_PANEL_ROUTE" in main_js
    assert "failClosedPanelRoute" in main_js
    assert "No command is executed from shell navigation" in main_js


def test_cp001_compact_layout_keeps_operation_host_in_responsive_flow() -> None:
    styles = read_app_file("src/styles.css")

    assert "@media (max-width: 1120px)" in styles
    assert ".operation-panel-host" in styles
    assert "order: 2;" in styles
    assert "order: 3;" in styles


def test_cp002_project_management_panels_are_registered_from_fixture_state() -> None:
    main_js = read_app_file("src/main.js")
    fixture = load_fixture()

    project_management = fixture["display_state"]["project_management"]
    assert project_management["creates_authority"] is False
    assert project_management["command_draft_preview_only"] is True

    for panel_id in (
        "project_shell",
        "project_create",
        "project_init_dirty",
        "project_standardization_preview",
    ):
        assert panel_id in main_js

    for hook in (
        "renderProjectCreatePanel",
        "renderProjectInitDirtyPanel",
        "renderProjectStandardizationPanel",
        "showProjectCreateDraftPreview",
        "showProjectInitDraftPreview",
        "showProjectStandardizationDraftPreview",
    ):
        assert hook in main_js


def test_cp002_project_menu_routes_to_preview_only_child_panels() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")

    assert 'id="top-menu-project"' in html
    assert 'data-panel-route="project_shell"' in html

    for visible_label in (
        "Create Project",
        "Init Project Dirty State",
        "Standardization Preview",
    ):
        assert visible_label in main_js

    for expected_contract in (
        "command_type=SubmitCommandDraft",
        "expected_version",
        "idempotency_key",
        "source_refs",
        "affects_state=false",
        "creates_authority=false",
    ):
        assert expected_contract in main_js


def test_cp002_project_panels_do_not_add_direct_authority_or_baseline_controls() -> None:
    main_js = read_app_file("src/main.js").lower()
    html = read_app_file("src/index.html").lower()
    combined = "\n".join((main_js, html))

    forbidden_affordances = (
        "approve baseline",
        "make canonical",
        "canonical write",
        "create baseline entry",
        "submit canonical",
        "mark approved",
        "final pass",
    )

    for affordance in forbidden_affordances:
        assert affordance not in combined, affordance

    assert "direct baseline approval" in main_js
    assert "direct canonical mutation" in main_js
    assert "err_no_go_boundary" in main_js


def test_cp002_operation_panel_metadata_wraps_inside_right_panel() -> None:
    styles = read_app_file("src/styles.css")

    assert ".operation-panel-body code" in styles
    assert ".panel-detail-list li" in styles
    assert "overflow-wrap: anywhere" in styles
    assert "max-width: 100%" in styles


def test_cp003_agent_management_panels_are_registered_from_fixture_state() -> None:
    main_js = read_app_file("src/main.js")
    fixture = load_fixture()

    agent_management = fixture["display_state"]["agent_management"]
    assert agent_management["private_agent_invocation"] is False
    assert agent_management["runtime_control_activation"] is False
    assert agent_management["command_draft_preview_only"] is True

    for panel_id in (
        "agent_shell",
        "agent_directory",
        "agent_assignment",
        "agent_runtime_status_blocked",
        "agent_configure",
    ):
        assert panel_id in main_js

    for hook in (
        "renderAgentDirectoryPanel",
        "renderAgentAssignmentPanel",
        "renderAgentRuntimeStatusPanel",
        "renderAgentConfigurePanel",
        "showAgentAssignmentDraftPreview",
        "showAgentConfigureDraftPreview",
        "showAgentRuntimeBlocked",
    ):
        assert hook in main_js


def test_cp003_agent_menu_routes_to_display_and_preview_only_child_panels() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")

    assert 'id="top-menu-agent"' in html
    assert 'data-panel-route="agent_shell"' in html

    for visible_label in (
        "Agent Directory",
        "Assign Agent",
        "Runtime Status Blocked",
        "Configure Agent",
    ):
        assert visible_label in main_js

    for expected_contract in (
        "command_type=SubmitCommandDraft",
        "subtype=AgentAssignmentPanel",
        "subtype=AgentConfigurePanel",
        "context_update",
        "display-only",
        "private_agent_invocation=false",
        "runtime_control_activation=false",
        "ERR_NO_GO_BOUNDARY",
    ):
        assert expected_contract in main_js


def test_cp003_agent_panels_do_not_add_runtime_or_private_agent_controls() -> None:
    main_js = read_app_file("src/main.js").lower()
    html = read_app_file("src/index.html").lower()
    combined = "\n".join((main_js, html))

    forbidden_affordances = (
        "invoke private agent",
        "start runtime",
        "stop runtime",
        "activate runtime",
        "run agent",
        "execute agent",
        "dispatch agent",
        "call controller",
        "activate route",
    )

    for affordance in forbidden_affordances:
        assert affordance not in combined, affordance

    assert "private_agent_invocation" in main_js
    assert "runtime_control_activation" in main_js
    assert "err_no_go_boundary" in main_js


def test_cp004_mq_management_fixture_is_display_and_preview_only() -> None:
    fixture = load_fixture()

    mq_management = fixture["display_state"]["mq_management"]
    assert mq_management["queue_execution"] is False
    assert mq_management["dispatch_execution"] is False
    assert mq_management["controller_call"] is False
    assert mq_management["route_activation"] is False
    assert mq_management["adapter_transport_activation"] is False
    assert mq_management["replay_execution"] is False
    assert mq_management["command_draft_preview_only"] is True

    assert mq_management["queue_overview"]["queues"][0]["label"] == "Governance inbox"
    assert mq_management["message_detail"]["correlation_id"] == "corr-cp004-message-preview"
    assert mq_management["dispatch_no_go"]["error_code"] == "ERR_NO_GO_BOUNDARY"
    assert mq_management["replay_evidence"]["evidence_only"] is True


def test_cp004_mq_management_panels_are_registered_from_fixture_state() -> None:
    main_js = read_app_file("src/main.js")

    for panel_id in (
        "mq_shell",
        "mq_queue_overview",
        "mq_message_detail",
        "mq_no_go_diagnostics",
        "mq_replay_evidence",
    ):
        assert panel_id in main_js

    for hook in (
        "renderMqQueueOverviewPanel",
        "renderMqMessageDetailPanel",
        "renderMqNoGoDiagnosticsPanel",
        "renderMqReplayEvidencePanel",
        "showMqMessageDraftPreview",
        "showMqDispatchNoGo",
        "showMqReplayEvidencePreview",
    ):
        assert hook in main_js


def test_cp004_mq_menu_routes_to_display_and_preview_only_child_panels() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")

    assert 'id="top-menu-mq"' in html
    assert 'data-panel-route="mq_shell"' in html

    for visible_label in (
        "Queue Overview",
        "Message Detail",
        "Dispatch No-Go Diagnostics",
        "Replay Evidence",
    ):
        assert visible_label in main_js

    for expected_contract in (
        "command_type=SubmitCommandDraft",
        "subtype=MqMessageDetailPanel",
        "correlation_id",
        "idempotency_key",
        "expected_version",
        "queue_execution=false",
        "dispatch_execution=false",
        "controller_call=false",
        "replay_execution=false",
        "ERR_NO_GO_BOUNDARY",
        "evidence-only",
    ):
        assert expected_contract in main_js


def test_cp004_mq_panels_do_not_add_executable_mq_or_dispatch_controls() -> None:
    main_js = read_app_file("src/main.js").lower()
    html = read_app_file("src/index.html").lower()
    combined = "\n".join((main_js, html))

    forbidden_affordances = (
        "execute queue",
        "message execution",
        "send message",
        "publish message",
        "replay message",
        "run replay",
        "execute replay",
        "dispatch now",
        "call controller",
        "activate route",
        "activate adapter",
        "activate transport",
    )

    for affordance in forbidden_affordances:
        assert affordance not in combined, affordance

    assert "queue_execution" in main_js
    assert "dispatch_execution" in main_js
    assert "replay_execution" in main_js
    assert "err_no_go_boundary" in main_js
