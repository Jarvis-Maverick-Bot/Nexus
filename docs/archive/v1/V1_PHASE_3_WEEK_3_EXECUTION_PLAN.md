# V1 Phase 3 — Week 3: LangGraph Engine Execution Plan

**Version:** V0.2
**Date:** 2026-04-06
**Scope:** Layer 4 — LangGraph Engine (GovernanceState, Nodes, Edges, Pipeline)
**Baseline:** V1_IMPLEMENTATION_PLAN_V0_6.md
**Status:** COMPLETE ✅
**Nova Final Approval:** 2026-04-06
**Commits:** 3d73655, 540c4e3, 9718968, 8e293a5, 64f775e, 6d03567

---

## Overview

Week 3 delivers the **LangGraph Engine** — synchronous graph orchestration for one governed workitem at a time.

**Core framing:** LangGraph orchestration for one governed workitem at a time, with synchronous execution, explicit routing, halt-safe gate behavior, visible blocker handling, and no LangGraph-led authority drift.

---

## Nova-Aligned Answers (2026-04-06)

| # | Question | Decision |
|---|----------|----------|
| Q1 | GovernanceState granularity | **One graph per workitem** — not project-wide dict. Cleaner, simpler checkpoint/restart, easier to debug. |
| Q2 | Node execution model | **Synchronous** — one node runs, returns, routing decides next. Deterministic, testable, checkpointable. |
| Q3 | Gate rejection behavior | **Halt and await intervention** — rejection is a governance decision event, not a routing hint. No auto-return. |
| Q4 | Blocker handling | **Explicit blocker/escalation branch** — graph routes to resolver, not hidden inside stage node. Blocker must remain workflow-visible. |

---

## GovernanceState

One graph run = one workitem. State carries only that workitem's data:

```
GovernanceState = {
    project_id: str,
    task_id: str,
    workitem: WorkItem,
    task_state: TaskState,
    pending_handoffs: list[Handoff],
    gates: dict[str, Gate],
    event_log: list[Event],
    current_action: str,       # "advance" | "block" | "handoff" | "halt" | "gate_approved" | "gate_rejected" | "done"
    halt_reason: str | None,  # set when current_action = "halt"
    blocked: bool,
    blocker: str | None,
}
```

---

## Node Design (Role-Shaped, Not Sovereign)

Nodes are **procedures with scope**, not mini-agents with sovereign discretion.

Each node:
- Receives GovernanceState
- Performs one bounded action within its role scope
- Returns a command dict (advance/block/handoff/halt/done)
- Does NOT own governance judgment
- Does NOT make routing decisions — routing is handled by conditional edges

| Node | Role scope | Possible commands |
|------|------------|-------------------|
| `maverick_node` | PMO coordination | route, monitor |
| `viper_ba_node` | BA stage work | advance, block, handoff, halt |
| `viper_sa_node` | SA stage work | advance, block, handoff, halt |
| `viper_dev_node` | DEV stage work | advance, block, handoff, halt |
| `viper_qa_node` | QA stage work | advance, block, handoff, gate_approved, halt |

---

## Edge Routing (Explicit, Not Automatic)

Conditional edges decide next node based on `current_action` in GovernanceState:

```
BA node returns:
  - "advance"  -> route to SA node
  - "block"    -> route to blocker handling
  - "handoff"  -> route to handoff handling
  - "halt"     -> stop graph, await intervention

SA node returns:
  - "advance"  -> route to DEV node
  - ...

Gate approved -> advance to next stage
Gate rejected -> HALT, await intervention (NOT auto-return)

Any stage on "halt" -> __END__ (graph stops, state checkpointed)
Any stage on "done" -> __END__
```

---

## Day-by-Day Breakdown

### Day 1 — GovernanceState + Graph Scaffold ✅

Commit: 3d73655
- GovernanceState: one workitem per graph, all workflow fields
- Nodes/base.py: NodeFunction protocol + VALID_ACTIONS
- Nodes/maverick.py: maverick_node routes to current stage
- graph.py: StateGraph scaffold with START->maverick->stage routing
- pipeline.py: compile() + run_workitem() + get_pipeline()
- Smoke test: graph compiles, maverick routes to BA, BA halts (stub)

### Day 2 — Stage Nodes Implementation

**Goal:** Define GovernanceState, scaffold LangGraph StateGraph with stage nodes, basic compile.

Specific tasks:
- `langgraph_engine/state.py`: GovernanceState dataclass (one workitem per run)
- `langgraph_engine/__init__.py`: Module init
- `langgraph_engine/nodes/__init__.py`: Node registry
- `langgraph_engine/nodes/base.py`: Base node function pattern (receives state, returns command)
- `langgraph_engine/graph.py`: LangGraph StateGraph scaffold with BA/SA/DEV/QA node placeholders
- `langgraph_engine/pipeline.py`: compile() stub returning compiled graph

Review checkpoint: End of Day 1 🔜

---

### Day 2 — Stage Nodes Implementation ✅

Commits: d01232b (initial), fd2d96a (review fixes)

Initial implementation (d01232b):
- viper_ba/sa/dev/qa nodes with make_viper_node() factory

Nova Day 2 review fixes (fd2d96a):
- NEW: RuntimeContext singleton — config, store, checkpointer, event_journal
- Nodes use get_runtime() instead of creating own dependencies
- viper_qa.py: dedicated QA node returning 'done' explicitly (not halt-via-invalid-transition)
- TaskState persistence errors propagate (no silent pass)
- nodes/base.py docstring: 'action' -> 'current_action'
- pipeline.py: init_runtime() called at start of run_workitem()

Verified: BA->SA->DEV->QA pipeline, QA returns 'done', TaskState marked DONE

---

### Day 3 — Edges + Conditional Routing ✅

Commit: 540c4e3
- langgraph_engine/edges.py: formal edge map documentation
- _maverick_router fixed: routes based on stage only, not current_action
- _stage_router expanded: all 7 actions handled explicitly
- Block routing: maverick detects blocked flag, halts at END
- Verified: BA->SA->DEV->QA done, block halts correctly

**Goal:** Define and implement conditional edges with explicit routing.

Specific tasks:
- `langgraph_engine/edges.py`: Edge definitions
  - `advance` action -> next stage node
  - `block` action -> explicit blocker handling branch
  - `handoff` action -> handoff handling
  - `halt` action -> graph stops, checkpoint saved, await intervention
  - `gate_approved` -> advance to next stage
  - `gate_rejected` -> HALT, do NOT auto-return
  - `done` -> __END__
- Test: verify all routing paths work

Review checkpoint: End of Day 3

---

### Day 4 — Pipeline Compile + Integration ✅

Commit: 05e2015
- advance_stage_tool now uses langgraph_run_workitem() — advances full pipeline
- coordinator: advance_stage no longer requires target_stage
- Verified: BA->SA->DEV->QA, 5 events, TaskState DONE

### Day 5 — E2E Test + Documentation ✅

Commit: (pending push)
- LANGGRAPH_E2E_TEST.py: 8-step E2E test (all steps pass)
- README.md: updated structure, Week 3 status, LANGGRAPH_E2E_TEST.py reference
- Platform model E2E_TEST.py (D2) still valid

### Week 3 — COMPLETE ✅

**Nova final approval: 2026-04-06**
- LangGraph engine layer: real (not placeholder)
- Bounded stage progression: preserved
- Routing/governance posture: aligned
- E2E coverage: present (8-step LANGGRAPH_E2E_TEST.py)
- No remaining blockers

**Soft watchpoints (non-blocking):**
1. RuntimeContext — watch for uncontrolled global-state convenience drift
2. GovernanceState — keep lean, no mini-database growth
3. Stage-node/routing semantics — stay explicit as Week 4+ deepens

**Final commits:**
- 6d03567 — Day 5 E2E + README
- 64f775e — Day 4 fix (silent except removed)
- 8e293a5 — Day 4 fixes (bounded advance, RuntimeContext, actor)
- 9718968 — Day 3 edges + routing
- 540c4e3 — Day 2/3 stage nodes + edges
- 3d73655 — Day 1 scaffold

**Goal:** Finalize pipeline.compile(), integrate with OpenClaw tools.

Specific tasks:
- `langgraph_engine/pipeline.py`: Full compile() implementation
- Wire pipeline into openclaw_integration: advance_stage tool calls compiled graph
- Test: full BA→SA→DEV→QA through compiled pipeline
- Verify checkpointing and event journaling fire within graph execution

Review checkpoint: End of Day 4

---

### Day 5 — E2E Test + Documentation

**Goal:** Full pipeline end-to-end test, node documentation.

Specific tasks:
- Write LangGraph E2E test: one workitem → BA → SA → DEV → QA via compiled graph
- Test halt path: gate rejection halts graph, await intervention
- Test blocker path: blocker detected, graph routes to escalation
- Verify state at each stage checkpoint
- Verify events written at each transition
- `langgraph_engine/README.md`: architecture, node contracts, usage
- Update main README if needed

Review checkpoint: End of Day 5

---

## Guardrails for Week 3

1. **LangGraph does NOT own governance** — it enforces what Platform Core defines
2. **One workitem per graph run** — not project-wide state
3. **Nodes are scoped procedures** — role-shaped, not sovereign agents
4. **Gate rejection = halt** — no automatic return-to-prior-stage
5. **Blockers are workflow-visible** — graph routes explicitly, not hidden inside stage node
6. **All mutations go through Platform Core + Harness** — no hidden side effects
7. **Conditional edges must be deterministic** — based on GovernanceState fields only

---

## Review Cadence

| When | Who | What |
|------|-----|------|
| End of Day 1 | Nova | GovernanceState + graph scaffold |
| End of Day 2 | Nova | Stage nodes + harness wiring |
| End of Day 3 | Nova | Edges + conditional routing |
| End of Day 4 | Nova | Pipeline compile + integration |
| End of Day 5 | Nova + Alex | Full Week 3 end-to-end review |

---

## Success Criteria — Week 3

| # | Criterion |
|---|-----------|
| 1 | GovernanceState carries one workitem through graph |
| 2 | Each stage node can: advance, block, handoff, halt, or complete |
| 3 | Gate approved: advance to next stage |
| 4 | Gate rejected: halt graph, checkpoint, await intervention |
| 5 | Blocker detected: graph routes to explicit escalation branch |
| 6 | Compiled pipeline drives one workitem through BA→SA→DEV→QA |
| 7 | Harness (checkpoint + event journal) fires correctly within graph execution |
| 8 | Graph execution survives simulated restart via checkpoint restore |

---

## Next: Week 4

OpenClaw Integration already scaffolded in Week 2 Day 4. Week 4 will finalize OpenClaw tools + main session coordination.
