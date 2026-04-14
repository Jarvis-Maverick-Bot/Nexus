# V1.8 PMO Action Inventory

**Purpose:** Enumerate all PMO Smart Agent interaction scenarios for V1.8 delivery.

---

## Context

V1.8 delivers the first AI-native game (Grid Escape) through the Claw Studio + Viper operating model. PMO Smart Agent operations must complete via CLI without UI dependency (F3.3.1).

---

## PMO Interaction Scenarios

| # | Scenario | Current UI Dependency | CLI Replacement |
|---|----------|---------------------|-----------------|
| 1 | Create delivery work item | None (new) | `pmo create-work-item <name>` |
| 2 | Register game artifact | None (new) | `pmo submit-artifact <item_id> <path>` |
| 3 | Advance delivery stage | None (new) | `pmo request-transition <item_id> <stage>` |
| 4 | Record validation result | None (new) | `pmo record-validation <item_id> <result>` |
| 5 | Signal blocker/escalation | None (new) | `pmo signal-blocker <item_id> <desc>` |
| 6 | Package delivery candidate | None (new) | `pmo package-delivery <item_id>` |
| 7 | Check delivery/item status | None (new) | `pmo status [item_id]` |

---

## Valid Stages

`BACKLOG` → `IN_PROGRESS` → `IN_REVIEW` → `APPROVED` → `DELIVERED`

---

## State Store

All PMO state is persisted to `governance/pmo/data/pmo_state.json`.

---

## CLI Invariant

All 7 commands MUST:
- Return valid JSON to stdout
- Return `{"ok": false, "error": "..."}` on any error
- Exit with code 0 on success, non-zero on failure
- Produce identical output for identical inputs (idempotent where applicable)
