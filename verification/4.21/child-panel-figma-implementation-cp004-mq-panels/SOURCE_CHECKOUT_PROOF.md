# Source Checkout Proof

| Field | Value |
| --- | --- |
| Checkout path | `D:\Projects\Nexus_cp001_child_panel_shell` |
| Branch | `codex/4.21-child-panel-cp004-mq-panels` |
| Base branch | `codex/4.21-real-testproject-e2e-uat` |
| Base HEAD | `ea487273183ba714ebeb336176bbaccfaed7c5a9` |
| CP-003 merge commit | `ea487273183ba714ebeb336176bbaccfaed7c5a9` |
| CP-004 package review commit | `442c8b3` |

## Source File Existence

- `apps/l1gov-desktop-client/src/index.html`
- `apps/l1gov-desktop-client/src/main.js`
- `apps/l1gov-desktop-client/src/styles.css`
- `apps/l1gov-desktop-client/src/fixtures/slice012_desktop_state.json`
- `apps/l1gov-desktop-client/scripts/verify-fixture.mjs`
- `nexus/governance/tests/test_client_desktop_surface_slice012.py`

## Changed Files

- `apps/l1gov-desktop-client/scripts/verify-fixture.mjs`
- `apps/l1gov-desktop-client/src/fixtures/slice012_desktop_state.json`
- `apps/l1gov-desktop-client/src/main.js`
- `nexus/governance/tests/test_client_desktop_surface_slice012.py`
- `verification/4.21/child-panel-figma-implementation-cp004-mq-panels/`

## Source Boundary

Implementation stayed inside the approved desktop-client/test/evidence boundary. No `src-tauri` bridge file was modified.