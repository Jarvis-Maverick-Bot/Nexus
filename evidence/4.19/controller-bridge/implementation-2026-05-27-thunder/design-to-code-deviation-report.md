# Design-to-Code Deviation Report

## Deviations

- The operator CLI is implemented as `python -m nexus.mq.controller_bridge_cli ...`. A global `nexus dispatch` or `nexus runtime` executable was not added because global CLI packaging was explicitly outside the approved write set.
- Runtime CLI commands use deterministic JSON inputs and SQLite state for this code-review gate. They do not perform live runtime registration, broker traffic, or Phase 3 rerun behavior.
- `dispatch request-eligibility` uses a deterministic query-only lifecycle provider fed by lifecycle-decision JSON for the review gate. This preserves the dispatch/runtime ownership boundary while avoiding live runtime startup.

## Nova Review Corrections

- Added the missing `dispatch request-eligibility` CLI command and focused persistence/output test.
- Added Runtime Lifecycle lease transition reconciliation for consume, release, revoke, and expiry.
- Added focused tests for post-consume capacity blocking, post-release eligibility, and expired reservation cleanup.

## No Design Deviations Requiring Approval

- Dispatch does not mint registration, readiness, heartbeat, lifecycle decisions, leases, broker config, or final PASS.
- Runtime Lifecycle owns registration/readiness/heartbeat/eligibility/capacity/lease state and does not publish assignments.
- Layer 3 MQ transport files were not modified.
- Evidence builder cannot convert incomplete bridge evidence or diagnostic-only evidence into PASS/live readiness.

## Blockers

None for Nova code review.
