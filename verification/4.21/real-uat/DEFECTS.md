# Defects And Notes

## Blocking Defects

None found in the implemented local test path.

## Non-blocking Notes

- Windows debug build opens a console window alongside the Tauri WebView; screenshots must target the `Nexus L1 Governance UX Test Surface` WebView window, not the console.
- PowerShell native command quoting can strip JSON quotes when manually passing `--payload-json`; Tauri command invocation passes JSON directly and is unaffected. Direct Python save function was used for evidence verification.
- UI coordinate automation was not treated as authoritative UAT evidence because window z-order and coordinate scaling were noisy. User screenshot and deterministic tests cover the Project Init display path.
