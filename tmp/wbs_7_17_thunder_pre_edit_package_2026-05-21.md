# Thunder WBS 7.17 Pre-Edit Package

Status: `THUNDER_WBS_7_17_PRE_EDIT_PACKAGE_RETURNED / CODE EDITS NOT STARTED`

Prepared: 2026-05-21 CST
Prepared by: Thunder
Repo: `D:\Projects\Nexus`
Scope: pre-coding / pre-edit only

## 0. Authorization Boundary

This package is file-backed pre-edit evidence only. Source code edits have not started.

No source files were modified, no commit was created, no runtime/listener/daemon was started, no assignment was published, no private agent was invoked, no business task was run, no broker config was mutated, no credential value was exposed, and WBS 7.17 was not marked PASS.

Implementation remains blocked until Nova clears this package and Alex explicitly authorizes implementation kickoff.

## 1. Repo / Base / Branch / Worktree Evidence

Commands were run read-only from `D:\Projects\Nexus`.

```text
git status --short --branch
## codex/wbs-7-17-live-mq-send-receive-correction...origin/master
```

```text
git rev-parse --show-toplevel
D:/Projects/Nexus

git rev-parse --abbrev-ref HEAD
codex/wbs-7-17-live-mq-send-receive-correction

git rev-parse HEAD
8f5bd1ec18a9f1211434f2bf0f3d3200a476bb87

git rev-parse origin/master
8f5bd1ec18a9f1211434f2bf0f3d3200a476bb87

git merge-base HEAD origin/master
8f5bd1ec18a9f1211434f2bf0f3d3200a476bb87
```

Required source base is satisfied:

```text
origin/master@8f5bd1ec18a9f1211434f2bf0f3d3200a476bb87
```

Proposed branch is current:

```text
codex/wbs-7-17-live-mq-send-receive-correction
```

Pre-package working tree evidence:

```text
git diff --stat
<no output>

git diff --cached --stat
<no output>
```

The only intended file-system write for this turn is this Markdown package under `tmp/`.

Post-package file evidence:

```text
Get-Item tmp/wbs_7_17_thunder_pre_edit_package_2026-05-21.md
Length: 25942 bytes at final verification

git check-ignore -v tmp/wbs_7_17_thunder_pre_edit_package_2026-05-21.md
.gitignore:15:tmp/ tmp/wbs_7_17_thunder_pre_edit_package_2026-05-21.md

git status --short --branch
## codex/wbs-7-17-live-mq-send-receive-correction...origin/master
```

The package is file-backed but ignored by git via `tmp/`; tracked source worktree status remains clean.

## 2. Source Authority Read

Primary authority explicitly requested:

- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\3.5-workflow-runtime-mq-architecture\implementation-design\THUNDER_3_5_4_19_WBS_7_17_LIVE_MQ_SEND_RECEIVE_CORRECTION_HANDOFF_2026-05-21.md`
- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\4.19-multi-channel-agent-runtime-compatibility\review-evidence\nova\2026-05-21_4_19_WBS_7_17_THUNDER_PRE_EDIT_REQUEST_AUTHORIZATION.md`

Handoff Section 1 source authority read:

- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\standards\THREE_LAYER_ARCHITECTURE_BOUNDARY_STANDARD_V0_1.md`
- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\3.5-workflow-runtime-mq-architecture\solution-design\3_5_GENERIC_LIVE_MQ_SEND_RECEIVE_CAPABILITY_SOLUTION_SPEC_V0_1.md`
- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\3.5-workflow-runtime-mq-architecture\implementation-design\jarvis\2026-05-21_3.5-4.19-wbs7.17-implementation-alignment-design_jarvis_v0.3\`
  - `3_5_4_19_WBS_7_17_IMPLEMENTATION_ALIGNMENT_JARVIS_README_V0_3.md`
  - `3_5_4_19_WBS_7_17_IMPLEMENTATION_ALIGNMENT_JARVIS_IMPLEMENTATION_PLAN_V0_3.md`
  - `3_5_4_19_WBS_7_17_IMPLEMENTATION_ALIGNMENT_JARVIS_DESIGN_CLARIFICATIONS_V0_3.md`
  - `3_5_4_19_WBS_7_17_IMPLEMENTATION_ALIGNMENT_JARVIS_EVIDENCE_TRACE_V0_3.md`
  - `3_5_4_19_WBS_7_17_IMPLEMENTATION_ALIGNMENT_JARVIS_CHANGELOG_V0_3.md`
  - `3_5_4_19_WBS_7_17_IMPLEMENTATION_ALIGNMENT_JARVIS_SUBMISSION_MANIFEST_V0_3.json`
  - `3_5_4_19_WBS_7_17_IMPLEMENTATION_ALIGNMENT_JARVIS_SUBMISSION_LOG_V0_3.md`
  - `3_5_4_19_WBS_7_17_IMPLEMENTATION_ALIGNMENT_JARVIS_SHA256SUMS_V0_3`
- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\3.5-workflow-runtime-mq-architecture\review-evidence\nova\review-2026-05-21-jarvis-3-5-4-19-wbs7-17-implementation-alignment-design-v0-3.md`
- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\4.19-multi-channel-agent-runtime-compatibility\review-evidence\nova\2026-05-21_4_19_WBS_7_17_ALEX_ALIGNMENT_ACCEPTANCE.md`
- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\4.19-multi-channel-agent-runtime-compatibility\solution-design\MULTI_CHANNEL_AGENT_RUNTIME_COMPATIBILITY_MODEL_V0_1.md`
- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\4.19-multi-channel-agent-runtime-compatibility\README.md` lines 119-127 for WBS 7.15 and WBS 7.16 bounded evidence summary.

Authority path not independently resolved during this read-only pass:

- Archived blocked review path named in handoff: `...\archive\2026-05-process\review-evidence\nova\2026-05-20_4_19_WBS_7_17_BLOCKED_REVIEW.md`

Searches under `D:\Nova-Jarvis-Shared-Docs` did not find that exact file. The current handoff and 4.19 README still preserve the same blocked-review conclusion: WBS 7.17 previous evidence was not accepted as PASS, sender-only proof is insufficient, and the old Thunder branch must not be continued.

## 3. Read-Only Nexus Source Findings

Observed source surfaces:

- `nexus/mq/message_contracts.py` has `ExecutionMessageEnvelope`, `build_execution_envelope`, and `validate_execution_message`. Existing runtime overlay fields are partial: source agent/runtime/role, authority scope, reply subject, and target agent. It lacks explicit target runtime/role, capability, binding policy ref, payload schema/hash, and no-go scope.
- `nexus/mq/payloads.py` defines `CommandMessagePayload`, `GoalDrivenCommandPayload`, `ReviewTaskPayload`, `FeedbackMessagePayload`, `BusinessMessagePayload`, `TimeoutMessagePayload`, `RetryMessagePayload`, `DeadLetterMessagePayload`, `EvidenceWriteMessagePayload`, `StateTransitionMessagePayload`, and `AbnormalStateRecord`. It does not define first-class `Result_Message`, `Callback_Message`, `Handoff_Message`, or `Anomaly_Message` payload contracts.
- `nexus/mq/taxonomy.py` currently has 7 primary message types and 2 deferred message types. Existing tests assert those exact counts.
- `nexus/mq/message_families.py` derives family definitions directly from taxonomy.
- `nexus/mq/protocol_routing.py` routes existing execution message types and older protocol types. It does not route first-class execution `Result_Message`, `Callback_Message`, `Handoff_Message`, or `Anomaly_Message`; existing builders include broad legacy `agent.*` and `workflow.*` subject paths.
- `nexus/mq/adapter.py` provides deterministic `MqAdapterStub` publish/consume/ack/nak/DLQ evidence without live broker dependency.
- `nexus/mq/adapter_nats.py` provides live NATS/JetStream behavior, redacted URL evidence, subject/stream config, and ACK logs. This package does not propose running it during pre-edit.
- `nexus/mq/listener_runtime.py` has poll/ACK behavior, anomaly emission, timeout publishing, and runtime startup paths. WBS 7.17 implementation should avoid starting this runtime during source work.
- `nexus/mq/dispatch_request.py`, `dispatch_eligibility.py`, and `dispatch_assignment.py` contain inert 4.19 request/eligibility/candidate logic. They are useful policy references, but WBS 7.17 must not publish assignment or perform operational dispatch.
- `nexus/mq/agent_registry.py`, `agent_registry_store.py`, and `agent_registry_service.py` contain registry/readiness/heartbeat/presence state that a 4.19 policy hook can read without mutating runtime state.
- `nexus/mq/idempotency_store.py` contains bounded idempotency checks and duplicate detection. WBS 7.17 can reuse the concept, but the live receive helper must still prove claim/dedupe before handler side effects.
- `nexus/mq/agent_runtime.py` is a WBS 15.6 controlled-UAT bootstrap surface using `nexus.3_5.uat.*` subjects and `Business_Message` for controlled UAT returns. It is not the WBS 7.17 target implementation path.

## 4. Planned Write Set

No source edits are authorized now. If Nova clears this package and Alex authorizes implementation kickoff, the planned write set is:

Existing source files:

- `nexus/mq/taxonomy.py`
- `nexus/mq/payloads.py`
- `nexus/mq/message_contracts.py`
- `nexus/mq/message_families.py`
- `nexus/mq/protocol_routing.py`

New source modules:

- `nexus/mq/live_transport_evidence.py`
- `nexus/mq/agent_message_capability_policy.py`
- `nexus/mq/live_send_receive.py`
- `nexus/mq/wbs717_diagnostic_binding.py`

Existing tests to update:

- `nexus/mq/tests/test_message_contracts.py`

New tests:

- `nexus/mq/tests/test_wbs717_live_send_receive_contract.py`
- `nexus/mq/tests/test_wbs717_diagnostic_binding.py`
- `nexus/mq/tests/test_wbs717_live_transport_evidence.py`

Conditional source files only if focused implementation proves the wrapper cannot satisfy the contract without a small shared change:

- `nexus/mq/idempotency_store.py`: only if a reusable claim-before-side-effect API is required instead of a WBS 7.17 run-scoped ledger inside `live_send_receive.py`.
- `nexus/mq/adapter_interface.py`: only if the evidence wrapper needs a typed adapter protocol. No interface change is expected initially.
- `nexus/mq/adapter.py`: only if deterministic stub evidence needs a non-breaking accessor. No publish/consume semantics change is expected initially.
- `nexus/mq/adapter_nats.py`: only if Nova requires live adapter preflight metadata hooks in source. No broker mutation, live connection, or stream creation will be performed during implementation tests.

## 5. Explicit Non-Target Files / Surfaces

Do not edit for WBS 7.17 implementation unless Nova/Alex explicitly expands scope:

- `nexus/mq/agent_runtime.py`
- `nexus/mq/tests/test_agent_runtime_bootstrap.py`
- `nexus/mq/listener_runtime.py` runtime start behavior
- `nexus/mq/listener_supervisor.py`
- `nexus/mq/phase3_uat_command_bridge.py`
- `nexus/mq/private_agent_contract.py`
- `nexus/mq/private_agent_eligibility.py`
- `nexus/mq/private_agent_projection.py`
- `nexus/mq/private_context_policy.py`
- `nexus/mq/private_contract_registry.py`
- `nexus/mq/private_invocation_allowlist.py`
- `nexus/mq/private_invocation_runner.py`
- `nexus/mq/private_result_candidate.py`
- `nexus/mq/private_result_validators.py`
- `nexus/mq/private_task_package.py`
- `config/agents.yaml`
- `config/agents/*.yaml`
- broker deployment files or NATS server config
- credential files, `.env` files, secrets, tokens, key material, or rotations
- UI Dashboard files
- marketplace, payment, ranking, escrow, reputation, production operations, or WBS 7.18 persistent runtime surfaces

`dispatch_request.py`, `dispatch_eligibility.py`, and `dispatch_assignment.py` are not planned write targets. They remain read-only policy references and regression surfaces unless Nova explicitly asks for a 4.19 shared policy refactor.

## 6. File-by-File Implementation Plan

### `nexus/mq/taxonomy.py`

- Add `Result_Message`, `Callback_Message`, `Handoff_Message`, and `Anomaly_Message` as first-class transport-active primary message types.
- Add message classes such as `result`, `callback`, `handoff`, and `anomaly`.
- Preserve deferred status for `Evidence_Write_Message` and `State_Transition_Message`.
- Update exact-count tests intentionally so count changes are reviewed, not accidental.

### `nexus/mq/payloads.py`

- Add `ResultMessagePayload` for non-business diagnostic/result candidates with original message/correlation/causation/idempotency/evidence refs and `not_business_completion=True`.
- Add `CallbackMessagePayload` and `HandoffMessagePayload` for return/progress/transfer carriers that cannot imply business completion.
- Add `AnomalyMessagePayload` for abnormal transport/runtime state evidence, distinct from `Dead_Letter_Message`.
- Validate required correlation/evidence/reason fields and reject any `not_business_completion=False` payload.

### `nexus/mq/message_contracts.py`

- Import the new payload classes and extend `PAYLOAD_TYPE_BY_MESSAGE_TYPE`.
- Extend callback/response type handling to include `Result_Message`, `Callback_Message`, `Handoff_Message`, `Anomaly_Message`, and existing timeout/retry/DLQ returns.
- Add WBS 7.17 runtime addressing fields to `ExecutionMessageEnvelope`: target runtime id, target role, capability, binding policy ref, payload schema, payload hash, no-go scope, and evidence/artifact refs as needed by existing patterns.
- Add strict WBS 7.17 diagnostic validation that requires source/target agent/runtime identities, capability, authority scope, binding policy ref, reply path, payload schema/hash, expiry, correlation, idempotency, and no-go scope.
- Keep generic validation backward compatible where existing non-WBS tests do not request WBS 7.17 strict mode.

### `nexus/mq/message_families.py`

- Prefer no direct logic change because it derives from taxonomy.
- Update only if family metadata needs explicit non-business return classification for tests or evidence.

### `nexus/mq/protocol_routing.py`

- Add WBS 7.17 run-scoped subject builders/validators.
- Reject broad or unscoped subjects for WBS 7.17 diagnostics, including `agent.>`, `workflow.>`, `agent.jarvis.inbox`, and unscoped production subjects.
- Route execution `Result_Message`, `Callback_Message`, `Handoff_Message`, and `Anomaly_Message` through reply/return/anomaly subjects without treating any as business completion.
- Keep legacy routing behavior intact for existing tests outside the WBS 7.17 strict path.

### `nexus/mq/live_transport_evidence.py`

- Add redacted evidence dataclasses or typed dictionaries for preflight, publish, receive, ACK, duplicate/idempotency, timeout/anomaly/DLQ, return path, cleanup, and final gate aggregation.
- Include `not_business_completion=True` on result/anomaly/timeout/ACK/publish evidence.
- Add secret-value scanning/redaction helpers for evidence payloads and refs.
- Ensure publish-only evidence produces an incomplete/not-pass gate state.

### `nexus/mq/agent_message_capability_policy.py`

- Add 4.19 allow/deny metadata models for source/target agent runtime, direction, capability, authority, privacy/task boundary, no-go scope, subject pattern, payload schema, evidence requirements, readiness and heartbeat observations.
- Read from registry/eligibility records or provided fakes; do not mutate registry, publish assignment, or emit transport envelopes.
- Fail closed on missing, denied, stale, mismatched, unregistered, unready, stale heartbeat, not accepting work, capability denied, authority denied, privacy denied, or no-go conflict.
- Emit `binding_policy_ref` and denial reasons only.

### `nexus/mq/live_send_receive.py`

- Add deterministic helper functions for future tests:
  - `preflight_live_send`
  - `publish_live_message`
  - `receive_live_message_once`
  - `publish_return_message`
  - `evaluate_wbs717_evidence_gate`
- Block before `adapter.publish` when policy, subject, envelope, payload schema/hash, expiry, credential resolver, or target readiness fails.
- Use credential/config references only and a resolver interface that returns redacted success/failure metadata; never log or return secret values.
- On receive, validate envelope, subject, target agent/runtime, policy/binding, idempotency, and safe-intake claim before ACK.
- Suppress duplicates before handler side effects and record duplicate evidence.
- Model missing ACK/result as timeout/anomaly/DLQ evidence and never as PASS.

### `nexus/mq/wbs717_diagnostic_binding.py`

- Add thin WBS 7.17 binding objects over the generic 3.5 helpers.
- Carry run id, allowed subject scope, diagnostic command payload schema/hash, no-go scope, policy ref, and evidence refs.
- Explicitly reject business assignment, business dispatch, private-agent invocation, and non-diagnostic payloads.
- Keep binding per-run and not reusable as a second sender protocol.

### Tests

- Update `test_message_contracts.py` for new message-family counts and new payload/envelope strict validations.
- Add focused WBS 7.17 tests for pre-publish blocking, subject rejection, policy denial, credential resolver failure, publish evidence, receive ACK ordering, duplicate suppression, timeout/anomaly/DLQ, return correlation, sender-only not-pass, and secret scan.
- Use `MqAdapterStub` and fake policy/resolver/registry objects only.
- Do not start real listeners, daemon loops, live NATS, private agents, or business workflows.

## 7. Jarvis TSK-001 to TSK-008 Mapping

| TSK | Jarvis requirement | Planned source mapping | Planned tests/evidence |
|-----|--------------------|-------------------------|------------------------|
| TSK-001 | Map WBS 7.17 diagnostic command onto 3.5 `Message_Envelope` with agent addressing | `message_contracts.py`, `payloads.py`, `taxonomy.py`, `wbs717_diagnostic_binding.py` | strict envelope tests requiring source/target agent/runtime, capability, authority, binding policy ref, reply path, schema/hash, expiry, correlation, idempotency, no-go scope |
| TSK-002 | 4.19 policy hook allow/deny metadata only | `agent_message_capability_policy.py` | policy tests proving allow/deny metadata only, no transport envelope, fail-closed denial for missing/stale/unready/unauthorized target |
| TSK-003 | Credential/config refs through approved 3.5 resolver before live publish | `live_send_receive.py`, `live_transport_evidence.py` | resolver failure blocks before publish, evidence is redacted, secret scan clean |
| TSK-004 | Route publish through 3.5 live publisher and subject router | `live_send_receive.py`, `protocol_routing.py` | publish uses run-scoped subject, broad subjects rejected, adapter publish not called on invalid preflight |
| TSK-005 | Route receive through 3.5 durable consumer/listener; ACK after validation/target/dedupe/safe intake | `live_send_receive.py`, existing `MqAdapterStub`, optional `idempotency_store.py` dependency | receive-once tests assert ACK occurs only after validation, target check, dedupe/claim, and safe intake; duplicate suppressed before side effects |
| TSK-006 | Timeout/retry/DLQ/anomaly through 3.5 policy; missing ACK/result is not PASS | `live_send_receive.py`, `live_transport_evidence.py`, existing retry/DLQ concepts | missing ACK/result routes to timeout/anomaly/DLQ evidence; final gate not-pass |
| TSK-007 | Correlated 3.5 return path for result/anomaly/timeout; no business completion | `payloads.py`, `message_contracts.py`, `protocol_routing.py`, `live_send_receive.py` | return path test checks original message id, causation id, correlation id, idempotency key, evidence refs, `not_business_completion=True` |
| TSK-008 | Evidence gate requires send, receive, ACK, duplicate/idempotency, timeout/anomaly, return path, cleanup, secret scan | `live_transport_evidence.py`, `wbs717_diagnostic_binding.py` | final evidence gate rejects sender-only evidence and requires all WBS 7.17 evidence classes plus cleanup and secret scan |

## 8. Planned Tests / Evidence Shape

Focused deterministic tests after implementation kickoff:

```powershell
python -m pytest nexus/mq/tests/test_message_contracts.py nexus/mq/tests/test_wbs717_live_send_receive_contract.py nexus/mq/tests/test_wbs717_diagnostic_binding.py nexus/mq/tests/test_wbs717_live_transport_evidence.py -q
```

WBS 7.8/7.9/7.10 registry, heartbeat, and dispatch regressions:

```powershell
python -m pytest nexus/mq/tests/test_agent_registry_persistence.py nexus/mq/tests/test_agent_registry_conflicts.py nexus/mq/tests/test_agent_registry_recovery.py nexus/mq/tests/test_agent_registry_readiness.py -q
python -m pytest nexus/mq/tests/test_heartbeat_runtime.py nexus/mq/tests/test_heartbeat_presence_ttl.py nexus/mq/tests/test_heartbeat_registry_integration.py nexus/mq/tests/test_heartbeat_agent_access_projection.py -q
python -m pytest nexus/mq/tests/test_dispatch_eligibility.py nexus/mq/tests/test_dispatch_reallocation.py nexus/mq/tests/test_operational_dispatch_eligibility.py nexus/mq/tests/test_operational_dispatch_assignment.py nexus/mq/tests/test_operational_dispatch_agent_access.py -q
```

Focused 3.5/MQ regressions:

```powershell
python -m pytest nexus/mq/tests/test_phase2_durable_intake_ack.py nexus/mq/tests/test_phase4_timeout_abnormal_retry_recovery.py nexus/mq/tests/test_execution_lifecycle.py -q
```

Optional full MQ suite with live broker disabled or unreachable:

```powershell
$env:NATS_URL='nats://127.0.0.1:1'
python -m pytest nexus/mq/tests -q
```

Quality and secret scan:

```powershell
git diff --check
rg -n "(AIza|BEGIN PRIVATE KEY|Bearer |password=|token=|secret=|nats://[^/\s]+:[^@\s]+@)" nexus/mq
```

Evidence package shape expected after future implementation:

- `repo_base.json`: branch, base, HEAD, merge-base, status.
- `authority_refs.md`: authority docs and TSK mapping.
- `wbs_7_17_envelope_validation.json`: strict envelope validation and failure evidence.
- `wbs_7_17_policy_validation.json`: 4.19 allow/deny metadata evidence.
- `wbs_7_17_resolver_evidence.json`: credential-ref resolver success/failure metadata with no secret values.
- `wbs_7_17_transport_evidence.json`: publish and adapter evidence, redacted.
- `wbs_7_17_ack_evidence.json`: receiver validation, target check, dedupe/claim, safe intake, ACK boundary.
- `wbs_7_17_duplicate_evidence.json`: duplicate suppressed before side effects.
- `wbs_7_17_timeout_dlq_evidence.json`: missing ACK/result routes to timeout/anomaly/DLQ and no PASS.
- `wbs_7_17_return_evidence.json`: correlated `Result_Message`/anomaly/timeout return evidence.
- `wbs_7_17_acceptance_gate.json`: final evidence gate; sender-only evidence is incomplete/not-pass.
- `wbs_7_17_secret_scan.txt`: scan command and clean result.

## 9. Credential / No-Secret Plan

- Implementation will accept credential/config refs only, such as `env:NAME`, `file-ref:...`, or `credential-ref:...` if approved by Nova/Alex.
- Resolver success will be proven by resolver status and config/evidence refs, never by logging resolved material.
- Any resolver failure blocks before `adapter.publish`.
- Evidence will use redacted broker URLs and reference labels only.
- Secret scan patterns will include API key, private key, bearer token, password/token/secret markers, and embedded NATS URL credentials.
- No credential files, `.env` values, secret refs, or rotations are in the write set.

## 10. No-Go Confirmation

Confirmed not authorized and not performed:

- no source implementation edits started;
- no commit;
- no listener start;
- no daemon start;
- no UAT/formal WBS 7.17 rerun;
- no assignment publish;
- no private-agent registration, dispatch, invocation, or result use;
- no operational dispatch;
- no business dispatch;
- no business execution;
- no business completion marking;
- no broker config mutation;
- no credential value exposure;
- no UI Dashboard work;
- no WBS 7.18 persistent runtime enablement;
- no WBS 7.17 PASS marking.

## 11. Residual Risks / Assumptions / Scope-Change Requests

Residual risks:

- The exact archived blocked-review file path named in the handoff was not found by read-only search. Current handoff, Nova review, Alex acceptance, and 4.19 README carry the same controlling conclusions, so this does not block pre-edit planning.
- The authoritative credential resolver backend remains a design clarification. Plan assumes a small resolver interface in `live_send_receive.py` with fake resolver tests until Nova/Alex confirms the live backend.
- Durable policy storage for WBS 7.17 per-run capability policy remains a design clarification. Plan assumes non-secret in-memory/test policy objects for deterministic source tests and no runtime mutation.
- Existing `agent_runtime.py` is WBS 15.6 controlled-UAT scoped and returns `Business_Message`; WBS 7.17 implementation should not refactor it unless Nova explicitly expands scope.
- Existing `idempotency_store.py` records processed keys after safe processing, while WBS 7.17 receive evidence must prove claim/dedupe before side effects. Plan uses a WBS 7.17 run-scoped receive ledger unless Nova requests a shared idempotency API change.

Assumptions:

- Deterministic unit/integration tests with `MqAdapterStub` are sufficient for Thunder implementation evidence before any live rerun gate.
- Live NATS tests remain gated and disabled/unreachable during source implementation verification unless Nova/Alex separately authorize a redacted live preflight.
- 4.19 policy hook may read registry/readiness/heartbeat state but must not mutate registry, publish assignments, or create transport envelopes.
- WBS 7.17 diagnostic binding remains per-run and does not become a reusable 4.19 sender protocol.

Scope-change requests before implementation kickoff:

- Nova should confirm whether `Result_Message`, `Callback_Message`, `Handoff_Message`, and `Anomaly_Message` all belong in `PRIMARY_MESSAGE_TYPES` for this correction, or whether any should be deferred but transport-active through a separate classification.
- Nova should confirm the accepted credential/config ref forms for WBS 7.17 source tests.
- Nova should confirm whether live adapter source changes are expected now, or whether wrapper-level preflight/evidence around existing adapters is preferred.

## 12. Recommendation for Nova Pre-Edit Review

Recommend Nova review this package for:

- base/branch correctness against `origin/master@8f5bd1ec18a9f1211434f2bf0f3d3200a476bb87`;
- write set boundaries;
- non-target exclusions, especially WBS 15.6 UAT runtime and private-agent surfaces;
- TSK-001 through TSK-008 coverage;
- credential resolver assumption;
- policy storage assumption;
- whether the planned tests/evidence package are sufficient before Alex implementation kickoff.

Thunder should not edit source until Nova returns cleared pre-edit review and Alex explicitly authorizes implementation kickoff.
