from __future__ import annotations

from pathlib import Path


APP_ROOT = Path("apps/l1gov-desktop-client")


def read_app_file(path: str) -> str:
    return (APP_ROOT / path).read_text(encoding="utf-8")


def test_desktop_has_real_testproject_creation_surface() -> None:
    html = read_app_file("src/index.html")
    top_actions = html.split('<section class="workspace-strip"', 1)[0]

    assert 'id="workspace-overlay"' in html
    assert 'id="create-testproject"' in html
    assert 'id="cleanup-testproject"' in html
    assert "Create TestProject" in html
    assert html.index('id="workspace-overlay"') < html.index('id="create-testproject"')
    assert html.index('id="workspace-overlay"') < html.index('id="cleanup-testproject"')
    assert 'id="create-testproject"' not in top_actions
    assert 'id="cleanup-testproject"' not in top_actions
    assert 'id="real-uat-state"' in html
    assert "fixture only" not in html.lower().split('id="service-state">', 1)[1].split("</strong>", 1)[0]


def test_desktop_has_project_init_surface_for_required_information() -> None:
    html = read_app_file("src/index.html")
    main_js = read_app_file("src/main.js")

    assert 'data-module="project_init">Project Init' in html
    assert 'id="project-init"' in html
    assert 'id="init-required-list"' in html
    assert 'id="init-workspace-root"' in html
    assert 'id="init-field-project-charter"' in html
    assert 'id="init-field-execution-plan"' in html
    assert 'id="save-init-draft"' in html
    assert 'id="draft-init-command"' in html
    assert "renderProjectInit" in main_js
    assert "saveProjectInitDraft" in main_js
    assert "showInitCommandDraft" in main_js
    assert "initRequirements" in main_js


def test_desktop_uses_tauri_commands_for_real_uat_state() -> None:
    main_js = read_app_file("src/main.js")
    main_rs = read_app_file("src-tauri/src/main.rs")
    tauri_config = read_app_file("src-tauri/tauri.conf.json")

    assert "createRealTestProject" in main_js
    assert "loadRealProjectionState" in main_js
    assert 'invoke("create_test_project"' in main_js
    assert 'invoke("read_test_project_projection"' in main_js
    assert 'invoke("cleanup_test_project"' in main_js
    assert 'invoke("save_project_init_draft"' in main_js
    assert "fixture-backed only" not in main_js
    assert "create_test_project" in main_rs
    assert "read_test_project_projection" in main_rs
    assert "cleanup_test_project" in main_rs
    assert "save_project_init_draft" in main_rs
    assert "generate_handler!" in main_rs
    assert '"withGlobalTauri": true' in tauri_config
