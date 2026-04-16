# V1.9 Execution Plan — v1.4 (Formal Close)

**Release:** V1.9
**Version:** 1.4
**Status:** READY FOR FORMAL CLOSE REVIEW
**Date:** 2026-04-16
**Branch:** `release/v1.9-dev`

---

## Release Overview

V1.9 delivers three bounded capability layers:

| Layer | Functions | Sprint |
|-------|-----------|--------|
| FB8 Queue Foundation | F1.1.1–F1.2.5, F2.1.1–F2.2.5 | Sprint 1 |
| FB3/F4 Routing + Escalation | F3.1.1–F3.3.3, F5.1.1–F5.3.4, F6.1.1–F6.3.3 | Sprint 2 |
| CLI Completeness + Migration | T9.1–T9.2, T10.1–T10.2, T11 | Sprint 3 |

---

## Sprint 1 — FB8 Queue Foundation

**Sprint:** M1 equivalent
**Functions:** F1.1.1–F1.2.5, F2.1.1–F2.2.5
**Goal:** Message queue infrastructure, NATS transport, bounded 4-state lifecycle
**Status:** ✅ COMPLETE — Nova approved

### Functions

| ID | Function | Status |
|----|----------|--------|
| F1.1.1 | Queue creation (NEW state) | ✅ |
| F1.1.2 | Queue listing and inspection | ✅ |
| F1.2.1 | NATS publish | ✅ |
| F1.2.2 | NATS subscribe + local cache | ✅ |
| F1.2.3 | State transitions (NEW→ROUTED→CLAIMED→ANSWERED) | ✅ |
| F1.2.4 | Response linking (request_id propagation) | ✅ |
| F1.2.5 | Append-only evidence log | ✅ |
| F2.1.1 | Planner seat — message intake | ✅ |
| F2.1.2 | Planner seat — task planning | ✅ |
| F2.1.3 | Planner seat — response routing | ✅ |
| F2.1.4 | Planner seat — NATS integration | ✅ |
| F2.2.1 | TDD seat — task intake | ✅ |
| F2.2.2 | TDD seat — test-first development | ✅ |
| F2.2.3 | TDD seat — code implementation | ✅ |
| F2.2.4 | TDD seat — NATS integration | ✅ |
| F2.2.5 | TDD seat — bounded evidence | ✅ |

### Definition of Done

- [x] NATS publish operational (real transport; local-state/cache layer handles unavailable condition)
- [x] Local state/cache + evidence/inspection surface (not alternate authoritative transport mode)
- [x] Queue state machine implements full state model: NEW, ROUTED, CLAIMED, WAITING, ANSWERED, CLOSED, CANCELED, EXPIRED (evidence concentrated on main-path: NEW→ROUTED→CLAIMED→ANSWERED→CLOSED)
- [x] Message linkage: linked response messages via `request_id` propagation (per PRD V0.3 linkage model)
- [x] Append-only evidence log per message lifecycle
- [x] Unit tests: all passing
- [x] Evidence trace: scenario1_agent_to_agent_trace.md captured from real queue event log

### Evidence

- `evidence/sprint1/scenario1_agent_to_agent_trace.md` — NATS queue loop trace
- `evidence/sprint1/s1_message_queue_trace.md` — NATS transport + cache trace
- `evidence/sprint1/s1_task_lifecycle_trace.md` — 8-state task lifecycle trace
- `evidence/sprint1/s1_planner_tdd_trace.md` — Planner→TDD end-to-end trace
- `evidence/sprint1/scenario4_planner_tdd_trace.md` — Planner+TDD collaboration trace
- `evidence/sprint1/scenario5_inspectable_state_trace.md` — CLI inspection outputs

### Sign-Off

- **Nova:** APPROVED (2026-04-15 ~21:24 GMT+8)
- **Sign-off commits:** `106dcdf` (messages.json schema), `18a2fce` (task/message lifecycle)

---

## Sprint 2 — FB3/F4 Routing + Escalation Loop

**Sprint:** M2 equivalent
**Functions:** F3.1.1–F3.3.3, F5.1.1–F5.3.4, F6.1.1–F6.3.3
**Goal:** Intake→Determine→Route→Resolve→Relay, escalation triggers, return-path decisions
**Status:** ✅ COMPLETE — Nova approved with carry-forward note

### Functions

| ID | Function | Status |
|----|----------|--------|
| F3.1.1 | Intake message capture | ✅ |
| F3.2.1 | Routing rules (backlog→active/pending→escalation) | ✅ |
| F3.2.2 | Route delivery | ✅ |
| F3.3.1 | Escalation trigger | ✅ |
| F3.3.2 | Escalation → NATS | ✅ |
| F3.3.3 | Return-path decisions (APPROVE/REJECT/CONTINUE/STOP) | ✅ |
| F5.1.1–F5.3.4 | PMO Event Routing core | ✅ |
| F6.1.1–F6.3.3 | Bounded command/control loop | ✅ |

### Definition of Done

- [x] Intake captures work item or task event
- [x] Routing rules classify: backlog / active / pending escalation
- [x] Escalation trigger publishes to `gov.escalations` subject
- [x] Return path supports: APPROVE, REJECT, CONTINUE, STOP
- [x] Unit tests: all passing
- [x] Evidence trace: scenario2 + scenario3 captured

### Evidence

- `evidence/sprint2/scenario2_pending_routing_trace.md` — Routing rules trace
- `evidence/sprint2/scenario3_escalation_return_trace.md` — Escalation + return trace

### Sign-Off

- **Nova:** APPROVED (2026-04-16 evening) with carry-forward note:
  - *"describe Sprint 2 honestly as 'bounded V1.9 routing/control proof, not a mature control-plane/runtime'"*

---

## Sprint 3 — CLI Completeness + Structural Migration

**Sprint:** M3 equivalent
**Tasks:** T9, T10, T11
**Goal:** Unified inspect across all 4 domains, evidence package, module cleanup
**Status:** ✅ COMPLETE — Nova approved

### Tasks

| ID | Task | Description | Status |
|----|------|-------------|--------|
| T9.1 | signal-blocker → FB4 | CLI signal-blocker routes to escalation triggers | ✅ |
| T9.2 | inspect unification | Unified inspect across queue/task/WI/escalation domains | ✅ |
| T10.1 | CLI evidence capture | Scenario 5: live `inspect` outputs | ✅ |
| T10.2 | Evidence package | Sprint 1 + Sprint 2 scenario traces | ✅ Approved w/ notes |
| T11 | Structural cleanup | workitem/ module, V1.8 artifacts removed | ✅ |

### Evidence

- `evidence/sprint1/scenario5_inspectable_state_trace.md` — Live CLI outputs
- `evidence/sprint1/` — Full Sprint 1 trace package (10 files)
- `evidence/sprint2/` — Full Sprint 2 trace package (2 files)
- `evidence/sprint3/` — Sprint 3 structural evidence (code + Nova review record)

### Commit Chain

```
be43586 — T11 structural cleanup
84eaf7f — T10.2 evidence package
77182b3 — T9.2 inspect semantic fix
58f727e — T9.1 signal-blocker → FB4 escalation
```

### Sign-Off

- **Nova:** APPROVED T11; APPROVED T10 with notes (2026-04-16 16:12 GMT+8)

### Carry-Forward Notes (from Nova)

1. **Remove legacy `signal_blocker()`** from `governance/workitem/store.py` — CLI now routes to FB4 escalation; the local function is dead code
2. **Normalize evidence structure** — `sprint1/` + `sprint2/` is functional but not elegantly normalized; later pass should consolidate into one final 5-scenario package surface
3. **Scenario 4 wording** — NATS-layer subscribe/claim not as directly evidenced as prose suggests; operational chain (planner+TDD+handoff) is well-evidenced
4. **Scenario 2** — weakest of 5; mixes routing proof + control loop + queue snippets

---

## Known Limitations

These are not hidden defects — they are honest maturity notes:

| Limitation | Description |
|------------|-------------|
| Not a mature routing runtime | FB3 routing rules are bounded proof, not production runtime |
| Not a mature control plane | FB4 command/control is bounded proof, not live authority system |
| Not a mature agent platform | FB8 NATS+cache is bounded foundation, not full agent runtime |
| Evidence package structural | Functional but not elegantly normalized across sprints |
| signal_blocker() residue | Legacy function in workitem/store.py needs removal |

---

## V1.9 — What Was NOT In Scope

The following were explicitly deferred to future releases:

| Item | Reason |
|------|--------|
| Production NATS cluster setup | Deferred to V1.10 or later |
| Live agent runtime (Viper/Claw integration) | Deferred — bounded proof only in V1.9 |
| Full game platform (game discovery, state, replay) | Deferred to V1.10 |
| Real auth/credentials management | Deferred — bounded CLI proof only |
| Game Platform resolution | Deferred to M1-R1 sprint |

---

## Request

**V1.9 Formal Close Review** — please review and sign off.

Upon approval, V1.9 will be formally closed and V1.10 scope planning can begin.
