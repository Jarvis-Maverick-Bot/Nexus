# STEP_3_V1_MINIMAL_ACTION_SET_V0_1

**Step:** 3
**Version:** V0_1
**Status:** Draft for discussion with Jarvis
**Purpose:** Freeze Step 3 of the implementation-ready framework: V1 minimal action set.

---

## Overview

If Step 2 defines what the platform manages, Step 3 defines what the platform can minimally do in V1.

The V1 action set is intentionally small and practical. It is designed to support planned, visible, and controllable delivery without expanding into a full command universe or overbuilt orchestration grammar.

Step 3 includes three action categories:

1. Management / mutation actions
2. Gate / approval actions
3. Query actions

---

## 1. Management / Mutation Actions

These actions create or change governed objects.

### V1 action list
- `create_project`
- `update_project`
- `create_task`
- `update_task`
- `assign_owner`
- `update_task_state`
- `submit_handoff`
- `record_blocker`
- `resolve_blocker`
- `close_task`
- `close_project`

### Notes
- These actions exist to serve governed delivery, not to mimic generic CRUD for its own sake.
- `update_project` and `update_task` are intentionally broad in V0_1, but may later need tighter field-level guardrails.
- `update_task_state` is especially important and will later need explicit authority constraints.

---

## 2. Gate / Approval Actions

These are the formal control actions available at governed decision points.

### V1 action list
- `approve`
- `reject`
- `hold`
- `stop`
- `return`

### Notes
- These actions align directly with the Gate decision values already frozen in Step 2.
- Step 3 does not reopen or expand the Gate decision model.

---

## 3. Query Actions

These actions retrieve current governed truth for visibility, control, and PMO operations.

### V1 action list
- `get_project_status`
- `get_task_status`
- `get_task_owner`
- `get_task_blocker`
- `get_pending_handoffs`
- `get_pending_gates`
- `get_recent_events`
- `get_tasks_by_stage`
- `get_tasks_by_owner`

### Notes
- Query actions are essential because planned, visible, and controllable delivery requires structured visibility.
- These actions should support dialogue, API, and future PMO_SMART_AGENT control surfaces.

---

## Quick Review Conclusion

This V1 action set is considered suitable for the Management layer because it is:
- explicit enough to constrain implementation direction
- small enough to stay practical
- directly aligned with the V1 object model
- suitable for dialogue, API, and PMO_SMART_AGENT-based operation
