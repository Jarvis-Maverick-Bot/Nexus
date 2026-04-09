# V1 Phase 3 — Week 4: Real Agent Workflow Integration

**Version:** V0.2 DRAFT — Nova-aligned
**Date:** 2026-04-06
**Scope:** Integrate real governed agent execution with the LangGraph engine
**Baseline:** V1_IMPLEMENTATION_PLAN_V0_6.md + Week 3 COMPLETE
**Status:** APPROVED — Nova + Alex approved 2026-04-06
**Version:** V0.2

---

## Overview

Week 4 addresses the core proof question: **can the system coordinate real governed execution through role-shaped workflow behavior without drifting?**

After Weeks 1-3 we have:
- Platform Core (objects, authority, state machine)
- Harness (persistence, checkpointing, event journal)
- LangGraph Engine (graph scaffold, stage nodes, edge routing, pipeline compile)

Week 4 connects these to **real agent execution** — verifying that role-shaped agents (Viper BA, SA, DEV, QA) actually operate within the governed system.

---

## Nova-Aligned Design Decisions (2026-04-06)

### Q1 — Role-shaped agent definition (LOCKED)

**Definition:** A role-shaped agent is a runtime-executing actor constrained by role-specific identity, scope, authority, and artifact obligations.

A role-shaped agent must have all of these:
1. Role identity
2. Scope boundary
3. Authority boundary
4. Expected artifact responsibility
5. Runtime embodiment

**Not enough:** SOUL.md/SCOPE.md alone. Not enough: stage-specific tools alone.

---

### Q2 — Agent execution model (LOCKED)

**Synchronous for V1.**

- Stage agent is invoked
- Produces artifact/result
- Returns
- Pipeline decides next step

**Why synchronous:** easier to govern, checkpoint, review, debug. No hidden runtime complexity.

**Avoid:** Background async multi-agent waiting/polling as default in V1.

---

### Q3 — Authority enforcement boundary (LOCKED)

**Both pre-execution and tool-level, with final governance review after return.**

Structure:
1. Pipeline/runtime entry checks — Is this role allowed to attempt this stage/work?
2. Tool/action-level enforcement — Is this exact action allowed for this role on this object?
3. Completion/gate review — Did the returned output satisfy governance conditions?

If authority is enforced only at the end when the agent reports completion, too much uncontrolled execution has already happened.

---

### Q4 — Handoff artifact minimum (LOCKED)

**Minimum required schema for every stage handoff:**

| Field | Description |
|-------|-------------|
| task_id / project_id | Identity |
| from_stage / to_stage | Stage context |
| producer_role | Who produced it |
| artifact_references | What was produced |
| handoff_summary | What was done |
| known_limitations | Open issues / risk |
| next_expected_action | What happens next |
| timestamp | When |
| status | Acceptance state |

**Principle:** The next stage should not have to guess what it received, what is complete, what is missing, what risk remains.

---

## Nova's Guardrails (explicit, non-negotiable for V1)

1. **No agent-first redefinition of architecture** — Agents are execution actors inside the governed system, not the new center of truth
2. **No free-form autonomous role drift** — Agents must stay bounded to their role/stage obligations
3. **Artifacts remain first-class** — Agent conversation is not enough; handoffs must stay visible and reviewable
4. **Human/governance review stays explicit** — Real agent execution does not mean automatic trust
5. **Keep V1 runtime simple** — No unnecessary async orchestration, polling complexity, or hidden background control loops

---

## Week 4 Scope — Real Agent Workflow Integration

### Goal

Demonstrate that a real workitem can be created, assigned to a role-shaped agent, and have that agent execute within governed boundaries — with no authority drift.

### Core deliverables

**Day 1 — Agent spawning and role binding**
- Maverick spawns Viper agents with all 5 role-shaped properties (identity, scope, authority, artifact obligation, runtime embodiment)
- Agent receives: task_id, project_id, current_stage, authority scope
- Agent produces: stage handoff document (minimum schema), next action recommendation
- No agent outside its role boundary can be spawned

**Day 2 — Governance boundary enforcement at agent level**
- Pre-execution: role allowed to attempt this stage?
- Tool-level: exact action allowed for this role on this object?
- Completion: did output satisfy governance conditions?
- Agent cannot bypass pipeline; all actions routed through stage nodes
- Blocker surfaces to Maverick, not silently swallowed

**Day 3 — Handoff protocol between agents**
- Each handoff follows minimum schema (10 required fields)
- Handoff document written to evidence store
- Handoff event logged with from_owner, to_owner, artifact_ref
- Next agent can read prior stage artifact before starting

**Day 4 — Authority hardening through runtime**
- `check_authority()` enforced at entry to each stage node
- Unauthorized agent attempts rejected and logged with reason
- Escalation path: agent denied → Maverick → Jarvis → Alex
- Audit trail for all authority decisions

**Day 5 — E2E test with real agents**
- Full pipeline: project created → Viper BA receives task → BA completes → handoff to SA → SA completes → handoff to DEV → DEV completes → handoff to QA → QA approves → DONE
- All governance events journaled
- Authority decisions verifiable
- Rollback/compensation path tested

---

## Handoff Schema (minimum, required in V1)

```yaml
handoff:
  task_id: str
  project_id: str
  from_stage: str       # BA | SA | DEV | QA
  to_stage: str
  producer_role: str    # viper_ba | viper_sa | viper_dev | viper_qa
  artifact_references: list[str]
  handoff_summary: str
  known_limitations: str
  next_expected_action: str
  timestamp: str        # ISO 8601
  status: str           # accepted | pending_review | rejected
```

---

## Self-Verification Checklist (Jarvis)

After each day, before requesting Nova review, Jarvis verifies:

**Day 1 — Agent spawning and role binding**
- [x] Compiles: `python -c "from gov_langgraph.langgraph_engine import compile; compile()"`
- [x] Agent spawns with all 5 role-shaped properties
- [x] Handoff document has all 10 required schema fields
- [x] No authority drift: agent cannot execute outside its scoped role

**Day 2 — Governance boundary enforcement**
- [x] Pre-execution check fires for unauthorized roles
- [x] Tool-level enforcement fires for out-of-scope actions
- [x] Agent action routed through LangGraph pipeline (not bypassing it)
- [x] Events written to journal for each agent action
- [x] Blocker surfaces to Maverick, not silently swallowed

**Day 3 — Handoff protocol**
- [x] Each handoff produces required 10-field schema
- [x] Handoff document written to evidence store
- [x] Handoff event logged with all required fields
- [x] Next agent can read prior stage artifact before starting

**Day 4 — Authority runtime hardening**
- [x] `check_authority()` fires at stage node entry
- [x] Unauthorized attempt: logged, rejected, halt_reason set
- [x] Escalation path: agent denied → Maverick notified → Jarvis notified
- [x] Audit log contains: who, what, why denied, when

**Day 5 — Full E2E**
- [x] `python LANGGRAPH_E2E_TEST.py` — all 9/9 steps pass
- [x] Full graph pipeline: BA→SA→DEV→QA→DONE verified (current_action=done, final_stage=QA, TaskState=DONE)
- [x] 4 handoffs produced (BA→SA, SA→DEV, DEV→QA, QA→END), all complete with 10 fields
- [x] 4 agent_executed events journaled (one per stage actor)
- [x] 3 stage_advanced events journaled (BA→SA, SA→DEV, DEV→QA)
- [x] Checkpoint restore works
- [x] Authority failure propagates (PermissionError, not silently swallowed)
- [x] Test and milestone narrative aligned (Nova note addressed)

**Before any commit:**
- [x] `git log --oneline` shows clean, atomic commits per day
- [x] No test files left in repo root
- [x] README reflects any new commands or structure changes
- [x] Test claims match milestone narrative (no overclaiming vs reviewed evidence)

---

## Open Items

- [x] Nova alignment on Week 4 scope and design questions (2026-04-06)
- [x] Alex approval to start Day 1
- [x] Viper agent SOUL.md/SCOPE.md review (confirm they reflect role-shaped definition)
- [x] Handoff schema codified in platform_model

---

## Day 1 — COMPLETE ✅

Commit: d311bb1 + bab734f (fixes)
- `platform_model/handoff_schema.py`: HandoffDocument (10-field minimum schema)
- `langgraph_engine/agent.py`: RoleShapedAgent with all 5 properties + factories
- Smoke tests: 9/9 passed
- Self-verification: all Day 1 items passed

---

## Day 2 — COMPLETE ✅

Commit: 054c967
- `langgraph_engine/executor.py`: AgentExecutor (3 enforcement layers)
- `langgraph_engine/nodes/viper_ba.py`: uses AgentExecutor
- `platform_model/actions.py`: BAAction/SAAction/DEVAction/QAAction enums
- Explicit action enforcement, initiator/role separation confirmed
- E2E: all pass
- Nova soft note: broad exception -> halt path watched (not a blocker)

---

## Day 3 — COMPLETE ✅

Commit: 9a23b73 (docs closure) / 8a9e9e2 (functional)
- evidence_store: EvidenceType.HANDOFF + append_handoff + get_handoffs_for_task
- RuntimeContext: evidence_store field added
- Executor: handoff persisted to evidence store after execution
- _write_event: fixed Event constructor (removed invalid metadata kwarg)
- Handoff protocol: evidence store, journal, schema all working
- E2E: all pass
- Nova notes closed: silent-containment scope documented, V1 storage choice noted

---

## Day 4 — COMPLETE ✅

Commit: 8346e22
- viper_sa_node: AgentExecutor -> SA -> DEV advance
- viper_dev_node: AgentExecutor -> DEV -> QA advance
- viper_qa_node: AgentExecutor -> marks DONE (terminal, no StateMachine advance)
- All nodes: 3 enforcement layers + handoff to evidence + event journal
- E2E: all pass
- Self-verification: all Day 4 items passed

---

## Day 5 — COMPLETE ✅

Commit: 1f1dedc (test alignment fix)
LANGGRAPH_E2E_TEST.py now directly verifies all claims:
- Graph: BA → SA → DEV → QA → DONE (done=terminal)
- TaskState = DONE
- Handoffs: 4 unique transitions, all complete (10 fields)
- agent_executed events: 4 (one per stage actor)
- stage_advanced events: 3 (BA→SA, SA→DEV, DEV→QA)
- Checkpoint: DEV→QA, restore works
- Authority failure propagates (PermissionError, not swallowed)

All 9/9 test steps pass. Test now matches milestone narrative precisely.

---

## Dependencies

- Week 3 COMPLETE (GovernanceState, graph, stage nodes, edges, pipeline compile)
- Viper agent SOUL.md/SCOPE.md (from earlier initialization)
- Best-pick governance specs (approved skills and rules reference)

---

## Risks

- Agent execution may expose gaps in authority model that require Week 2-level fixes
- Handoff artifact minimum may need governance approval (not just technical)
- If agent can bypass pipeline (act without going through stage node), governance breaks
- Scope creep toward PMO UI before foundation is solid
