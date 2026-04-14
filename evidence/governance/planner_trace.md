# Planner Instantiation Trace — M4-R1 (Real Task Redo)

**Date:** 2026-04-14 16:14 GMT+8
**Status:** REVISION — using real task against actual V1.8 codebase
**Purpose:** Address Nova's blocking issue — prior trace used detached example instead of real integrated handoff

---

## Task Selection Rationale

**User story:** "As a player, I want the ESCAPED message to include my tier, so I immediately know how well I played."

**Why this task:**
- Real gap: `compute_tier` exists but is never called in the escape path
- Real codebase: `games/grid_escape/engine.py` + `games/grid_escape/scoring.py`
- The ESCAPED message currently reads: `ESCAPED|<steps>|<grid>|<timestamp>` — no tier
- This is bounded, meaningful, and actually improves the product

---

## Planner Output (16:14 GMT+8)

```json
{
  "task_plan": [
    {
      "task_id": "TASK-001",
      "description": "Update the ESCAPED message format in engine.py to include a tier field as the sixth field. Change format from 'ESCAPED|<steps>|<grid>|<timestamp>' to 'ESCAPED|<steps>|<grid>|<timestamp>|<tier>'.",
      "acceptance_criteria": [
        "The ESCAPED message format string is updated to include a sixth field for tier",
        "All call sites that parse or construct the ESCAPED message are updated to handle the new field"
      ],
      "estimated_complexity": "LOW"
    },
    {
      "task_id": "TASK-002",
      "description": "Wire compute_tier into the escape path in engine.py. When the player reaches EXIT, call scoring.compute_tier(grid_id, steps) and insert the returned tier string as the sixth field in the ESCAPED message.",
      "acceptance_criteria": [
        "compute_tier is called exactly once in the escape code path",
        "The tier returned by compute_tier is inserted as the sixth field in the ESCAPED message"
      ],
      "estimated_complexity": "LOW"
    },
    {
      "task_id": "TASK-003",
      "description": "Add end-to-end integration test(s) to verify ESCAPED message now contains a valid tier. Test at least two grids confirming tier field is present and dynamic (not hardcoded).",
      "acceptance_criteria": [
        "A test exercises the escape path end-to-end and asserts ESCAPED message contains a non-empty tier string",
        "At least two distinct tiers are exercised to confirm the field is dynamic"
      ],
      "estimated_complexity": "MEDIUM"
    }
  ],
  "decomposition_notes": "TASK-001 and TASK-002 are tightly coupled — format change + tier wiring. TASK-003 is separate because testing the escape path requires test fixtures. The work touches exactly two files: engine.py and a test file. Minimal, self-contained change.",
  "recommended_order": ["TASK-001", "TASK-002", "TASK-003"]
}
```

---

## Verification

- [x] User story in -> task plan out
- [x] 3 tasks with unique task_ids (TASK-001, TASK-002, TASK-003)
- [x] Each task has at least 2 acceptance criteria
- [x] recommended_order covers all 3 task_ids
- [x] Planner did not write code — only decomposed
- [x] Task is REAL — targets actual missing feature in `games/grid_escape/engine.py`
- [x] Input/output contract matches skill spec

**Status:** PLANNER SEAT RE-VERIFIED (real task)

Seat labeled `instantiated` in: `V1_8_AGENT_ROLES.md`