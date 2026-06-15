# Visual QA Notes

## Method

Screenshots were captured with local Chrome headless against a temporary Python HTTP server serving `apps/l1gov-desktop-client`.

No Playwright/npm dependency was installed. No Tauri bridge expansion was used for screenshots.

## Captured Screenshots

| File | Dimensions | Result |
| --- | --- | --- |
| `cp001-02-main-cockpit-desktop.png` | 1440x900 | ContextEnvelope and Operation Panel Host visible; no visible Mission Control label. |
| `cp001-02-main-cockpit-compact.png` | 900x700 | Compact top shell crop verifies top menu and Main Cockpit visible. |
| `cp001-02-main-cockpit-compact-full.png` | 900x1400 | Compact-width flow verifies Operation Panel Host and ContextEnvelope remain in responsive flow. |

## Findings

- ContextEnvelope text is visible and not overlapping in desktop and compact-width screenshots.
- Operation Panel Host is visible on desktop.
- Compact responsive flow places Operation Panel Host before Main Cockpit content, then ContextEnvelope and Main Cockpit content.
- Status bar remains non-authoritative.
- No command-like execution affordance was added to tree/sidebar rows or shell route buttons.

