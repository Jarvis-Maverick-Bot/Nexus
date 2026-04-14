# V1.8 Agent Roles - Claw Studio Seat Definitions

**Version:** 1.0
**Date:** 2026-04-14
**Status:** IN PROGRESS — M4-R1 course correction (Planner + TDD now persistent OpenClaw agents, not one-shot sub-agents)
**Game:** Grid Escape

---

## Overview

Claw Studio agents are role-shaped sub-agents that accept structured inputs and produce structured outputs. Each seat has an input contract, an output contract, and a defined boundary. V1.8 instantiates two seats: **Planner** and **TDD**. The remaining five role stubs (Architect, CodeReviewer, Security, Docs, DBExpert) are documented as V1.9 targets.

**M3 framing (carry-forward):** These are bounded V1.8 proof surfaces. Not production-grade runtime agents.

---

## V1.8 Instantiated Seats

### Planner

**Status:** `approved` (2026-04-14T16:30 GMT+8); **persistent OpenClaw agent** (corrected 2026-04-14T19:38 GMT+8)
**Agent workspace:** `C:\Users\John\.openclaw\agents\planner`
**Function coverage:** F7.1.1-F7.1.3, F7.4.1

**Role:** Accepts a user story or work item description, decomposes it into a task plan with acceptance criteria per task. Feeds the TDD seat.

**Input contract:**
- `input`: free-form user story or work item description (string)
- `context`: optional context dict (may be empty)

**Output contract:**
- `task_plan`: list of `{task_id, description, acceptance_criteria}` objects
- `decomposition_notes`: string - rationale for how work was split

**Skill spec:** `agent_seats/planner/skill.md`

**Instantiation trace:** `evidence/governance/planner_trace.md`

---

### TDD (Test-Driven Development)

**Status:** `approved` (2026-04-14T16:30 GMT+8); **persistent OpenClaw agent** (corrected 2026-04-14T19:38 GMT+8)
**Agent workspace:** `C:\Users\John\.openclaw\agents\tdd`
**Function coverage:** F7.1.1-F7.1.3, F7.4.2

**Role:** Receives a task specification from Planner, produces a failing test first, then minimal passing implementation. Proven cycle: failing test appears before passing code.

**Input contract:**
- `task_spec`: task description string from Planner output
- `acceptance_criteria`: list of criteria from Planner

**Output contract:**
- `failing_test`: code string - test that fails against current implementation
- `passing_code`: code string - minimal implementation that makes test pass
- `test_results`: `{passed: bool, output: string}`

**Skill spec:** `agent_seats/tdd/skill.md`

**Instantiation trace:** `evidence/governance/tdd_trace.md`

---

## V1.9 Role Stubs (Pre-Sprint Artifacts - NOT Instantiated)

The following roles are documented here as target specifications for V1.9. They are NOT part of V1.8 sprint work.

| Role | Function | Status |
|------|----------|--------|
| Architect | F7.4.3 | stub - targeting V1.9 |
| CodeReviewer | F7.4.3 | stub - targeting V1.9 |
| Security | F7.4.3 | stub - targeting V1.9 |
| Docs | F7.4.3 | stub - targeting V1.9 |
| DBExpert | F7.4.3 | stub - targeting V1.9 |

Each stub documents: input contract, output contract, role boundary. Skill specs to be defined in V1.9.

---

## Handoff Chain (V1.8 Proof)

```
User story / Work Item
  -> Planner: task plan with acceptance criteria
    -> TDD: failing test first, then passing code
      -> Code artifact (validated)
```

**Handoff trace:** `evidence/governance/handoff_chain_trace.md`

---

## Governance

- All instantiated seats require Nova sign-off before claiming `approved` status
- Sign-off recorded in: `evidence/governance/seat_approval_signoffs.md`
- Uninstantiated stubs must not be claimed as live or approved