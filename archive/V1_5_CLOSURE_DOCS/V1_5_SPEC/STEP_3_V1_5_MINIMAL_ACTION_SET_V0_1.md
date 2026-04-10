# STEP_3_V1_5_MINIMAL_ACTION_SET_V0_1

**Step:** 3
**Version:** V0_1
**Status:** Draft for discussion with Jarvis
**Purpose:** Freeze Step 3 of the implementation-ready framework: V1.5 minimal action set.

---

## Overview

V1.5 extends the V1 action set in order to support project initiation, kickoff readiness, reporting, and expanded acceptance behavior.

Action categories:
1. Management / mutation actions
2. Gate / approval actions
3. Query / reporting actions
4. Acceptance actions

---

## 1. Management / Mutation Actions

### V1.5 action list
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
- `run_kickoff_readiness_check`

---

## 2. Gate / Approval Actions

### V1.5 action list
- `approve`
- `reject`
- `hold`
- `stop`
- `return`

---

## 3. Query / Reporting Actions

### V1.5 action list
- `get_project_status`
- `get_task_status`
- `get_task_owner`
- `get_task_blocker`
- `get_pending_handoffs`
- `get_pending_gates`
- `get_recent_events`
- `get_tasks_by_stage`
- `get_tasks_by_owner`
- `get_project_report`
- `get_project_scope`
- `get_project_spec`
- `get_project_architecture`
- `get_project_testcases`
- `get_project_testreport`
- `get_project_guideline`
- `get_acceptance_status`
- `get_readiness_status`
- `spawn_delivery_agent`
- `get_agent_execution_status`

---

## 4. Acceptance Actions

### V1.5 action list
- `submit_acceptance_package`
- `review_acceptance_package`
- `approve_acceptance`
- `reject_acceptance`

---

## Quick Review Conclusion

V1.5 action expansion is intentionally limited to what is required for multi-project PMO operation, readiness checks, reporting, acceptance workflow, and Maverick-led agent spawning through OpenClaw integration. Advisory actions should remain separate from authoritative mutation actions.
