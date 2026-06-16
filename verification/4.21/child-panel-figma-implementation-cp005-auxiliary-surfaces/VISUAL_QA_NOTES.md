# Visual QA Notes

## Capture Method

Screenshots were captured through a temporary static HTTP server rooted at:

```text
D:/Projects/Nexus_cp001_child_panel_shell/apps/l1gov-desktop-client/src
```

The capture used bundled Playwright with the installed Chrome executable:

```text
C:/Program Files/Google/Chrome/Application/chrome.exe
```

Viewport:

```text
1440x950
```

## Spot Checks

- Workspace Picker Overlay opens from the toolbar, uses the operation host route `workspace_picker`, and shows `workspace_selection_creates_authority=false`.
- Command Preview shows `command_preview_submits_command=false`, `affects_state=false`, and `creates_authority=false`.
- Evidence Drawer shows `evidence-only=true` and `evidence_is_authority=false`.
- No-Go Dialog shows `ERR_NO_GO_BOUNDARY` and `no_go_bypass_allowed=false`.
- Stale Projection Refresh cycles display freshness and shows `stale_refresh_canonical_mutation=false`.
- Status Toast is present in the status bar and reports display-only lifecycle messages.
- Host Back and Close return to Main Cockpit and report `host_back_executes_command=false` or `host_close_executes_command=false`.

## Layout Notes

The operation host controls fit in the existing right panel. Status bar messages wrap without overlapping the main content. The checked desktop screenshots do not show incoherent element overlap.
