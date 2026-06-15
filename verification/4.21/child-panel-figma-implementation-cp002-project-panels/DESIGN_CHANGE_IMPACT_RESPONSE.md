# Design Change Impact Response

## Implemented Change

CP-002 replaces the CP-001 Project placeholder with Project Management child panels mapped to accepted Figma frames `03` through `06`.

After Nova review, CP-002 also adds a small wrapping patch for right-panel metadata in the Standardization Preview.

## UX Impact

- Project menu now opens a child-panel menu inside Operation Panel Host.
- Create Project, Init Project Dirty State, and Standardization Preview are reviewable without replacing the shell.
- Command draft previews expose expected version, idempotency key, source refs, and non-authoritative status.
- Long Project panel metadata wraps inside Operation Panel Host instead of clipping at the right edge.

## Governance Impact

- Kernel and Governance Service remain authority.
- Project panels do not write canonical records.
- Baseline approval and canonical mutation are blocked at the UI boundary.
- No Tauri bridge expansion or dependency change was made.

## Deferred

- CP-003 Agent Management panels.
- CP-004 MQ Management panels.
- CP-005 auxiliary surfaces and close/back behavior.
- CP-006 final compact visual QA and consolidated evidence.
