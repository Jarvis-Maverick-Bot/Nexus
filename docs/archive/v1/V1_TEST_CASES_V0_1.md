# PMO Smart Agent V1 — Formal Test Cases

**Author:** Nova
**Date:** 2026-04-09
**Status:** DRAFT — derived from frozen V1 archive set
**Purpose:** Define the formal V1 test basis before execution and reporting

---

## 1. Test Basis

These test cases are derived from the frozen V1 archive set, especially:
- `V1 SPEC/STEP_6_V1_ACCEPTANCE_CRITERIA_V0_1.md`
- `PMO_SMART_AGENT_V1_PRD_V0_3.md`
- `PMO_V1_WEB_UI_ARCH.md`
- `V1_FINAL_STATUS.md`

This document is the formal test-case layer for V1 archive completion.
It defines what should be tested, why it matters, and what counts as pass/fail.

---

## 2. Test Scope

V1 test scope covers only the frozen V1 product surface and its accepted boundary:

1. **Announce Kickoff**
2. **View Status**
3. **Confirm Gate**
4. **Edge-case behavior in V1 scope**
5. **Shell-boundary behavior**

Not in scope:
- multi-user testing
- reporting expansion
- artifact upload
- readiness checks beyond V1
- future evidence model improvements
- replacement of V1 shortcuts explicitly accepted as non-doctrine

---

## 3. Test Case Index

| ID | Area | Test Case | Type |
|----|------|-----------|------|
| V1-TC-001 | Kickoff | Kickoff with full valid product input | Functional |
| V1-TC-002 | Kickoff | Kickoff with blank assignee defaults to unassigned | Functional |
| V1-TC-003 | Kickoff | Kickoff rejects missing required fields | Validation |
| V1-TC-004 | Status | Status returns current stage/owner/status for valid task | Functional |
| V1-TC-005 | Gate | Gate panel loads for active task | Functional |
| V1-TC-006 | Gate | Approve gate succeeds for pending gate | Functional |
| V1-TC-007 | Gate | Reject gate requires reason | Validation |
| V1-TC-008 | Gate | Double decision is prevented | Edge case |
| V1-TC-009 | Edge | Terminal-state task cannot be gate-confirmed | Edge case |
| V1-TC-010 | Edge | Platform unavailable is rendered distinctly from task not found | Error handling |
| V1-TC-011 | Edge | Failed fetch clears stale panel / no stale success state remains | UI error behavior |
| V1-TC-012 | Boundary | PMO behaves as non-authoritative shell | Boundary |
| V1-TC-013 | End-to-end | Single browser-session path across all 3 V1 functions | Integration |

---

## 4. Detailed Test Cases

### V1-TC-001 — Kickoff with full valid product input
**Requirement basis:** PRD V1 kickoff surface, PMO web UI architecture

**Preconditions**
- PMO Web UI available
- gov_langgraph backend available

**Steps**
1. Open kickoff form
2. Enter valid title
3. Enter valid description
4. Select priority P0-P3 value
5. Enter assignee
6. Enter actor
7. Submit

**Expected result**
- request succeeds
- workitem is created
- returned stage is `INTAKE`
- assignee matches submitted assignee
- no backend-only fields are required in UI

---

### V1-TC-002 — Kickoff with blank assignee defaults to unassigned
**Expected result**
- request succeeds
- created task has assignee/owner = `unassigned`
- stage is still `INTAKE`

---

### V1-TC-003 — Kickoff rejects missing required fields
**Expected result**
- request fails with validation error
- error response is structured enough for frontend rendering
- no misleading success output remains

---

### V1-TC-004 — Status returns current stage/owner/status for valid task
**Expected result**
- status endpoint returns current stage
- current owner is shown
- task status is shown
- no stale/cached fake state is introduced by PMO

---

### V1-TC-005 — Gate panel loads for active task
**Expected result**
- gate panel loads successfully for an eligible task
- `gate_status` is rendered correctly
- panel reflects live gov_langgraph state

---

### V1-TC-006 — Approve gate succeeds for pending gate
**Expected result**
- approve action succeeds once
- gate state becomes approved
- panel updates to already-decided state
- action buttons are no longer available for that decided gate

---

### V1-TC-007 — Reject gate requires reason
**Expected result**
- reject without reason is blocked
- validation is enforced in UI and/or backend
- no silent rejection occurs

---

### V1-TC-008 — Double decision is prevented
**Expected result**
- second approve/reject attempt on an already-decided gate fails
- existing decision is preserved
- no overwrite occurs
- returned error is explicit enough for UI display

---

### V1-TC-009 — Terminal-state task cannot be gate-confirmed
**Expected result**
- gate action is behaviorally blocked for terminal-state tasks
- UI does not expose active confirm controls for terminal-state case
- backend also rejects such actions if called directly

**Note**
Exact terminal vocabulary must match the authoritative current model at execution time.

---

### V1-TC-010 — Platform unavailable is rendered distinctly from task not found
**Expected result**
- platform unavailable produces distinct error classification from task-not-found
- frontend renders them differently enough for operational debugging
- error type and message are not collapsed into one vague state

---

### V1-TC-011 — Failed fetch clears stale panel / no stale success state remains
**Expected result**
- previous good panel is not left visible as if current truth after fetch failure
- failed load/action replaces or clears stale visual success state

---

### V1-TC-012 — PMO behaves as non-authoritative shell
**Expected result**
- PMO stores no independent authoritative business state
- reads are driven by gov_langgraph/tool path
- UI behavior does not imply local source-of-truth ownership

**Verification mode**
- code review / architecture review check
- runtime behavior spot-check

---

### V1-TC-013 — Single browser-session path across all 3 V1 functions
**Expected result**
- within one browser session, operator can exercise kickoff, status, and gate interaction successfully
- this verifies product-surface integration across the 3 V1 functions

**Boundary note**
This does **not** mean PMO itself owns intermediate workflow advancement. Any required pipeline progression remains gov_langgraph responsibility.

---

## 5. Pass Criteria

V1 test execution passes when:
- all critical in-scope test cases pass
- no failure contradicts frozen V1 scope or accepted boundary
- any accepted V1 shortcuts remain explicitly recorded as standing notes, not hidden defects

---

## 6. Standing Notes (Not Automatic Failures)

These are accepted V1 limitations/shortcuts and should be recorded in the test report, not treated as surprise discoveries:

1. `DEFAULT_PROJECT_ID = "pmo-kickoff"`
   - accepted V1 shortcut
   - not long-term doctrine

2. `Evidence pending` tied to gate decision-note emptiness
   - accepted V1 simplification
   - not long-term evidence model

---

## 7. Next Document

After execution, results should be written into:
- `V1_TEST_REPORT_V0_1.md`

That report should record:
- executor
- environment
- date/time
- pass/fail per test case
- issues found
- final UAT/review conclusion
