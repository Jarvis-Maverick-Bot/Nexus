# STEP_2_V1_5_MINIMAL_OBJECT_MODEL_V0_1

**Step:** 2
**Version:** V0_1
**Status:** Draft for discussion with Jarvis
**Purpose:** Freeze Step 2 of the implementation-ready framework: V1.5 minimal object model.

---

## Overview

V1.5 should retain the V1 object foundation while expanding the model where project-centric PMO operation requires it.

V1.5 first-class objects:

1. Project
2. Work Item / Task
3. Workflow
4. Task State
5. Handoff
6. Gate
7. Event
8. Kickoff Readiness
9. Report
10. Acceptance Record

---

## 1. Project

Project becomes an active first-class PMO object in V1.5, not only an implicit fixed container. V1.5 assumes true multi-project operation rather than a hidden single-project wrapper.

### V1.5 minimum fields
- `project_id`
- `project_name`
- `project_goal`
- `domain_type`
- `workflow_template_id`
- `project_status`
- `created_at`
- `project_summary`
- `project_owner`
- `kickoff_readiness_status`

---

## 2. Work Item / Task

Task remains the minimum governed delivery unit, now explicitly linked to active project lifecycle rather than a hidden single-project assumption.

### V1.5 minimum fields
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

---

## 3. Workflow

Workflow remains the reusable delivery path object.

### V1.5 minimum fields
- `workflow_id`
- `workflow_name`
- `domain_type`
- `stage_list`
- `allowed_transitions`
- `stage_role_map`
- `default_handoff_points`
- `default_gate_points`
- `acceptance_points`

---

## 4. Task State

Task State remains separate from task definition.

### V1.5 minimum fields
- `task_id`
- `current_stage`
- `state_status`
- `current_owner`
- `current_blocker`
- `next_expected_action`
- `last_updated_at`

---

## 5. Handoff

Handoff remains the explicit governed transfer object.

### V1.5 minimum fields
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

---

## 6. Gate

Gate remains the formal control object.

### V1.5 minimum fields
- `gate_id`
- `task_id`
- `stage`
- `gate_type`
- `decision`
- `decision_by`
- `decision_note`
- `decided_at`

### Confirmed V1.5 decision values
- `approved`
- `rejected`
- `held`
- `stopped`
- `returned`

---

## 7. Event

Event remains the traceable governance-relevant action record.

### V1.5 minimum fields
- `event_id`
- `project_id`
- `task_id`
- `event_type`
- `actor`
- `event_summary`
- `related_stage`
- `timestamp`

---

## 8. Kickoff Readiness

Kickoff Readiness is a new first-class object in V1.5.
It represents whether the project/task start conditions are sufficiently complete to allow governed activation.

### V1.5 minimum fields
- `readiness_id`
- `project_id`
- `scope_ready`
- `spec_ready`
- `plan_ready`
- `test_basis_ready`
- `risks_noted`
- `checked_by`
- `readiness_status`
- `checked_at`

---

## 9. Report

Report is a new first-class PMO-facing object in V1.5 for structured project visibility.

### V1.5 minimum fields
- `report_id`
- `project_id`
- `report_type`
- `scope_reference`
- `spec_reference`
- `architecture_reference`
- `testcase_reference`
- `testreport_reference`
- `guideline_reference`
- `generated_by`
- `generated_at`

---

## 10. Acceptance Record

Acceptance Record is a new first-class object for expanded acceptance workflow.

### V1.5 minimum fields
- `acceptance_id`
- `project_id`
- `task_id`
- `scope_reference`
- `spec_reference`
- `architecture_reference`
- `testcase_reference`
- `testreport_reference`
- `guideline_reference`
- `review_status`
- `final_decision`
- `decision_by`
- `decision_note`
- `decided_at`

---

## Quick Review Conclusion

V1.5 keeps the V1 governed core and adds only the minimum new objects needed for project initiation realism, readiness gating, reporting, and expanded acceptance workflow.
