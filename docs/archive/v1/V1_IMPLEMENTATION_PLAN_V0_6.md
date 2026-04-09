# V1 Implementation Plan

**Version:** V0.6
**Date:** 2026-04-06
**Based on:** Steps 1-7 freeze framework + Technical Constraints
**Status:** Updated after 2026-04-06 alignment discussion with Alex + Nova

---

## Executive Summary

**Target:** V1 PMO Smart Agent on governed management platform foundation

**Core Principle:**
> Use LangGraph to run the workflow, use Harness/OpenClaw to run the execution, but use our own frozen governance model to define the system.

---

## Agent / Procedure / Object Boundary (Nova-aligned)

**Key clarification from 2026-04-06 discussion.**

The line is not "spawned vs not spawned." The correct boundary is:

| Category | Definition | Examples |
|----------|-----------|----------|
| **Agent** | Role-bearing accountable actor with identity, scope, authority boundary, ownership, lifecycle continuity | Alex, Nova, Jarvis, Maverick, embodied Viper roles |
| **Procedure / Skill** | Bounded reusable method for doing work inside an agent's scope | `check_authority()`, `advance_stage()`, `StateMachine` |
| **Object** | Governed state entity | Project, WorkItem, TaskState, Gate, Handoff, Event |

**Critical rule:** Spawned subagents are one runtime embodiment form of an agent — not the definition of agenthood itself. Nova, Jarvis, and Maverick are agents even when not "spawned" as subagents.

**Application:**
- Viper BA/SA/DEV/QA start as **roles** in the object model
- They upgrade to **agents** when intentionally embodied with: identity, scope, authority boundary, memory, runtime seat
- Platform Core procedures (`check_authority()`, `StateMachine`) are **not agents** — they are mechanisms operated by agents

---

## 5-Layer Memory Model (Design Frame Only)

**From Scout Consolidation Note — design frame, not implementation target.**

| Layer | Name | Description | V1 Status |
|-------|------|-------------|-----------|
| 1 | Ephemeral agent-local | Scratch/thinking space | Deferred |
| 2 | Workflow checkpoint/state | Current execution checkpoint, resumability | Week 2 scaffold delivered |
| 3 | Append-only event journal | Audit / replay / provenance | Week 2 scaffold delivered |
| 4 | Project-shared operational memory | PMO shared state, cross-agent visibility | Design only — deferred |
| 5 | Curated durable memory | MEMORY.md, daily logs | Ongoing — outside repo |

**Important:** Week 1 defined the *object model* for layers 2 and 3. Week 2 delivered the *scaffolding* — checkpoint/journal infrastructure exists but is pending correction/review closure. This is not yet a full memory system.

---

## Harness Boundary Clarification (Nova-aligned)

**Harness = evidence transport / persistence support. Gate/Event = governance meaning.**

Harness may store:
- Test result file paths
- Review artifact paths
- Execution log references
- Deliverable paths
- Checkpoint metadata

Harness must NOT own:
- Approval / rejection meaning
- Governance judgment
- Verification significance

These belong to Gate / Event.

**Known limitations (V1):**
- Checkpoint writes are sequential, not truly atomic — discipline required
- Event file rotation (max_lines) not yet implemented
- Evidence linkage requires in-memory tracking or database backend

---

## Layer Architecture

```
LAYYER 5 │ PMO_SMART_AGENT (operator surface)
LAYYER 4 │ LangGraph Workflow Engine
LAYYER 3 │ Platform Core
LAYYER 2 │ Harness
          │   Layer 2: checkpoint/state (scaffold delivered)
          │   Layer 3: event journal (scaffold delivered)
          │   Evidence: transport/persistence (scaffold delivered)
LAYYER 1 │ OpenClaw / Jarvis Main Session
LAYYER 0 │ Production Nodes (Viper BA/SA/DEV/QA)
```

---

## Module/Component Breakdown

```
gov_langgraph/
│
├── platform_model/                    LAYER 3: PLATFORM CORE
│   ├── objects.py                    Step 2 frozen objects
│   ├── authority.py                 Tier, Action, check_authority
│   ├── state_machine.py             StateMachine, transitions
│   └── exceptions.py                Exception hierarchy
│
├── harness/                          LAYER 2: PERSISTENCE + RESUMABILITY
│   ├── config.py                   HarnessConfig, path settings
│   ├── state_store.py               Layer 2: JSON file I/O
│   ├── checkpointer.py             Layer 2: checkpoint (sequential, not atomic)
│   ├── events.py                   Layer 3: append-only event journal
│   └── evidence.py                 Evidence reference storage (scaffold)
│
├── langgraph_engine/                LAYER 4: WORKFLOW ENGINE
│   ├── nodes/
│   ├── edges.py
│   └── pipeline.py
│
├── openclaw_integration/             LAYER 1: COORDINATION
│   ├── tools.py
│   └── coordinator.py
│
└── pmo_smart_agent/                LAYER 5: OPERATOR SURFACE
    ├── cli.py
    └── dashboard.py
```

---

## Build Order

| Order | Layer | Module | What | Status |
|-------|-------|--------|------|--------|
| 1 | Platform Core | objects.py | Step 2 frozen objects | Week 1 |
| 2 | Platform Core | authority.py | Tier, Action, check_authority | Week 1 |
| 3 | Platform Core | state_machine.py | Transitions + StateMachine | Week 1 |
| 4 | Platform Core | exceptions.py | Exception hierarchy | Week 1 |
| 5 | Harness | config.py | Settings | Week 2 |
| 6 | Harness | state_store.py | Layer 2 JSON I/O | Week 2 |
| 7 | Harness | checkpointer.py | Layer 2 checkpoint + restore | Week 2 |
| 8 | Harness | events.py | Layer 3 event journal | Week 2 |
| 9 | Harness | evidence.py | Evidence reference storage | Week 2 |
| 10 | LangGraph Engine | state.py | GovernanceState | Week 3 |
| 11 | LangGraph Engine | nodes/ | All nodes | Week 3 |
| 12 | LangGraph Engine | edges.py | Transitions | Week 3 |
| 13 | LangGraph Engine | pipeline.py | Compile | Week 3 |
| 14 | OpenClaw Integration | tools.py | Tool definition | Week 4 |
| 15 | OpenClaw Integration | coordinator.py | Main session | Week 4 |
| 16 | PMO Smart Agent | cli.py | Commands | Week 5 |
| 17 | PMO Smart Agent | dashboard.py | Status | Week 5 |

---

## Technical Constraints Checklist

| Constraint | Implementation | Status |
|------------|---------------|--------|
| TC1: OpenClaw as coordinator | openclaw_integration/coordinator.py | Week 4 |
| TC2: Python 3.12+ | gov_langgraph | Week 1 |
| TC3: JSON file checkpoint | harness/state_store.py, harness/checkpointer.py | Week 2 scaffold |
| TC4: Platform Core headless | No UI in Platform Model | Week 1 |
| TC5: PMO = operator view | pmo_smart_agent/ queries + displays | Week 5 |
| TC6: Event emission | Approved V1 simplification: synchronous coordination | Week 1 |
| TC7: All auth through governance | platform_model/authority.py | Week 1 |
| TC8: No multi-OpenClaw V1 | Single session | Week 1 |

---

## V1 Finish Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | WorkItem lifecycle | CREATE -> AUTHORIZE -> EXECUTE -> COMPLETE |
| 2 | Authority enforced | Unauthorized actions rejected by Platform Core |
| 3 | State transitions valid | Invalid transitions blocked by state machine |
| 4 | State persists | JSON checkpoint survives restart |
| 5 | PMO visibility | CLI shows WorkItem status |
| 6 | OpenClaw callable | Tool executes pipeline |
| 7 | End-to-end | Telegram -> LangGraph -> Platform Core -> Result |

---

## Timeline

```
Week 1: Platform Core (objects, authority, state_machine, exceptions)    Delivered
Week 2: Harness (config, state_store, checkpointer, events, evidence)        Scaffold delivered - pending review
Week 3: LangGraph Engine (nodes, edges, pipeline)                           In Progress
Week 4: OpenClaw Integration (tools, coordinator)
Week 5: PMO surface (cli, dashboard) + end-to-end test
```

**Total: ~5 weeks**

---

## Open Items

### Resolved in V0.6
- [x] Agent / Procedure / Object boundary established
- [x] 5-layer memory model as design frame
- [x] Harness boundary clarified
- [x] Week 1 scope: object model, not full operational implementation
- [x] Layer naming consistency

### Ongoing Watchpoints
- [ ] Numeric tier comparison in authority (post-Week 3)
- [ ] WorkItem.current_stage vs TaskState source of truth (post-Week 3)
- [ ] Failed audit record persistent capture
- [ ] Workflow.stage_role_map tightening

### Harness Corrections (post-Week 2)
- [ ] Checkpoint writes are sequential, not atomic - add discipline documentation
- [ ] Event file rotation not yet implemented
- [ ] Evidence linkage requires in-memory or database backend
