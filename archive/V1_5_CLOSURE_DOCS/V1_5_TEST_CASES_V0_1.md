# V1_5_TEST_CASES_V0_1

## Document Control
- Version: V0.1
- Status: Working draft
- Scope: PMO Smart Agent V1.5 final-phase UAT and closure support
- Related branch: `v1.5`
- Related repo: `gov_langgraph`

## Purpose
This document defines the formal test cases for PMO Smart Agent V1.5 final validation.

It is intended to support:
- live UAT execution
- final acceptance review
- completion of `V1_5_TEST_REPORT`
- evidence-backed V1.5 closure

## Test Scope
V1.5 validation focuses on the corrected V1.5 model already accepted during Sprint reviews:
- multi-project support from the start
- human-governed kickoff/intake control
- PMO status aggregation
- artifact completeness tracking
- acceptance package workflow
- advisory and blocker surfacing
- bounded Maverick coordination role

Out of scope for V1.5 final acceptance unless they break claimed behavior:
- direct PMO-managed transport hardening
- generalized middleware/message-bus architecture
- V2.0 coordination infrastructure
- persistent-session architecture as a correctness prerequisite

## Required Test Artifacts
The following six artifacts must be present for the selected V1.5 test project before final acceptance is granted:
1. Scope
2. SPEC
3. Arch
4. Test Case
5. Test Report
6. GuideLine

## Test Environment
- Runtime surface: live V1.5 PMO deployment
- Authority model: Alex/Jarvis assign, Maverick coordinates, PMO Web UI aggregates, humans decide at intake/gates
- Primary evidence surfaces:
  - PMO Web UI
  - live API behavior if needed
  - repository code at accepted V1.5 branch state
  - generated project artifacts and acceptance state

## Formal Test Cases

### TC-01 Project creation
**Objective**
Verify that a new V1.5 project can be created as a distinct governed delivery container.

**Preconditions**
- PMO Web UI is reachable
- no blocking platform outage

**Steps**
1. Create a new project with project name, goal, and owner.
2. Open the created project detail view.
3. Confirm the project appears in project listing.

**Expected Result**
- Project is created successfully
- Project has its own `project_id`
- Project detail can be retrieved
- Project is visible in project list without corrupting other projects

### TC-02 Multi-project isolation
**Objective**
Verify that multiple projects can coexist without namespace or state collision.

**Preconditions**
- At least two projects exist

**Steps**
1. Open Project A.
2. Open Project B.
3. Compare task list, artifact status, and acceptance state across both projects.

**Expected Result**
- Project A and Project B remain distinct
- Tasks are not cross-mixed
- Artifact completeness is evaluated per project
- Acceptance status is per-project, not shared globally

### TC-03 Kickoff and intake path
**Objective**
Verify that kickoff works under the corrected human-governed V1.5 model.

**Preconditions**
- Test project exists
- required scope/context for kickoff is available

**Steps**
1. Trigger kickoff for the test project.
2. Verify task creation.
3. Check current stage/state after kickoff.

**Expected Result**
- Kickoff succeeds
- Work item is created under the correct project
- Initial stage/state matches the implemented V1.5 workflow
- No autonomous readiness-engine behavior is required beyond the human-governed path

### TC-04 Stage progression through governed flow
**Objective**
Verify that the reference delivery path can progress cleanly through the implemented stages.

**Preconditions**
- A kicked-off task exists

**Steps**
1. Advance the task through the implemented handoff path.
2. Observe task state and current stage after each step.
3. Confirm final completion state is reachable.

**Expected Result**
- Stage progression is valid and consistent
- State transitions are reflected correctly
- Final completion state is reachable without contradictory status

### TC-05 PMO status visibility
**Objective**
Verify that PMO surfaces the current project/task state correctly.

**Preconditions**
- Test project and task exist

**Steps**
1. Open PMO status/project detail view.
2. Check displayed project status, task status, current stage, and owner context.

**Expected Result**
- PMO Web UI presents aggregated current state correctly
- Displayed status matches backend state/tool output

### TC-06 Artifact completeness tracking
**Objective**
Verify that V1.5 tracks required artifacts and missing-artifact state correctly.

**Preconditions**
- Test project exists

**Steps**
1. Add/update artifacts incrementally.
2. Observe completeness state before all six are present.
3. Complete the full artifact set.

**Expected Result**
- Missing artifacts are shown accurately while incomplete
- Completeness becomes true only when all six required artifacts are present
- Artifact status is project-scoped

### TC-07 Acceptance package creation
**Objective**
Verify that an acceptance package can be created for the project/task using the recorded artifacts.

**Preconditions**
- Required artifacts are present

**Steps**
1. Create acceptance package.
2. Inspect package completeness and missing-artifact output.

**Expected Result**
- Acceptance package is created successfully
- Package reflects current artifact completeness truthfully
- No false “complete” status appears when required artifacts are missing

### TC-08 Acceptance approval path
**Objective**
Verify the positive final-acceptance path.

**Preconditions**
- Acceptance package exists and is complete

**Steps**
1. Approve the acceptance package.
2. Re-open acceptance details.

**Expected Result**
- Approval is recorded successfully
- Decision actor, decision state, and optional note are retained
- Final state remains consistent after approval

### TC-09 Acceptance rejection path
**Objective**
Verify the rejection/revision-request path.

**Preconditions**
- Acceptance package exists

**Steps**
1. Reject the acceptance package with a reason.
2. Reload acceptance details.

**Expected Result**
- Rejection is recorded successfully
- Rejection reason is preserved
- Rejection is visible through the correct acceptance-package surface

### TC-10 Advisory surfacing
**Objective**
Verify that advisory signals are visible as informational PMO signals, not hidden governance decisions.

**Preconditions**
- Test project exists

**Steps**
1. Raise one or more advisories.
2. Inspect advisory list/order.
3. Acknowledge an advisory.

**Expected Result**
- Advisories appear in a stable newest-first order
- Advisory metadata is visible
- Acknowledgement/dismiss works correctly
- Advisories do not silently alter governance authority

### TC-11 Blocker surfacing and resolution
**Objective**
Verify blocker detection, severity display, age tracking, and resolution flow.

**Preconditions**
- Test project/task exists

**Steps**
1. Raise a blocker for a task.
2. Inspect blocker severity and age information.
3. Resolve the blocker.
4. Recheck active blocker list.

**Expected Result**
- Blocker is recorded against the correct task/project
- Severity is shown correctly
- Age tracking is visible
- Resolution removes it from active-blocker state
- Auto-generated blocker advisory is also visible where applicable

### TC-12 Error handling surfaces
**Objective**
Verify that normal error cases return bounded, typed behavior rather than misleading server-failure semantics.

**Preconditions**
- PMO backend reachable

**Steps**
1. Request a nonexistent project.
2. Request a nonexistent task where relevant.
3. Trigger a validation error path.

**Expected Result**
- Missing project returns project-not-found behavior
- Missing task returns task-not-found behavior
- Validation errors return typed validation behavior
- UI/API behavior is consistent with the implemented error map

## Acceptance Use Rule
Passing these test cases supports V1.5 final acceptance review, but does not replace Nova’s final integrated judgment.

Final V1.5 acceptance still requires:
- code state verified
- architecture/boundary still acceptable
- required artifacts present
- test report completed truthfully
- final status document completed truthfully
- Alex final decision
