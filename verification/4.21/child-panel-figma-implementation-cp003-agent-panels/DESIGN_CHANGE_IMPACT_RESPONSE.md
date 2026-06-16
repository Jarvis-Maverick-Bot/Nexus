# Design Change Impact Response

## Implemented Change

CP-003 replaces the CP-001 Agent placeholder with Agent Management child panels mapped to accepted Figma frames `07` through `10` and `21`.

## UX Impact

- Agent menu now opens a child-panel menu inside Operation Panel Host.
- Agent Directory, Assign Agent, Runtime Status Blocked, and Configure Agent are reviewable without replacing the shell.
- Assign Agent updates the visible ContextEnvelope as display state only.
- Agent assignment/configuration command draft previews expose expected version, idempotency key, and non-authoritative runtime boundaries.

## Governance Impact

- Kernel and Governance Service remain authority.
- Agent panels do not invoke private agents or activate runtime controls.
- Runtime status remains blocked-display only.
- No Tauri bridge expansion or dependency change was made.

## Deferred

- CP-004 MQ Management panels.
- CP-005 auxiliary surfaces and close/back behavior.
- CP-006 final compact visual QA and consolidated evidence.
