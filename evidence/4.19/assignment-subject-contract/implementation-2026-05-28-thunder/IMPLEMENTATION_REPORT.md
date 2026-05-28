# 4.19 Assignment Subject Contract Implementation Evidence

Owner: Thunder
Requester: Alex / Nova governance side
Prepared: 2026-05-28
Candidate verdict: `IMPLEMENTATION_READY_FOR_NOVA_REVIEW`

## Branch And Base

| Item | Value |
|---|---|
| Branch | `codex/4.19-assignment-subject-contract-implementation` |
| Base / origin/master | `3e4a5d7c20814540ea6f63a9ec87cf6e2ebc9133` |
| Merge-base with origin/master | `3e4a5d7c20814540ea6f63a9ec87cf6e2ebc9133` |
| Pre-edit head | `b277d7133493687c16d525b9487809c92d7a5956` |
| Shared Docs review commit | `6b50ca3` |

The final implementation branch head is reported by `git rev-parse HEAD` after this evidence package is committed and pushed.

## Scope Summary

Implemented the narrow v0.3 assignment subject contract patch:

- Dispatch assignment publish now validates the canonical subject shape `nexus.4_19.wbs7_19_14.{run_id}.jarvis.assignment`.
- Dispatch no longer requires `runtime_instance_id` in the assignment subject path.
- Runtime identity remains enforced through dispatch run, Runtime Lifecycle decision, reservation lease, idempotency, and result validation.
- Candidate Adapter semantic intake rejects runtime-scoped assignment aliases before candidate-facing assignment output.
- Direct Candidate Adapter ACK validation rejects runtime-scoped aliases and cannot bypass intake.
- Candidate Adapter duplicate ACK replay with the same assignment/idempotency/decision/lease is suppressed without a second event.

## Code Diff Summary

See:

- `changed-files-code.txt`
- `diff-summary-code.txt`

Code/test files changed:

- `nexus/mq/controller_bridge_dispatch.py`
- `nexus/mq/candidate_adapter_subject_broker_policy.py`
- `nexus/mq/candidate_adapter_api.py`
- `nexus/mq/tests/test_controller_bridge_dispatch.py`
- `nexus/mq/tests/test_controller_bridge_cli.py`
- `nexus/mq/tests/test_candidate_adapter_assignment_validator.py`
- `nexus/mq/tests/test_candidate_adapter_api_cli.py`
- `nexus/mq/tests/test_candidate_adapter_run_loop.py`
- `nexus/mq/tests/test_candidate_adapter_event_mapper.py`
- `nexus/mq/tests/test_resident_controller_subject_policy.py`
- `nexus/mq/tests/test_resident_controller_observer_dispatcher.py`

## Code-To-Design Traceability

| v0.3 requirement | Implementation / tests |
|---|---|
| Canonical inbound assignment subject only | `controller_bridge_dispatch.py::_subject_errors`; `test_controller_bridge_dispatch.py`; `test_controller_bridge_cli.py` |
| No runtime id in canonical subject path | Dispatch subject validator now expects `nexus.4_19.wbs7_19_14.{run_id}.jarvis.assignment`; resident subject tests pin no-runtime canonical form. |
| Runtime id stays in payload/decision/lease validation | Existing `validate_assignment_publish` path preserved; wrong-runtime tests assert dispatch, decision, and lease mismatches still reject. |
| Runtime-scoped subject diagnostic-only | `candidate_adapter_subject_broker_policy.py::_is_runtime_scoped_assignment_alias`; API/ACK/run-loop/CLI negative tests assert alias rejection. |
| No silent fallback | Alias rejection tests use observation-style wildcard patterns and still fail closed before semantic assignment output. |
| Wrong runtime payload rejection | `test_assignment_publish_blocks_wrong_runtime_payload_with_canonical_subject`; `test_candidate_ack_rejects_wrong_runtime_payload`. |
| Wrong lease rejection | Existing lease mismatch tests remain green under canonical subject fixtures. |
| Duplicate assignment/idempotency suppression | `CandidateAdapterApi.ack_assignment`; `test_candidate_ack_duplicate_same_idempotency_suppressed_without_second_event`; controller duplicate publish replay tests. |
| Missing `not_business_completion=true` rejection | `test_candidate_ack_rejects_missing_not_business_completion_flag`. |
| Resident canonical subject pinning | `test_resident_controller_subject_policy_accepts_canonical_assignment_subject_without_runtime_id`; `test_resident_controller_duplicate_replay_same_idempotency_key_suppressed`. |

## Verification Summary

Raw command outputs are included in this package:

- `git-diff-check.txt`: exit 0
- `compileall.txt`: exit 0
- `pytest-focused.txt`: 90 passed
- `pytest-regression-slice.txt`: 57 passed
- `pytest-full-mq.txt`: 628 passed, 19 warnings
- `secret-scan.txt`: no high-confidence matches
- `SHA256SUMS.txt`: package manifest; excludes `SHA256SUMS.txt`, `sha256-verify.txt`, and `sha256-clean-export-verify.txt`
- `sha256-verify.txt`: package directory verification output
- `sha256-clean-export-verify.txt`: clean `core.autocrlf=false` export verification output

Skipped tests: none.

Warnings: full MQ suite retains pre-existing warnings from NATS dependency deprecation and `test_mq_skeleton.py` returning booleans from tests. No warning is introduced by this patch.

## No-Go Compliance

Not performed:

- deploy;
- broker/config/credential mutation;
- private-agent invocation;
- business execution;
- runtime/UAT/Phase 3 rerun;
- PASS, WBS PASS, live-readiness, or final PASS claim;
- broad refactor outside assignment subject contract handling.

## Deviations And Blockers

Deviations: none.

Blockers: none.

Final candidate verdict: `IMPLEMENTATION_READY_FOR_NOVA_REVIEW`
