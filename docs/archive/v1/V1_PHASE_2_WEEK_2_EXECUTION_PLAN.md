# V1 Phase 2 — Week 2: Harness Layer — FINAL

**Version:** V1.0 FINAL
**Date:** 2026-04-06
**Scope:** Harness — Layer 2 + Layer 3 persistence
**Baseline:** V1_IMPLEMENTATION_PLAN_V0_6.md
**Status:** COMPLETE — All 5 days delivered and Nova-approved

---

## Overview

Week 2 delivered the **Harness Layer** — persistence + resumability for Platform Core.

**Two layers delivered:**
- **Layer 2:** Workflow checkpoint/state — resumability + operational runtime state
- **Layer 3:** Append-only event journal — audit / replay / provenance

---

## Day-by-Day Breakdown

### Day 1 — Config + State Store + Checkpointer ✅

Commits: 808124c, 5d13436, 91e0677 (Nova approved)
- harness/config.py: HarnessConfig, path settings
- harness/state_store.py: Layer 2 JSON file I/O
- harness/checkpointer.py: Layer 2 checkpoint before/after + restore
- harness/events.py: Layer 3 append-only event journal
- harness/evidence.py: Evidence reference storage

### Day 2 — Wire StateMachine + Checkpointer + EventJournal ✅

Commit: 9dabc16 (Nova approved with notes)
- StateMachine accepts checkpointer= + event_journal= via dependency injection
- advance_stage() calls checkpoint_before before advancing
- advance_stage() calls checkpoint_after after advancing
- advance_stage() appends stage_advanced event to EventJournal
- Smoke test: BA->SA->DEV, checkpoint recover, event journal verified

**Nova notes:**
1. checkpoint_after() reuses get_latest_checkpoint() — direction is right but looser than ideal
2. Restart recovery not independently verifiable from state_machine.py alone — needs Day 5 end-to-end
3. WorkItem.current_stage vs TaskState.current_stage source-of-truth watchpoint deferred post-Week 3

### Day 3 — PMO Visibility + CLI Integration ✅

Commits: 88dc4fa, fbf28ba (Nova approved)
- pmo_smart_agent/cli.py: 6 commands — status, list, pipeline, events, checkpoint, evidence
- pmo_smart_agent/dashboard.py: get_pipeline_view() + render_pipeline_text()
- PMO reads backed by StateStore (explicit query paths, not raw access)
- PMO writes go through Platform Core methods
- Bug fix: list/pipeline required project_id positional arg, handlers fixed

### Day 4 — OpenClaw Integration + Tool Definition ✅

Commits: 361dfd4, 9fcec70, f1866b0, d91ebe7 (Nova approved)
- openclaw_integration/tools.py: 8 @tool functions — create_project, create_task, advance_stage, submit_handoff, approve_gate, reject_gate, get_status, list_tasks
- openclaw_integration/coordinator.py: Coordinator routes Telegram → tool, formats responses
- Bug fixes: gate_type local variable, save_gate/save_handoff, dict eager evaluation
- Hardcode fix: V1_PIPELINE_STAGES centralized in platform_model.workflows
- All active paths now reference central source — no hardcoded stage literals

### Day 5 — End-to-End Test + Documentation ✅

Commits: 96d61fb, 6d2c1f9 (Nova approved)
- E2E_TEST.py: All 8 steps pass — create project → create task → advance BA→SA→DEV→QA → verify events → approve gate → submit handoff → checkpoint recover → final verification
- README.md: Setup, usage, project structure, V1 pipeline reference, authority model, design decisions
- README authority wording corrected: TIER2=alex/nova/jarvis/maverick, TIER3=viper_*

---

## Aligned Decisions (Alex + Nova, 2026-04-06)

| # | Decision |
|---|----------|
| 1 | Who creates Checkpointer/EventJournal? Dependency injection — caller creates and passes. No global state. |
| 2 | PMO CLI reads: explicit query paths backed by StateStore. Writes: go through Platform Core methods. |
| 3 | OpenClaw tool return format: structured dict — Platform Core returns data, coordinator formats. |
| 4 | Session restart recovery: Coordinator owns recovery policy — harness exposes restore, coordinator decides when. |

---

## Guardrails for Week 2

1. Harness does not own governance meaning — never store approval/rejection logic in evidence or checkpoint
2. Events are append-only — never modify or delete events in EventJournal
3. Layer 2 and Layer 3 are separate — state and event journal stay in separate modules
4. Checkpoint discipline — always checkpoint_before before advancing, checkpoint_after after
5. Evidence is a reference, not the artifact — evidence.py stores paths, not content
6. Do not let LangGraph creep into Harness — pure persistence concerns only

---

## Review Cadence

| When | Who | What | Status |
|------|-----|------|--------|
| End of Day 1 | Nova | Config + StateStore + Checkpointer | ✅ |
| End of Day 2 | Nova | Events + Evidence + Wire integration | ✅ |
| End of Day 3 | Nova | CLI + PMO visibility | ✅ |
| End of Day 4 | Nova | OpenClaw integration + tools | ✅ |
| End of Day 5 | Nova + Alex | Full Week 2 end-to-end review | ✅ |

---

## Success Criteria — Week 2

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Project/WorkItem/TaskState survive session restart via StateStore | ✅ |
| 2 | Checkpoint restores to last completed state after crash | ✅ |
| 3 | All stage transitions append events to EventJournal | ✅ |
| 4 | Evidence references persist and are retrievable by task | ✅ |
| 5 | `pmo status` shows correct current state from StateStore | ✅ |
| 6 | Full pipeline: Telegram → Tool → Platform Core → Harness → Event → Result | ✅ |
| 7 | Session restart: recover from checkpoint, continue without data loss | ✅ |

---

## Commits Summary

| Day | Commit | Description |
|-----|--------|-------------|
| Day 1 | 808124c, 5d13436, 91e0677 | Harness scaffold + JSONL fix |
| Day 2 | 9dabc16 | StateMachine wired with checkpointer + event journal |
| Day 3 | 88dc4fa | PMO CLI + dashboard |
| Day 3 | fbf28ba | Fix CLI list/pipeline project_id bug |
| Day 4 | 361dfd4 | OpenClaw tools + coordinator |
| Day 4 | 9fcec70 | Fix gate_type bug + save_gate/save_handoff |
| Day 4 | f1866b0 | Centralize V1 workflow in platform_model.workflows |
| Day 4 | d91ebe7 | Fix dashboard hardcoded stage list |
| Day 5 | 96d61fb | E2E test + README |
| Day 5 | 6d2c1f9 | Fix README authority tier wording |

---

## Next: Week 3

**LangGraph Engine** — GovernanceState, nodes (maverick, viper_*), edges, pipeline compilation
