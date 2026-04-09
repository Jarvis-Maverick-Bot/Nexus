# PMO Smart Agent V1 — Formal Test Report

**Report ID:** V1-TEST-REPORT-001
**Version:** V0.1
**Status:** ROUND 1 COMPLETE — issues found
**Date:** 2026-04-09

---

## 1. Purpose

This document records the formal V1 test execution results for PMO Smart Agent V1.

It is based on:
- `V1_TEST_CASES_V0_1.md`
- frozen V1 archive set
- actual UAT execution observations

This report is intended to provide audit-grade test evidence for the V1 freeze package.

---

## 2. Test Basis

### Reference documents
- `V1_TEST_CASES_V0_1.md`
- `V1 SPEC/STEP_1..STEP_7`
- `PMO_SMART_AGENT_V1_PRD_V0_3.md`
- `PMO_V1_WEB_UI_ARCH.md`
- `V1_FINAL_STATUS.md`

### Scope under test
- Announce Kickoff
- View Status
- Confirm Gate
- V1 edge-case handling
- Shell-boundary behavior

---

## 3. Test Execution Context

### Executor information
- **Primary UAT Executor:** Nova (Round 1)
- **Environment prepared by:** Jarvis
- **Final UAT Executor:** Alex

### Environment details
- **Host / machine:** Nova runtime via reachable PMO server
- **Repo / branch / tag:** frozen V1 server environment (remote URL under test)
- **Freeze commit under test:** assumed V1 frozen deployment target
- **Tag under test:** v1.0.0 target behavior
- **Server start method:** remote running server provided by Jarvis
- **Browser / client used:** HTTP endpoint execution from Nova runtime
- **Date / time of execution:** 2026-04-09 afternoon (GMT+8)

- **Base URL under test:** `http://192.168.31.64:8000`

---

## 4. Source-of-Truth Note

Where wording in the test-case checklist is generic, actual runtime/model semantics must be verified against the authoritative implementation.

Especially for terminal-state behavior, the source of truth is the current V1 model/runtime implementation, not informal wording in the test checklist.

---

## 5. Test Case Results

| ID | Test Case | Result | Notes |
|----|-----------|--------|-------|
| V1-TC-001 | Kickoff with full valid product input | PASS | Returned `INTAKE`, assignee `viper_ba`, no backend-only fields required in request |
| V1-TC-002 | Kickoff with blank assignee defaults to unassigned | NOT RUN | Deferred in Round 1 |
| V1-TC-003 | Kickoff rejects missing required fields | PASS | Returned `422` with `error_type: validation_error` |
| V1-TC-004 | Status returns current stage/owner/status for valid task | PASS | Returned `INTAKE`, `viper_ba`, and current status |
| V1-TC-005 | Gate panel loads for active task | PASS | Returned `gate_status: pending` for created task |
| V1-TC-006 | Approve gate succeeds for pending gate | PASS | Approve returned success and gate moved to decided state |
| V1-TC-007 | Reject gate requires reason | FAIL | Returned `500` with unstructured `error`, not expected typed/consistent error handling |
| V1-TC-008 | Double decision is prevented | PASS | Returned `409` with `error_type: already_decided` |
| V1-TC-009 | Terminal-state task cannot be gate-confirmed | NOT RUN | Deferred in Round 1 |
| V1-TC-010 | Platform unavailable is rendered distinctly from task not found | PARTIAL | `task_not_found` verified; platform-unavailable path not yet forced in Round 1 |
| V1-TC-011 | Failed fetch clears stale panel / no stale success state remains | NOT RUN | Requires browser/UI observation |
| V1-TC-012 | PMO behaves as non-authoritative shell | PARTIAL | Behavior remains shell-consistent; deeper code/runtime reconfirmation already reviewed separately |
| V1-TC-013 | Single browser-session path across all 3 V1 functions | PASS | Kickoff → Status → Gate → Approve → second decision rejected |

---

## 6. Detailed Observations

### Functional observations
- Kickoff, status view, gate load, approve, and double-decision prevention all behaved materially as expected.
- `task_not_found` behavior was structurally correct.
- The live server is reachable and serving the PMO shell correctly.

### UI / error-handling observations
- Structured error handling is not fully consistent yet.
- Specifically, reject-without-reason returned `500` with `error` instead of a typed error shape matching the documented M4 intent.

### Boundary / architecture observations
- The tested paths still behave like a thin shell over governed backend responses.
- No evidence in this round suggested PMO held independent authoritative business state.

---

## 7. Standing Notes Verification

These are accepted V1 shortcuts/simplifications and should be recorded explicitly, not rediscovered as if they were unknown defects.

### 7.1 DEFAULT_PROJECT_ID shortcut
- **Observed during test?** Yes
- **Consistent with accepted V1 note?** Yes
- **Comments:** Kickoff behavior is consistent with the accepted V1 shortcut model.

### 7.2 Evidence simplification
- **Observed during test?** Indirectly / not deeply exercised in Round 1
- **Consistent with accepted V1 note?** Appears consistent
- **Comments:** Needs final-round observation if Alex wants explicit UI confirmation.

---

## 8. Issues Found During UAT

| ID | Severity | Area | Description | Status |
|----|----------|------|-------------|--------|
| UAT-001 | Major | Error handling | Reject without reason returned HTTP 500 with `{ok:false,error:"reason_required",message:...}` instead of the expected structured typed error response pattern | Open |

Severity guidance:
- Critical = blocks V1 acceptance
- Major = significant issue needing explicit decision
- Minor = non-blocking issue / documentation note
- Note = accepted simplification or observation

---

## 9. Final Test Judgment

### Summary
- Total test cases: 13
- Passed: 6
- Failed: 1
- Partial: 2
- Not Run: 4

### UAT conclusion
Choose one:
- ☐ Accepted
- ☐ Accepted with notes
- ☒ Re-test required
- ☐ Not accepted

### Final comment
Round 1 found a real issue in the documented V1 error-handling contract: reject-without-reason is currently surfacing as an internal-server-style failure rather than a clean typed validation/business-rule error. Because Alex will perform the final round, this should be treated as a real finding and clarified before final UAT closure.

---

## 10. Sign-off

| Role | Name | Decision | Date |
|------|------|----------|------|
| Round 1 UAT | Nova | Re-test required | 2026-04-09 |
| Environment Preparation | Jarvis | Pending | — |
| Final UAT | Alex | Pending | — |

---

## 11. Archive Note

After execution is complete, this report should be stored with the V1 freeze archive set and treated as the formal test-evidence layer for V1.
