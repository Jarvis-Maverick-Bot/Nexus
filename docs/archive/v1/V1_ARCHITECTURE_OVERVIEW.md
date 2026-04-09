# PMO Smart Agent V1 — Architecture Overview

**Author:** Jarvis
**Date:** 2026-04-09
**Status:** V1 ARCHIVE — part of v1.0.0 freeze set

---

## Purpose

This document provides the canonical V1 architecture overview: the layer model, the split of responsibilities between PMO shell and gov_langgraph, and the source-of-truth boundaries within the system.

It is the primary design reference for the V1 archive review pack.

---

## Authority Order in the V1 Archive

For future review, the V1 archive should be interpreted in this order:

1. `V1 SPEC/STEP_1..STEP_7` — authoritative scope, boundary, acceptance, and technical-constraint baseline
2. `PMO_SMART_AGENT_V1_PRD_V0_3.md` — product intent and scope framing
3. `V1_IMPLEMENTATION_PLAN_V0_6.md` — planned delivery path for V1
4. `V1_ARCHITECTURE_OVERVIEW.md` — this top-level architecture explanation
5. `PMO_V1_WEB_UI_ARCH.md` — PMO shell architecture for the frozen V1 surface
6. `HARNESS_INTEGRATION_PLAN.md` — Harness integration explanation
7. `LANGGRAPH_INTEGRATION_PLAN.md` — subordinate runtime-layer explanation
8. `V1_PHASE_*_WEEK_*_EXECUTION_PLAN.md` — execution chronology and delivery record
9. `V1_FINAL_STATUS.md` — freeze-state summary and closure record

If documents differ in tone or abstraction level, the higher-order scope and boundary documents above should govern interpretation.

---

## Layer Model

V1 is organized into 4 layers (from outer to inner):

```
Layer 1: PMO Shell          — External interface (Web UI, Telegram)
Layer 2: Harness            — State persistence + event journal
Layer 3: Platform Model     — Governance objects, authority, state machine
Layer 4: LangGraph Engine   — Pipeline execution, role-shaped agents
```

### Layer 1 — PMO Shell (`pmo_web_ui/`, `openclaw_integration/`)
External-facing interface. Receives HTTP requests, validates input, delegates to Harness layer.

Responsibilities:
- Expose REST API for 3 V1 functions: kickoff, status view, gate confirmation
- Translate external requests into Harness calls
- Return structured responses to clients

Does NOT own: governance logic, pipeline sequencing, state machine transitions.

### Layer 2 — Harness (`gov_langgraph/harness/`)
State persistence and runtime trace. Provides checkpoint/resume capability.

Responsibilities:
- `StateStore`: JSON file-based workitem/taskstate persistence
- `Checkpointer`: named checkpoint snapshots for resumability
- `EventJournal`: append-only event log for audit trail
- `EvidenceStore`: evidence reference storage per workitem

Does NOT own: governance meaning, decision authority, verification judgment.

### Layer 3 — Platform Model (`gov_langgraph/platform_model/`)
Governance primitives and rules. Defines what the system enforces.

Responsibilities:
- `Authority`: tier/action matrix, `check_authority()`
- `StateMachine`: stage-to-stage transitions, terminal state detection
- `HandoffDocument`: 10-field schema for BA→SA→DEV→QA handoffs
- `BAAction/SAction/DEVAction/QAAction`: action enumerations
- `Exception hierarchy`: typed governance exceptions

Does NOT own: runtime execution, pipeline sequencing, agent behavior.

### Layer 4 — LangGraph Engine (`gov_langgraph/langgraph_engine/`)
Pipeline execution engine. Routes workitems through stage nodes.

Responsibilities:
- `Graph`: compile() builds the LangGraph directed graph
- `Pipeline`: run_workitem() drives a workitem through stages
- `AgentExecutor`: enforces 3 layers (pre-execution authority, action-level governance, completion check)
- Role-shaped agents: `make_viper_ba/sa/dev/qa()`

Does NOT own: external interfaces, state persistence, governance rule definitions.

---

## Source of Truth Boundary

**Within the PMO Smart Agent:**

- `gov_langgraph/harness/StateStore` = authoritative source for workitem/taskstate
- `gov_langgraph/harness/EventJournal` = authoritative source for event history
- `gov_langgraph/platform_model/StateMachine` = authoritative source for stage transition rules

**External systems (NOT owned by PMO V1):**

- `openclaw_integration/tools.py` — OpenClaw tool wrappers (translation layer)
- `pmo_web_ui/main.py` — Web UI server (interface only)
- GitHub issues — assignment and tracking surface (display only, not authoritative)

**The PMO V1 does NOT own:**
- The Viper external delivery pipeline (execution lives outside)
- Long-term evidence model (evidence = `gate_decision_note` emptiness in V1)
- Multi-user / multi-project support

---

## PMO Shell vs gov_langgraph Responsibility Split

```
External Request
       ↓
pmo_web_ui/main.py  ←→  openclaw_integration/tools.py
       ↓ (Harness API)
Harness (StateStore / EventJournal / Checkpointer / EvidenceStore)
       ↓
Platform Model (Authority / StateMachine / HandoffDocument)
       ↓
LangGraph Engine (Graph / Pipeline / AgentExecutor / RoleShapedAgents)
```

**What the PMO shell handles:**
- HTTP serving (port 8000)
- Tool registration with OpenClaw
- API endpoint routing
- Request/response serialization

**What gov_langgraph handles:**
- All governance logic
- Stage state machine
- Pipeline execution
- Evidence and event tracking

**In V1:** The two are intentionally co-located in the same repo (`D:\Projects/gov_langgraph/`). Future work may extract gov_langgraph as an independent module.

---

## V1 Scope Boundaries

**In V1:**
- Single project (`DEFAULT_PROJECT_ID = "pmo-kickoff"`)
- Single-user assumption (Alex = sole operator)
- 3 PMO functions only: kickoff, status view, gate confirmation
- Evidence = `gate_decision_note` emptiness (simplification)

**Explicitly out of V1 scope:**
- Intelligent PM feedback (Maverick advisory)
- Full project reports
- Formal acceptance workflow
- Multi-user support
- gov_client.py abstraction layer

---

## Architecture Decisions Locked at V1

| Decision | Rationale |
|----------|-----------|
| JSON file-based state (not DB) | Simplification for V1; not doctrine |
| Single-project hardcoded ID | Pragmatic for V1 single-use case |
| Evidence = `gate_decision_note` emptiness | Simplest workable proxy; not long-term model |
| Role-shaped agents (BA/SA/DEV/QA) | Reusable factory pattern for stage agents |
| 3-layer AgentExecutor enforcement | Pre-execution → action-level → completion |

---

## Archive Reference

For full architecture detail, see:
- **Web UI + API spec:** `PMO_V1_WEB_UI_ARCH.md`
- **Harness integration:** `HARNESS_INTEGRATION_PLAN.md`
- **LangGraph integration:** `LANGGRAPH_INTEGRATION_PLAN.md`
- **PRD scope:** `PMO_SMART_AGENT_V1_PRD_V0_3.md`
- **7-step SPEC baseline:** `PMO_SMART_AGENT_PLAN_V1.md`
- **Implementation path:** `IMPLEMENTATION_PATH_V0_1.md`
