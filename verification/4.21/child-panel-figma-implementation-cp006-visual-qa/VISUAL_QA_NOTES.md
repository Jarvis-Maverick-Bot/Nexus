# CP-006 Visual QA Notes

## Scope

CP-006 performed visual QA for CP-001 through CP-005. No new UX features were added.

## Screenshot Coverage

- Total screenshots: 31
- Desktop screenshots: 23
- Compact screenshots: 8
- Viewports: `1440x950`, `900x700`, and `900x1400`.

## Layout Diagnostics

No horizontal overflow or diagnostic offender boxes were detected across the screenshot inventory.

Representative manual spot checks covered compact Main Cockpit, compact Workspace Picker Overlay, and dense MQ Dispatch No-Go Diagnostics.

## Compact Hardening Decision

No CSS or JS hardening patch was applied because captured compact surfaces fit/read correctly and diagnostics reported no horizontal overflow/offender boxes.

## Capture Method

Screenshots were captured from a temporary static HTTP server rooted at `apps/l1gov-desktop-client/src` using the bundled Playwright package and installed Chrome at `C:/Program Files/Google/Chrome/Application/chrome.exe`.

The Playwright CLI wrapper was not used because `npx` is not available on PATH in this environment.
