# Thunder Phase 2 Durable Intake / ACK Boundary Report V0.1

## Scope

Implemented bounded Phase 2 only:

- durable intake record behavior
- raw and normalized envelope preservation
- inbound validation before ACK eligibility
- ACK / broker action decision logic
- invalid intake outcomes for IF-01 through IF-09
- IF-09 local recovery / handler exhaustion behavior
- focused tests and fixtures

Confirmed not touched:

- HITL decision flow semantics
- HITL review UI/backend
- full state/evidence store redesign
- listener/supervisor architecture beyond minimal intake-path broker-action handling
- Phase 3+ dispatch/runtime expansion
- production NATS hardening

## Changed Files

- `config/agents.yaml`
- `config/agents_uat.yaml`
- `nexus/mq/durable_state.py`
- `nexus/mq/coordination_runtime.py`
- `nexus/mq/listener_runtime.py`
- `nexus/mq/adapter.py`
- `nexus/mq/tests/test_durable_state.py`
- `nexus/mq/tests/test_execution_runtime_v03.py`
- `nexus/mq/tests/test_phase2_durable_intake_ack.py`

## Exact Functions / Modules Touched

- `nexus/mq/durable_state.py`
  - `EnvelopeInboxRecord`
  - `record_envelope_inbox(...)`
  - `complete_envelope_inbox(...)`
  - `get_envelope_inbox(...)`
  - `list_envelope_inbox_for_local_recovery(...)`
  - `mark_envelope_inbox_handler_running(...)`
  - `mark_envelope_inbox_handler_failure(...)`
  - `update_envelope_inbox_abnormal_state(...)`
  - `_migrate_schema(...)`
- `nexus/mq/coordination_runtime.py`
  - `intake_inbound_message(...)`
  - `receive_callback(...)`
  - `receive_feedback(...)`
  - `record_post_ack_handler_failure(...)`
  - `list_local_recovery_candidates(...)`
  - `_intake_protocol_message(...)`
  - `_receive_protocol_callback(...)`
  - `_intake_execution_message(...)`
  - `_classify_execution_intake_failure(...)`
  - `_record_terminal_intake_failure(...)`
  - `_broker_action_for_expired_subject(...)`
  - `_anomaly_code_for_expiry(...)`
- `nexus/mq/listener_runtime.py`
  - `poll_once(...)`
  - `_apply_broker_action(...)`
  - `_result_message_id(...)`
  - `_should_publish_anomaly(...)`
- `nexus/mq/adapter.py`
  - `nak(...)`

## Behavior Summary

- Valid inbound execution / protocol messages now ACK only after parse/normalization/validation/idempotency and durable intake record commit.
- Invalid pre-intake cases IF-01 through IF-08 now produce classified terminal records in `envelope_inbox`, with anomaly / abnormal metadata where required.
- Retryable IF-04 subject families now classify to `NAK` instead of generic reject.
- Deferred skeleton-inactive transport families classify to IF-05 and ACK after terminal recording.
- IF-09 is handled as local recovery only. No broker NAK. After local retry exhaustion (`>= 3`), the intake record becomes `handler_exhausted`, recovery candidates exclude it, and `mechanism_stall` abnormal state is created.

## Verification Commands

```powershell
python -m pytest nexus/mq/tests/test_durable_state.py -q
```

Result:

```text
9 passed in 0.66s
```

```powershell
python -m pytest nexus/mq/tests/test_phase2_durable_intake_ack.py -q
```

Result:

```text
16 passed in 0.77s
```

```powershell
python -m pytest nexus/mq/tests/test_coordination_runtime.py -q
```

Result:

```text
5 passed in 0.32s
```

```powershell
python -m pytest nexus/mq/tests/test_listener_supervisor.py -q
```

Result:

```text
2 passed in 0.18s
```

```powershell
python -m pytest nexus/mq/tests -q
```

Result:

```text
106 passed in 6.34s
```

## Behavior Matrix

### INTAKE

| ID | Status | Evidence |
| --- | --- | --- |
| INTAKE-01 malformed/unparseable envelope -> IF-01 REJECT/ACK path | PASS | `test_if01_malformed_unparseable_envelope_is_terminal_reject` |
| INTAKE-02 schema validation failure -> IF-02 REJECT/ACK path | PASS | `test_if02_schema_validation_failure_records_terminal_reject` |
| INTAKE-03 authority/scope mismatch -> IF-03 REJECT/ACK + abnormal | PASS | `test_if03_authority_scope_mismatch_creates_abnormal_state` |
| INTAKE-04 expired `agent.{id}.inbox` -> IF-04 TERM/ACK | PASS | `test_if04_expired_inbox_is_terminal_ack_case` |
| INTAKE-05 expired `agent.{id}.callbacks` -> IF-04 TERM/ACK | PASS | `test_if04_expired_callback_subject_is_term_ack_with_orphan_anomaly` |
| INTAKE-06 expired feedback -> IF-04 NAK | PASS | `test_if04_expired_feedback_is_retryable_nak_case` |
| INTAKE-07 expired `review.*` -> IF-04 NAK | PASS | `test_if04_expired_review_subject_is_retryable_nak_case` |
| INTAKE-08 expired `ops.timeout` -> IF-04 NAK | PASS | `test_if04_expired_ops_timeout_is_retryable_nak_case` |
| INTAKE-09 expired `ops.anomaly` -> IF-04 TERM/ACK | PASS | `test_if04_expired_ops_anomaly_is_term_ack_without_abnormal_state` |
| INTAKE-10 deferred inactive family -> IF-05 REJECT/ACK | PASS | `test_if05_deferred_family_is_terminal_reject_case`, updated `test_listener_rejects_deferred_execution_family` |
| INTAKE-11 duplicate/idempotency hit -> IF-06 REJECT/ACK and reuse existing result | PASS | `test_if06_duplicate_reuses_existing_result_without_terminal_record` |
| INTAKE-12 unknown correlation/causation -> IF-07 REJECT/ACK + abnormal | PASS | `test_if07_unknown_correlation_causation_records_other_abnormal` |
| INTAKE-13 invalid HITL callback -> IF-08 REJECT/ACK + authority abnormal | PASS | `test_if08_invalid_hitl_callback_creates_authority_abnormal` |
| INTAKE-14 valid inbound ACK only after durable intake commit | PASS | `test_runtime_intake_records_pending_task_and_allows_ack`, `test_listener_acks_terminal_reject_and_naks_retryable_expiry` |
| INTAKE-15 raw/original envelope preserved separately from normalized | PASS | `test_envelope_inbox_preserves_raw_and_normalized_intake_contract` |
| INTAKE-16 invalid payload preserves raw audit body | PASS | `test_if01_malformed_unparseable_envelope_is_terminal_reject`, `test_if02_schema_validation_failure_records_terminal_reject` |
| INTAKE-17 terminal record stores validation errors and broker action | PASS | `test_envelope_inbox_preserves_raw_and_normalized_intake_contract` |
| INTAKE-18 callback invalidity rejected at intake boundary without runtime progression | PASS | `test_if07_unknown_correlation_causation_records_other_abnormal`, `test_if08_invalid_hitl_callback_creates_authority_abnormal` |
| INTAKE-19 IF-09 local recovery / handler exhaustion path | PASS | `test_if09_post_ack_handler_failure_exhaustion_quarantines_record` |

### ABN

| ID | Status | Evidence |
| --- | --- | --- |
| ABN-01 IF-03 creates `authority_stall` abnormal | PASS | `test_if03_authority_scope_mismatch_creates_abnormal_state` |
| ABN-02 IF-07 creates `other` abnormal | PASS | `test_if07_unknown_correlation_causation_records_other_abnormal` |
| ABN-03 IF-08 creates `authority_stall` abnormal | PASS | `test_if08_invalid_hitl_callback_creates_authority_abnormal` |
| ABN-04 IF-09 exhaustion creates `mechanism_stall` abnormal | PASS | `test_if09_post_ack_handler_failure_exhaustion_quarantines_record` |
| ABN-05 IF-01 / IF-02 do not create abnormal state | PASS | covered by IF-01 / IF-02 focused tests |
| ABN-06 IF-05 does not create abnormal state | PASS | `test_if05_deferred_family_is_terminal_reject_case` |
| ABN-07 retryable IF-04 does not create abnormal before exhaustion, then creates `mechanism_stall` after exhaustion | PASS | `test_if04_expired_feedback_is_retryable_nak_case`, `test_if04_retryable_families_create_mechanism_stall_after_maxdeliver_exhaustion` |

### AUD

| ID | Status | Evidence |
| --- | --- | --- |
| AUD-01 raw malformed body preserved | PASS | `test_if01_malformed_unparseable_envelope_is_terminal_reject` |
| AUD-02 raw and normalized envelopes stored separately | PASS | `test_envelope_inbox_preserves_raw_and_normalized_intake_contract` |
| AUD-03 validation errors stored durably | PASS | `test_envelope_inbox_preserves_raw_and_normalized_intake_contract` |
| AUD-04 broker action stored durably | PASS | `test_envelope_inbox_preserves_raw_and_normalized_intake_contract` |
| AUD-05 terminal outcome stored durably | PASS | `test_if04_expired_inbox_is_terminal_ack_case`, `test_envelope_inbox_local_recovery_exhaustion_blocks_redispatch` |
| AUD-06 local retry count persisted | PASS | `test_envelope_inbox_local_recovery_exhaustion_blocks_redispatch` |
| AUD-07 handler exhausted records excluded from recovery set | PASS | `test_envelope_inbox_local_recovery_exhaustion_blocks_redispatch`, `test_if09_post_ack_handler_failure_exhaustion_quarantines_record` |
| AUD-08 duplicates do not create duplicate side effect / duplicate intake record | PASS | `test_if06_duplicate_reuses_existing_result_without_terminal_record` |

## Skipped Tests

- None in the focused Phase 2 IF matrix coverage set.

## Open Gaps

- Anomaly evidence is represented by durable anomaly identifiers plus listener anomaly publication; there is still no separate durable anomaly store/table in this bounded Phase 2 implementation.
- `NAK` execution is wired in the stub listener/adapter path for verification, but no broader production transport hardening was attempted.
- The original clean-checkout failure came from `config/agents.yaml` not being included in the pushed branch. The branch must include the protocol-aware identity/trust config for the reported results to reproduce.

## Deviations From Handoff

- `envelope_inbox` was extended in place instead of being replaced. This follows Nova’s clarification that behavioral/schema capability matters more than the table name.
- `handler_exhausted_record` is represented by the exhausted `envelope_inbox` record plus abnormal-state linkage, rather than a new standalone table.

## Recommendation

Recommend: **Accept Phase 2 for Nova review**

Reason:

- The bounded Phase 2 intake / ACK implementation is working and the focused/full MQ tests are green.
- The requested focused IF-04 subject-family coverage is now present.
- The remaining risk is review of the implementation itself, not missing test coverage.
