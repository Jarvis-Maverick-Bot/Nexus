# 4.19 Assignment Subject Contract Correction Evidence

Owner: Thunder
Reviewer: Nova
Decision authority: Alex
Prepared: 2026-05-28
Candidate verdict: `IMPLEMENTATION_CORRECTION_READY_FOR_NOVA_REVIEW`

## Review Target

| Item | Value |
|---|---|
| Branch | `codex/4.19-assignment-subject-contract-implementation` |
| Reviewed head | `c75df15e0605025e1b2f7ccf7b1dccae2759697b` |
| Base / merge-base | `3e4a5d7c20814540ea6f63a9ec87cf6e2ebc9133` |
| Nova review commit | `6fc4e3b` |

The corrected branch head is reported after this correction package is committed and pushed.

## Blocking Issue Patched

Candidate Adapter duplicate ACK replay now handles active assignment binding conflicts before any state append or second ACK event publish.

Required behavior:

- Exact replay with matching `assignment_id`, `idempotency_key`, `decision_id`, and `reservation_lease_id`: suppress duplicate and publish no second ACK.
- Active assignment with any differing binding: reject with explicit duplicate binding conflict.
- Conflict path does not mutate active decision/lease/idempotency state and does not publish an ACK event.

## Code Changes

Correction delta from reviewed head:

- `nexus/mq/candidate_adapter_assignment_validator.py`
  - Added duplicate active-assignment binding comparison for idempotency, decision, and reservation lease.
  - Emits `DUPLICATE_ASSIGNMENT_BINDING_CONFLICT` plus a specific conflict code.
- `nexus/mq/tests/test_candidate_adapter_api_cli.py`
  - Added conflicting decision replay test.
  - Added conflicting lease replay test.
  - Existing exact replay suppression test remains green and verifies no second ACK event.

See:

- `changed-files-correction.txt`
- `diff-summary-correction.txt`
- `changed-files-full-branch.txt`
- `diff-summary-full-branch.txt`

## Verification Summary

Raw outputs included:

- `git-diff-check.txt`: exit 0
- `compileall.txt`: exit 0
- `pytest-focused.txt`: 92 passed
- `pytest-regression-slice.txt`: 57 passed
- `pytest-full-mq.txt`: 630 passed, 19 warnings
- `secret-scan.txt`: no high-confidence matches

Warnings: full MQ warnings are the existing NATS deprecation and `test_mq_skeleton.py` return-value warnings. No runtime/UAT warning or deploy action was introduced.

## No-Go Compliance

Not performed:

- Phase 3 rerun;
- deploy;
- broker/config/credential mutation;
- private-agent invocation;
- business execution;
- PASS, WBS PASS, live-readiness, or final PASS claim.

## Deviations And Blockers

Deviations: none.

Blockers: none.

Final candidate verdict: `IMPLEMENTATION_CORRECTION_READY_FOR_NOVA_REVIEW`
