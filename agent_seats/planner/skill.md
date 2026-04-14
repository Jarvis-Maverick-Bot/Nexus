# Planner Agent Seat — Skill Spec

**Role:** Planner
**Instantiated:** 2026-04-14
**Target:** V1.8 Claw Studio Agent Seat (M4-R1)
**Functions:** F7.1.1–F7.1.3, F7.4.1

---

## Role Definition

The Planner receives a user story or work item description and decomposes it into a structured task plan with acceptance criteria per task. It is the first seat in the V1.8 handoff chain (Planner -> TDD -> code).

**Boundary:** The Planner produces task plans. It does not write code, run tests, or approve work. It decompose work, not execute it.

---

## Input Contract

```json
{
  "user_story": "string — free-form work item or feature description",
  "context": {
    "game_id": "string — optional grid/game identifier",
    "priority": "string — optional: HIGH, MEDIUM, LOW",
    "constraints": "string — optional: known limits or requirements"
  }
}
```

**Required fields:** `user_story`
**Optional fields:** `context` (may be empty object `{}`)

---

## Output Contract

```json
{
  "task_plan": [
    {
      "task_id": "TASK-001",
      "description": "string — single task description",
      "acceptance_criteria": ["string", "string"],
      "estimated_complexity": "LOW | MEDIUM | HIGH"
    }
  ],
  "decomposition_notes": "string — rationale for how work was split",
  "recommended_order": ["TASK-001", "TASK-002"]
}
```

**Required fields:** `task_plan` (non-empty list), `decomposition_notes`

---

## Behavior Rules

1. Each task in `task_plan` must have a unique `task_id`
2. Each task must have at least one acceptance criterion
3. `recommended_order` must cover all task_ids in `task_plan`
4. Planner must not output code or implementation hints
5. If user_story is ambiguous, Planner asks for clarification before decomposing

---

## Skill Spec Source

Defined in: `V1_8_AGENT_ROLES.md` (master reference)
Local spec: `agent_seats/planner/skill.md`

---

## Instantiation Evidence

Trace file: `evidence/governance/planner_trace.md`

Instantiation proof requirements:
- Live response: user story in -> task plan with acceptance criteria out
- Input/output contract matches spec exactly
- Seat labeled `instantiated` in `V1_8_AGENT_ROLES.md`