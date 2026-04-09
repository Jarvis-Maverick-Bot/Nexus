# STEP_6_V1_ACCEPTANCE_CRITERIA_V0_1

**Step:** 6
**Version:** V0_1
**Status:** Draft for discussion with Jarvis
**Purpose:** Freeze Step 6 of the implementation-ready framework: V1 acceptance criteria.

---

## 1. Acceptance structure

V1 acceptance should be evaluated through five layers:

1. **object-by-object proof criteria**
2. **end-to-end happy-path proof**
3. **end-to-end failure-path proof**
4. **artifact proof**
5. **PMO_SMART_AGENT proof**

This structure is intended to ensure that V1 is not only architecturally correct, but also operationally useful, testable, and reviewable.

---

## 2. Object-by-object proof criteria

### 2.1 Project proof
V1 is acceptable only if all of the following can be demonstrated:
- a project can be created as a governed object
- project goal, summary, owner, and workflow context can be recorded
- project status can be updated and queried
- PMO_SMART_AGENT can display project-level summary and status

### 2.2 Work Item / Task proof
V1 is acceptable only if all of the following can be demonstrated:
- a task can be created under a project
- the task stores owner, description, dependency_task_ids, expected_deliverable, workflow/stage context, and priority
- the task can be updated without losing identity or project linkage
- PMO_SMART_AGENT can display task-level key fields

### 2.3 Workflow proof
V1 is acceptable only if all of the following can be demonstrated:
- a reusable software delivery workflow object exists
- the workflow includes defined stages, allowed transitions, stage_role_map, handoff points, and gate points
- tasks can reference the workflow object
- workflow logic is not implemented only as invisible hardcoded branching

### 2.4 Task State proof
V1 is acceptable only if all of the following can be demonstrated:
- task state exists separately from task definition
- current stage, state_status, current owner, blocker, and next expected action can be stored and updated
- task state changes do not overwrite the underlying task definition
- PMO_SMART_AGENT can display task definition and task state as distinct information

### 2.5 Handoff proof
V1 is acceptable only if all of the following can be demonstrated:
- a task can submit an explicit handoff record from one stage/owner to another
- handoff contains from_stage, to_stage, from_owner, to_owner, deliverable_reference, and status
- cross-stage movement is not treated as valid unless handoff behavior is explicitly recorded
- PMO_SMART_AGENT can display pending and completed handoffs

### 2.6 Gate proof
V1 is acceptable only if all of the following can be demonstrated:
- gate exists as an explicit control record bound to a task/stage
- gate decisions support: approved, rejected, held, stopped, returned
- a task cannot be treated as validly progressed through controlled boundaries without gate behavior
- PMO_SMART_AGENT can display pending or completed gate decisions

### 2.7 Event proof
V1 is acceptable only if all of the following can be demonstrated:
- meaningful actions and changes produce event records
- project/task event history can be queried
- event records include actor, event type, summary, stage context, and timestamp
- visibility does not depend only on narrative summaries or ad hoc memory

### 2.8 Authority proof
V1 is acceptable only if all of the following can be demonstrated:
- Management Layer and Delivery Layer are distinguishable in action eligibility
- delivery roles cannot freely perform management/gate actions by default
- handoff/gate/state mutation authority follows the V1 authority rules
- Maverick exists logically in the Management Layer model even if runtime participation is not required yet

---

## 3. End-to-end happy-path proof

V1 is acceptable only if one canonical software-delivery scenario can be demonstrated end-to-end as a governed flow.

### Canonical scenario
- a project is created
- a task is created under the project
- the standard software-delivery workflow is assigned
- the task progresses through BA → SA → DEV → QA
- each stage change is accompanied by explicit handoff and explicit gate behavior where required
- task state is updated throughout the flow
- events are recorded throughout the flow
- PMO_SMART_AGENT can observe the flow throughout the process

### Happy-path proof conditions
The demonstration must show that:
- the task starts in a defined initial state
- BA can complete its governed output and submit handoff
- SA can receive, work, and submit onward handoff
- DEV can receive, work, and submit onward handoff
- QA can receive, review, and make gate-controlled decisions
- the final completion state is visible in PMO_SMART_AGENT
- event history makes the entire path reconstructable

---

## 4. End-to-end failure-path proof

V1 is not acceptable if it proves only the happy path.
It must also prove that governed interruption paths work.

### Failure-path proof conditions
V1 must demonstrate at least the following:

#### 4.1 Return path
- a gate decision can return a task for revision
- the returned status is visible
- the affected stage/task state is updated correctly
- PMO_SMART_AGENT can display the returned condition and next expected action

#### 4.2 Hold path
- a task can be placed on hold
- the hold condition is visible in task state
- PMO_SMART_AGENT can show that the task is paused and not progressing

#### 4.3 Stop path
- a task can be stopped through governed control
- the stopped condition is visible and traceable
- the stop decision appears in event history

#### 4.4 Blocker path
- a blocker can be explicitly recorded
- the blocker becomes visible in task state
- the blocker can later be resolved
- PMO_SMART_AGENT can display blocker visibility before and after resolution

#### 4.5 Rejection path
- a gate decision can reject progression
- rejection reason/note is captured
- rejection remains visible to PMO/operator review

These proof points ensure V1 supports control, not just forward movement.

---

## 5. Artifact proof

V1 is acceptable only if the framework can support meaningful real delivery artifacts.

### Minimum artifact proof
The system must be able to support and surface artifacts such as:
- user stories
- test cases
- test plan
- reviewable delivery output
- auditable review/UAT support material

### Role relevance proof
The acceptance proof should demonstrate that:
- Viper-BA can use the framework to produce user-story-like or requirement-shaping artifacts
- QA can use the framework to produce test-plan / test-case-like artifacts
- those artifacts can be reviewed and surfaced through the governed process

### Governance usefulness proof
The same artifacts should also be usable for:
- code review support
- artifact audit support
- user acceptance test support

This ensures V1 is useful for real delivery governance, not only object/state bookkeeping.

---

## 6. PMO_SMART_AGENT proof

V1 is acceptable only if PMO_SMART_AGENT can function as the first meaningful operator-facing surface.

### PMO_SMART_AGENT must be able to:
- display current project status
- display current task status
- display current owner, blocker, and next expected action
- display pending handoffs and gate decisions
- display recent governance-relevant events
- initiate management/control actions through Platform Core
- present suggestion / analysis support to the human operator

### PMO_SMART_AGENT must not:
- become the independent system of record
- replace Platform Core governance logic
- remove human final review and decision authority

### Human authority proof
V1 is acceptable only if a human operator can:
- inspect the visible process state
- inspect events / blockers / pending items
- review recommendations or analysis
- make the final decision, including choosing differently from the system recommendation

---

## 7. Practical completion standard

V1 should be considered complete only if Jarvis can demonstrate:
- the governed objects work individually
- the canonical software-delivery path works end-to-end
- failure/control paths also work, not only the happy path
- real artifacts can be produced and used for governance/review/UAT purposes
- PMO_SMART_AGENT can act as the first real management/control surface without becoming the system of record

---

## 8. One-line frozen definition

**V1 acceptance requires object-level proof, happy-path proof, failure-path proof, artifact proof, and PMO_SMART_AGENT proof, such that the first software-delivery implementation is not only structurally correct but operationally usable, reviewable, and governable.**
