# STEP_2_V1_MINIMAL_OBJECT_MODEL_V0_1

**Step:** 2
**Version:** V0_1
**Status:** Draft for discussion with Jarvis
**Purpose:** Freeze Step 2 of the implementation-ready framework: V1 minimal object model.

---

## Overview

V1 should include these 7 first-class objects:

1. Project
2. Work Item / Task
3. Workflow
4. Task State
5. Handoff
6. Gate
7. Event

These objects are intended to be the minimum governed model required to support planned, visible, and controllable software-delivery execution in V1.

---

## 1. Project

### Definition
Project is the top-level governed delivery container for a software-delivery goal.
It contains work items and anchors workflow context, status visibility, and PMO tracking.

### V1 minimum fields
- `project_id`
- `project_name`
- `project_goal`
- `domain_type`
- `workflow_template_id`
- `project_status`
- `created_at`
- `project_summary`
- `project_owner`

---

## 2. Work Item / Task

### Definition
Work Item / Task is the minimum governed delivery unit that the platform assigns, tracks, progresses, hands off, and audits.

### V1 minimum fields
- `task_id`
- `project_id`
- `task_title`
- `task_description`
- `current_owner`
- `dependency_task_ids`
- `expected_deliverable`
- `workflow_id`
- `current_stage`
- `task_status`
- `handoff_target`
- `priority`

### Notes
- V1 keeps Work Item / Task as one merged object.
- V1 does not split broader “work” vs smaller “task” into separate objects yet.
- `dependency_task_ids` is preferred over vague dependency wording or simple sequence numbers.

---

## 3. Workflow

### Definition
Workflow is the defined, reusable, and extensible delivery path that governs how a work item progresses through software delivery stages.

### V1 minimum fields
- `workflow_id`
- `workflow_name`
- `domain_type`
- `stage_list`
- `allowed_transitions`
- `stage_role_map`
- `default_handoff_points`
- `default_gate_points`

### Notes
- Workflow must be represented as a platform object, not as an invisible hardcoded path.
- `stage_role_map` is required in V1.
- `workflow_status` is intentionally not included in V1 at this stage.

---

## 4. Task State

### Definition
Task State is the current actionable operational condition of a Work Item / Task, separate from the task definition itself.

### V1 minimum fields
- `task_id`
- `current_stage`
- `state_status`
- `current_owner`
- `current_blocker`
- `next_expected_action`
- `last_updated_at`

### Notes
- V1 explicitly separates task definition from task state.
- This preserves the distinction between what a task is and what situation it is currently in.

---

## 5. Handoff

### Definition
Handoff is the explicit governed transfer record of a task from one stage/owner to another, with a concrete deliverable reference.

### V1 minimum fields
- `handoff_id`
- `task_id`
- `from_stage`
- `to_stage`
- `from_owner`
- `to_owner`
- `deliverable_reference`
- `handoff_note`
- `handoff_status`
- `created_at`

### Notes
- Handoff is task/work-item based in V1, not project-based.
- `deliverable_reference` and `to_owner` are explicitly required.
- Handoff is treated as a real governed object, not just an implied message.

---

## 6. Gate

### Definition
Gate is the formal decision/control object that determines whether a task may proceed, return, hold, or stop at a workflow boundary.

### V1 minimum fields
- `gate_id`
- `task_id`
- `stage`
- `gate_type`
- `decision`
- `decision_by`
- `decision_note`
- `decided_at`

### Confirmed V1 decision values
- `approved`
- `rejected`
- `held`
- `stopped`
- `returned`

### Notes
- Handoff = formal submission / transfer
- Gate = formal decision / control

---

## 7. Event

### Definition
Event is the traceable governance-relevant record of meaningful action, change, or condition in project delivery.

### V1 minimum fields
- `event_id`
- `project_id`
- `task_id`
- `event_type`
- `actor`
- `event_summary`
- `related_stage`
- `timestamp`

### Notes
- `project_id` is required.
- `task_id` remains in the model, but may be empty for project-level events.
- Event should be treated as a required first-class governed record, but V1 should not over-engineer event infrastructure.

---

## Quick Review Conclusion

This 7-object set is considered valid for V1 because it is:
- small enough to stay implementable
- complete enough to support planned / visible / controllable delivery
- abstract enough to avoid hardcoding only one narrow demo path

### Intentional simplifications in V1
The following are not included as first-class objects in Step 2 for V1:
- Skill
- Agent
- Team
- Authority as a full object
- Deliverable as a full object
- Exception as a full object

These remain important, but are intentionally deferred to keep V1 lean and implementation-ready.
