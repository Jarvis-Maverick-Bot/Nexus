# Thunder WBS 7.17 Cleanup Package for Nova Re-Review

Status: `THUNDER_WBS_7_17_CLEANUP_PACKAGE_RETURNED / REQUEST_CHANGES_ADDRESSED / RUNTIME RERUN STILL BLOCKED`

## Review Context

- Repo: `D:\Projects\Nexus`
- Branch: `codex/wbs-7-17-live-mq-send-receive-correction`
- Review verdict addressed: `REQUEST CHANGES / NOT READY FOR RUNTIME RERUN`
- Nova review report: `2026-05-21_4_19_WBS_7_17_IMPLEMENTATION_BRANCH_REVIEW_REQUEST_CHANGES.md`
- Base implementation HEAD before cleanup: `ce9d4dba7fdbb0db9b99174338e32e55b52b957e`

## Blocking Findings Addressed

### 1. Agent transport routing could fall back to legacy broad subjects

Fix:

- `route_execution_envelope_dict(...)` now dispatches `workflow_type == "agent_transport"` into a strict `_route_agent_transport_envelope_dict(...)` path.
- Agent transport envelopes no longer fall through to legacy `agent.*`, `workflow.*`, `feedback.*`, or global ops routes.
- Explicit `subject` on agent transport envelopes must pass `validate_agent_transport_subject(...)`, even when the subject is a legacy broad subject.
- Agent transport commands without explicit subject route to `nexus.agent_transport.<run_id>.<target_agent_id>.inbox`, not `agent.<target>.inbox`.

Regression:

- `test_agent_transport_routing_does_not_fall_back_to_legacy_agent_subjects`

### 2. `reply_to_subject` was not validated before send

Fix:

- `publish_live_message(...)` preflight now validates both:
  - outbound publish `subject`
  - envelope `reply_to_subject`
- Broad reply routes such as `agent.thunder.callbacks` are rejected before adapter publish.

Regression:

- `test_live_send_rejects_broad_reply_to_subject_before_publish`

### 3. Evidence gate could accept records with errors or rejected status

Fix:

- `evaluate_live_mq_evidence_gate(...)` now rejects:
  - any evidence record containing `errors`
  - required evidence records with rejected terminal statuses: `blocked`, `error`, `failed`, `invalid`, `rejected`
- Existing missing-event and sender-only rejection behavior remains.

Regression:

- `test_evidence_gate_rejects_required_record_errors_and_rejected_status`

## Changed Files in Cleanup

- `nexus/mq/protocol_routing.py`
- `nexus/mq/live_send_receive.py`
- `nexus/mq/live_transport_evidence.py`
- `nexus/mq/tests/test_wbs717_diagnostic_binding.py`
- `nexus/mq/tests/test_wbs717_live_send_receive_contract.py`
- `nexus/mq/tests/test_wbs717_live_transport_evidence.py`
- `tmp/wbs_7_17_thunder_cleanup_package_for_nova_2026-05-21.md`

## Test Evidence

- `python -m py_compile nexus/mq/protocol_routing.py nexus/mq/live_send_receive.py nexus/mq/live_transport_evidence.py`
  - Result: pass

- `python -m pytest nexus/mq/tests/test_message_contracts.py nexus/mq/tests/test_wbs717_diagnostic_binding.py nexus/mq/tests/test_wbs717_live_transport_evidence.py nexus/mq/tests/test_wbs717_live_send_receive_contract.py`
  - Result: `22 passed`

- `python -m pytest nexus/mq/tests`
  - Result: `362 passed, 19 warnings`

- Production-source WBS hardcoding scan:
  - Pattern: `AGENT_TRANSPORT_DEFAULT_NO_GO_SCOPE|agent_transport_diagnostic|WBS 7.17|wbs_7_17|wbs717|WBS717|nexus\.wbs7_17`
  - Scope: `nexus/mq`, excluding tests
  - Result: no matches

- `git diff --check`
  - Result: no whitespace errors; Git reported Windows line-ending normalization warnings only.

## Secret Scan

Secret scan over changed cleanup files produced only scanner marker definitions and deliberate test sentinels:

- `api_key`
- `Bearer abc`
- `client_secret`
- `private_key`
- `password=`
- `token=`

No operational credential material was added.

## No-Go Confirmation

Still not performed:

- Runtime/listener/daemon start
- Assignment publish
- Private-agent invocation
- Business execution
- Broker config mutation
- WBS 7.17 PASS marking
- WBS 7.18 work

## Re-Review Request

Nova should re-review the cleanup commit for:

- strict agent transport routing with no legacy fallback
- outbound `reply_to_subject` validation
- evidence gate failure on rejected/error evidence records
- preservation of generic 3.5 MQ runtime boundaries
