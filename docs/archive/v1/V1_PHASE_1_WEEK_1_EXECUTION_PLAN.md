# V1 Phase 1 — Platform Core: Execution Plan

**Version:** V0.1
**Date:** 2026-04-05
**Scope:** Week 1 implementation — Platform Core (`platform_model/`)
**Baseline:** `V1_IMPLEMENTATION_PLAN_V0_5.md`
**Status:** For Alex + Nova review before start

---

## Overview

Week 1 delivers the **Platform Core** — the source of truth layer. Everything in LangGraph, Harness, and the PMO surface depends on this. A mistake here propagates everywhere.

The goal is: **correct and complete, not fast.** Speed matters less than getting the object model and authority rules right.

---

## Deliverables

| # | Module | File | Description |
|---|--------|------|-------------|
| 1 | Objects | `platform_model/objects.py` | Step 2 frozen objects |
| 2 | Authority | `platform_model/authority.py` | Tier 1/2/3 rules from Step 4 |
| 3 | State Machine | `platform_model/state_machine.py` | Valid transitions |
| 4 | Exceptions | `platform_model/exceptions.py` | `AuthorityViolation` and others |
| 5 | Package | `platform_model/__init__.py` | Public exports |

---

## Daily Breakdown

### Day 1 — `Project` + `WorkItem` (objects.py)

**Goal:** Two most critical objects implemented and reviewed.

**Specific tasks:**
- Define `Project` class with all Step 2 fields
- Define `WorkItem` class with all Step 2 fields (merged Task/WorkItem as per Step 2)
- Add `task_id`, `project_id`, `current_stage`, `current_owner`, `task_status` core fields
- Add `dependency_task_ids`, `expected_deliverable`, `handoff_target`, `priority`
- Implement `TaskState` as a separate object (Step 2 requirement: task definition ≠ task state)
- Add `workflow_id` to link WorkItem to Workflow

**Clarifications that WILL come up:**
1. `Task` vs `WorkItem` — Step 2 says merged. Use `WorkItem` as the class name, with a `task_id` field (not `work_item_id`) to match Step 2's field naming convention.
2. `TaskState` as a separate class vs embedded in `WorkItem` — Step 2 explicitly requires separation. `WorkItem` holds definition; `TaskState` holds current condition.
3. `dependency_task_ids` — list of strings or list of UUIDs? Use `list[str]` for simplicity.
4. `handoff_target` — is this an owner string, or a stage? Per Step 2 it refers to `to_owner` in Handoff. Use `str | None`.

**Review checkpoint:** End of Day 1 — Nova reviews `Project` + `WorkItem` before Day 2.

---

### Day 2 — `Workflow` + `TaskState` + `Handoff` (objects.py)

**Goal:** Remaining Step 2 objects implemented.

**Specific tasks:**
- Define `Workflow` with `stage_list`, `allowed_transitions`, `stage_role_map`, `default_handoff_points`, `default_gate_points`
- Implement `TaskState` with `current_stage`, `state_status`, `current_blocker`, `next_expected_action`, `last_updated_at`
- Define `Handoff` with all Step 2 fields
- Define `Gate` with `gate_id`, `task_id`, `stage`, `gate_type`, `decision`, `decision_by`, `decision_note`, `decided_at`
- Define `Event` with all Step 2 fields
- Add `project_id` required on `Event` (per Step 2)

**Clarifications that WILL come up:**
1. `stage_role_map` — how is this structured? Recommend `dict[str, list[str]]` where key = stage name, value = list of role names allowed in that stage.
2. `Gate.decision` — enum with values `approved | rejected | held | stopped | returned` per Step 2.
3. `Event.event_type` — open enum or free string? Recommend open for V1 with a small set of expected values.
4. `Handoff.deliverable_reference` — string (file path/URL) or a separate Artifact object? Step 2 says it's a reference field. Keep as `str | None` for now.
5. `TaskState.current_blocker` — free text or structured? Keep as `str | None` for V1.

**Review checkpoint:** End of Day 2 — Nova reviews all Step 2 objects before Day 3.

---

### Day 3 — `authority.py` — Tier 1/2/3

**Goal:** Step 4 authority rules implemented as enforceable code.

**Specific tasks:**
- Define `Tier` enum: `TIER1`, `TIER2`, `TIER3`
- Map Tier 1 → Management Layer (initiate, request)
- Map Tier 2 → Management + Advisory (authorize, approve_stage)
- Map Tier 3 → All layers (execute_stage, verify)
- Implement `check_authority(action, role, stage)` function
- Implement authority check for each Step 3 action:
  - `create_project` → TIER2 (Management Layer only)
  - `create_task` → TIER2
  - `update_task` → TIER2 + current owner
  - `submit_handoff` → current owner of task/stage OR TIER2
  - `approve/reject/hold/stop/return` → TIER2 (Gate authority)
  - `update_task_state` → current owner + TIER2
  - `record_blocker` / `resolve_blocker` → current owner + TIER2
- Add `AuthorizationRecord` tracking for audit trail

**Clarifications that WILL come up:**
1. Role representation — string enum (`"maverick"`, `"viper_ba"`) or formal `Role` enum? Recommend formal `Role` enum to avoid string typos.
2. Who is "Management Layer" in V1? Alex (human), Jarvis, Nova, Maverick (logical). The code should reference `Role.MANAGEMENT` — the enum handles the mapping.
3. `TIER2 + current owner` for `update_task` — does TIER2 include the current owner, or is it additive? Step 4 says "current owner and Management Layer." So: `current_owner == actor OR tier >= TIER2`.
4. `submit_handoff` — current owner OR TIER2. But what if the current owner is a Delivery Layer agent (viper_ba, etc.) and they try to handoff? Step 4 says they CAN submit handoff for owned task/stage. So handoff is allowed for delivery layer on owned task, but gate decisions are not.

**Review checkpoint:** End of Day 3 — Nova reviews authority rules. This is the most governance-critical piece.

---

### Day 4 — `state_machine.py`

**Goal:** Valid state transitions enforced by code, not assumption.

**Specific tasks:**
- Define `Transition` dataclass: `from_stage`, `to_stage`, `allowed_roles`, `required_gate`
- Build `VALID_TRANSITIONS` map keyed by `workflow_id`
- Implement `validate_transition(current_stage, target_stage, role, task_id)` function
- Return list of valid next stages for a given task + role
- Integrate with `authority.py` — state machine calls `check_authority()` before allowing transition

**Clarifications that WILL come up:**
1. Stage names — hardcoded or workflow-specific? Per Step 2, `Workflow.stage_list` defines stages. The state machine validates against the workflow's own `allowed_transitions`.
2. Default transitions — who defines `allowed_transitions` initially? The Workflow object itself carries them. For V1 demo, we define a standard pipeline.
3. Gate-required transitions — some transitions (stage advances) may require an approved Gate. `required_gate: bool` field on Transition.
4. What happens on invalid transition? `InvalidTransitionError` raised, caught by Platform Core, surfaced as user-facing message.

**Review checkpoint:** End of Day 4 — Nova reviews state machine logic.

---

### Day 5 — Integration + Exceptions + Package Export

**Goal:** Everything wires together, clean public API, review-ready.

**Specific tasks:**
- Implement `platform_model/exceptions.py`: `AuthorityViolation`, `InvalidTransitionError`, `ObjectNotFoundError`, `ValidationError`
- `platform_model/__init__.py` exports only public interfaces (not internal helpers)
- Smoke test: import all objects, create instances, run a basic authority check
- Write basic unit tests: create WorkItem, check authority, validate transition
- Document all public classes and methods in docstrings

**Clarifications that WILL come up:**
1. Should exceptions be subclasses of a base `PlatformException`? Yes — makes error handling cleaner for callers.
2. What validation belongs in `__init__` vs separate `validate()` method? Light validation in `__init__` (required fields, types), complex validation in `validate()`.
3. UUID generation — where? `task_id = str(uuid4())` in `__post_init__` using dataclasses.

---

## TODO List — Week 1 Platform Core

### Before Day 1 — RESOLVED ✅
- [x] Resolve Open Items 1-4 ✅ (answered by Alex + Nova)
- [x] Alex + Nova confirm: can start ✅

### Day 1 — Project + WorkItem ✅
- [x] `platform_model/__init__.py` created
- [x] `platform_model/objects.py` created
- [x] `Project` class with all Step 2 fields
- [x] `WorkItem` class with all Step 2 fields
- [x] `TaskState` as separate class (not embedded in WorkItem)
- [x] Smoke test passed — import + create + advance + block/unblock
- [x] Nova review: Project + WorkItem ✅ approved (Nova, 2026-04-05)

### Day 2 — Workflow + Handoff + Gate + Event ✅
- [x] `Workflow` class with `stage_list`, `allowed_transitions`, `stage_role_map`
- [x] `TaskState` fully implemented
- [x] `Handoff` class with all Step 2 fields
- [x] `Gate` class with decision enum (`approved | rejected | held | stopped | returned`)
- [x] `Event` class with all Step 2 fields
- [x] Smoke test passed — all 7 Step 2 objects functional
- [x] Nova review: all Step 2 objects ✅ approved (Nova, 2026-04-05)

### Day 3 — Authority Rules ✅
- [x] `Tier` enum: TIER1 (query), TIER2 (Management governance), TIER3 (Delivery execution)
- [x] Role → Tier mapping: Management → TIER2, Delivery → TIER3
- [x] `Action` enum with all Step 3 actions organized by category
- [x] `ActionRule` with `management_only` + `owner_check` for fine-grained control
- [x] `check_authority()` with proper management_only gate
- [x] `AuthorizationRecord` for audit trail
- [x] Smoke tests passed — 8/8 authority checks correct
- [x] Nova review: authority rules ✅ approved (Nova, 2026-04-05)

### Day 4 — State Machine ✅
- [x] `StateMachine` class: advance_stage(), is_valid_transition(), get_valid_transitions()
- [x] `InvalidTransitionError`, `StageNotFoundError`, `TransitionRecord`
- [x] advance_stage() validates: workflow allowed_transitions + authority check
- [x] advance_stage() now mutates work_item.current_stage
- [x] get_current_stage_info() for pipeline visibility
- [x] Smoke tests: BA->SA OK, BA->DEV denied, MAVERICK advance OK
- [x] Nova review: state machine ✅ approved (Nova, 2026-04-05)

### Day 5 — Integration + Package ✅
- [x] `platform_model/exceptions.py` (PlatformException + AuthorityViolation, InvalidTransitionError, StageNotFoundError, ObjectNotFoundError, ValidationError)
- [x] Public exports via `__init__.py`
- [x] Smoke test: import + create instances + authority check + advance_stage mutation
- [x] Nova + Alex review: full Platform Core ✅ approved (Nova, 2026-04-05)

### Week 1 Gate ✅
- [x] All 7 Step 2 objects exist with correct fields
- [x] `check_authority()` enforces Tier 1/2/3 correctly
- [x] `validate_transition()` works correctly
- [x] Code is importable and smoke-tested
- [x] Zero governance model violations (Nova sign-off)

## Review Cadence

| When | Who | What |
|------|-----|------|
| End of Day 1 | Nova | Project + WorkItem object model |
| End of Day 2 | Nova | All Step 2 objects |
| End of Day 3 | Nova | Authority rules (critical) |
| End of Day 4 | Nova | State machine |
| End of Day 5 | Nova + Alex | Full Platform Core review |

**Format:** Nova reviews and comments in the shared doc. Alex decides if anything needs reopening.

---

## Guardrails for Week 1

These are red lines. If any are breached, stop and raise before continuing:

1. **Do not add objects not in Step 2** — If you think something is missing, document it as an open item, don't silently add it
2. **Do not let internal structures become governance objects** — Artifact, DecisionRecord, authorization_history are support structures, not Step 2 objects
3. **Do not implement event-driven logic** — TC6 is synchronous for V1
4. **Do not let LangGraph creep into Platform Core** — Platform Model owns business truth; LangGraph calls it, doesn't define it
5. **Do not skip the authority check** — Every mutation action goes through `check_authority()` even if it feels redundant
6. **Ask when uncertain** — Don't guess at governance intent. Open an issue and ask Nova/Alex

---

## Open Items — RESOLVED

| # | Question | Answer |
|---|----------|--------|
| 1 | `Role` enum names | `ALEX`, `NOVA`, `JARVIS`, `MAVERICK`, `VIPER_BA`, `VIPER_SA`, `VIPER_DEV`, `VIPER_QA` |
| 2 | Default V1 pipeline stages | `BA`, `SA`, `DEV`, `QA` |
| 3 | V1 demo project | Template first → validate against real project after stable |
| 4 | Exception messages | Operator-facing / human-readable by default; developer detail kept internally |

---

## Success Criteria — Week 1

| # | Criterion |
|---|-----------|
| 1 | All 7 Step 2 objects exist in `objects.py` with correct fields |
| 2 | `check_authority(action, role, stage)` correctly enforces Tier 1/2/3 |
| 3 | `validate_transition()` correctly allows/blocks stage transitions |
| 4 | `AuthorityViolation` raised for unauthorized actions |
| 5 | `InvalidTransitionError` raised for invalid stage transitions |
| 6 | Code is importable and smoke-tested |
| 7 | Zero governance model violations (Nova confirms) |

---

## Next: Week 2

**Harness** — JSON checkpoint persistence (`state_store.py`, `checkpointer.py`, `config.py`)

---

# V1 Phase 2 — Week 2 TODO List

### Before Week 2
- [x] V0.6 alignment discussion with Alex + Nova (2026-04-06)
- [x] Agent/Procedure/Object boundary established (Nova-aligned)
- [x] 5-layer memory model confirmed as design frame only

### Week 2 Day 1 — Harness Layer ✅ (2026-04-06)
- [x] `harness/config.py` — HarnessConfig, path settings ✅
- [x] `harness/state_store.py` — Layer 2 JSON file I/O for Project, WorkItem, TaskState ✅
- [x] `harness/checkpointer.py` — Layer 2 checkpoint before/after + restore ✅ (sequential, not atomic — documented)
- [x] `harness/events.py` — Layer 3 append-only event journal ✅ (file rotation deferred)
- [x] `harness/evidence.py` — Evidence reference storage ✅ (JSONL format fixed)
- [x] Smoke tests passed
- [x] JSONL format corrected (indent=2 removed)
- [x] Nova review ✅ approved (commit 91e0677)

### Week 2 Day 2 — Integration + Wire to Platform Core
- [ ] Wire StateMachine + Checkpointer together
- [ ] Wire EventJournal into workflow transitions
- [ ] Smoke test: full pipeline persistence end-to-end

### Week 2 Gate
- [ ] Layer 2 + Layer 3 harness working end-to-end
- [ ] Evidence references persist and load correctly
- [ ] Nova sign-off on full harness layer
