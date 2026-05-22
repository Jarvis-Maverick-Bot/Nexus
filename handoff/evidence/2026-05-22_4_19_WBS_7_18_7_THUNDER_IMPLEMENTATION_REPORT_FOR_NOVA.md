# WBS 7.18.7 Thunder Implementation Report for Nova Review

Status: `READY_FOR_NOVA_SOURCE_REVIEW / NOT_RUNTIME_RERUN / NOT_PASS`
Owner: Thunder
Date: 2026-05-22 CST
Repository: `D:\Projects\Nexus`
Branch: `codex/wbs-7-18-candidate-agent-persistent-runtime-enablement`
Implementation commit under review: `11b15058409f2488cbc600119d42e038d153533a`

## 1. Review Ask

Nova is requested to perform source review on the WBS 7.18.7 Layer 3 implementation. This report is a repo-backed review artifact stored in the Nexus branch. `D:\Nova-Jarvis-Shared-Docs` is treated as read-only reference material and was not used as the delivery location.

Review goal:

- confirm the implementation remains inside 4.19 Layer 3 Agent Runtime Compatibility / Agent Access;
- confirm no 3.5 MQ transport behavior was moved or redefined;
- confirm no Layer 2 workflow/task semantics were introduced into Layer 3;
- confirm candidate runtime enablement is additive, generic, fail-closed, and non-secret;
- identify any blockers before a separate runtime rerun authorization is considered.

This is not a request to approve runtime rerun, UAT, live listener startup, assignment publication, business execution, or WBS 7.18 PASS.

## 2. Base Evidence

- Stacked base branch accepted for this work: `codex/wbs-7-17-live-mq-send-receive-correction`
- Base HEAD at kickoff: `94254924871d473bbf0f59d31b795c838804316a`
- Merge-base with `origin/master`: `8f5bd1ec18a9f1211434f2bf0f3d3200a476bb87`
- WBS 7.18.7 branch: `codex/wbs-7-18-candidate-agent-persistent-runtime-enablement`
- WBS 7.18.7 implementation commit: `11b15058409f2488cbc600119d42e038d153533a`

## 3. Scope Implemented

The implementation adds generic candidate runtime support for Layer 3:

- candidate agent profile and runtime identity validation;
- registry integration through an adapter-boundary wrapper over existing registry services;
- active-runtime conflict detection and fail-closed quarantine behavior;
- startup/readiness/presence lifecycle evaluation;
- capacity-before-claim checks;
- deterministic controller and scheduler claim decisions;
- Agent Access read-only candidate runtime projection;
- non-secret evidence records for review and audit.

The implementation is intentionally additive. It does not start, connect, register, or publish a live runtime.

## 4. Source Files for Review

Primary new modules:

- `nexus/mq/candidate_runtime_identity.py`
- `nexus/mq/candidate_runtime_registry.py`
- `nexus/mq/candidate_runtime_lifecycle.py`
- `nexus/mq/candidate_runtime_capacity.py`
- `nexus/mq/candidate_runtime_controller.py`
- `nexus/mq/candidate_runtime_scheduler.py`
- `nexus/mq/candidate_runtime_projection.py`
- `nexus/mq/candidate_runtime_evidence.py`

Existing modules touched:

- `nexus/mq/agent_registry.py`
- `nexus/mq/agent_registry_store.py`
- `nexus/mq/agent_access_read_model.py`

Review artifacts in this branch:

- `handoff/evidence/2026-05-22_4_19_WBS_7_18_7_THUNDER_IMPLEMENTATION_PACKAGE.md`
- `handoff/evidence/2026-05-22_4_19_WBS_7_18_7_THUNDER_IMPLEMENTATION_REPORT_FOR_NOVA.md`

## 5. File-Level Review Map

| File | Review focus |
|---|---|
| `candidate_runtime_identity.py` | Generic candidate profile/runtime identity tuple, non-business restrictions, no-secret validation, no Jarvis-only naming in core contract. |
| `candidate_runtime_registry.py` | Adapter-boundary-only registry wrapper, duplicate active candidate detection, local quarantine behavior, migration scope deferral. |
| `candidate_runtime_lifecycle.py` | Fail-closed checks for registry state, init readiness, startup packet freshness, presence freshness, draining/offline states. |
| `candidate_runtime_capacity.py` | Capacity revision, snapshot freshness, accepted claim classes, active claim limits, blocking load states. |
| `candidate_runtime_controller.py` | Policy preflight, emergency stop, disabled controller, no runtime side effects. |
| `candidate_runtime_scheduler.py` | Dispatch request validation, business dispatch rejection, lifecycle/capacity composition, idempotent claim key, duplicate suppression. |
| `candidate_runtime_projection.py` | Read-only Agent Access projection, credential exclusion, secret-like evidence redaction. |
| `candidate_runtime_evidence.py` | Non-secret evidence shape and accepted/rejected/blocked/duplicate status validation. |
| `agent_registry.py` | Backward-compatible optional candidate metadata fields and `quarantined` status. |
| `agent_registry_store.py` | Fake-store normalized row support for candidate metadata; no production DB adapter added. |
| `agent_access_read_model.py` | Optional `candidate_runtimes` projection collection; existing read model behavior preserved. |

## 6. Boundary Confirmation

Confirmed source boundaries:

- no 3.5 MQ transport source edited;
- no broker/server/config/credential mutation;
- no live NATS listener/runtime/daemon start;
- no assignment publish;
- no private-agent invocation;
- no business execution path enabled;
- no production registry DB adapter added;
- no WBS 7.18 PASS claim.

Layer boundaries:

- Layer 1 MQ remains transport/protocol responsibility.
- Layer 2 workflow/task semantics remain outside this implementation.
- Layer 3 owns only compatibility, identity, registry/readiness/capacity, dispatch eligibility, projection, and evidence surfaces.

## 7. Test Evidence

Focused WBS 7.18 candidate runtime tests:

```text
python -m pytest nexus/mq/tests/test_candidate_runtime_identity.py nexus/mq/tests/test_candidate_runtime_lifecycle.py nexus/mq/tests/test_candidate_runtime_registry.py nexus/mq/tests/test_candidate_runtime_controller.py nexus/mq/tests/test_candidate_runtime_scheduler.py nexus/mq/tests/test_candidate_runtime_capacity.py nexus/mq/tests/test_candidate_runtime_projection.py nexus/mq/tests/test_candidate_runtime_evidence.py nexus/mq/tests/test_candidate_runtime_no_go.py
27 passed
```

Registry, heartbeat, dispatch, and Agent Access regression:

```text
python -m pytest nexus/mq/tests/test_agent_registry_conflicts.py nexus/mq/tests/test_agent_registry_persistence.py nexus/mq/tests/test_agent_registry_readiness.py nexus/mq/tests/test_agent_registry_recovery.py nexus/mq/tests/test_heartbeat_runtime.py nexus/mq/tests/test_heartbeat_registry_integration.py nexus/mq/tests/test_heartbeat_presence_ttl.py nexus/mq/tests/test_heartbeat_supervisor.py nexus/mq/tests/test_heartbeat_agent_access_projection.py nexus/mq/tests/test_operational_dispatch_eligibility.py nexus/mq/tests/test_operational_dispatch_scope.py nexus/mq/tests/test_operational_dispatch_assignment.py nexus/mq/tests/test_operational_dispatch_agent_access.py nexus/mq/tests/test_agent_access_read_model.py nexus/mq/tests/test_agent_access_evidence_export.py nexus/mq/tests/test_startup_packet_readiness.py
73 passed
```

3.5 / WBS 7.17 boundary regression:

```text
python -m pytest nexus/mq/tests/test_message_contracts.py nexus/mq/tests/test_wbs717_diagnostic_binding.py nexus/mq/tests/test_wbs717_live_send_receive_contract.py nexus/mq/tests/test_wbs717_live_transport_evidence.py
24 passed
```

Private/contract-only regression:

```text
$files = Get-ChildItem nexus\mq\tests\test_private_*.py | ForEach-Object { $_.FullName }; python -m pytest @files
45 passed
```

Full MQ suite:

```text
python -m pytest nexus/mq/tests
391 passed, 19 warnings
```

Known warnings:

- NATS dependency deprecation warnings from `nats.aio.subscription`.
- Existing pytest warnings from legacy tests returning `bool` in `test_mq_skeleton.py`.

## 8. Hygiene and Secret Scan

Diff hygiene:

```text
git diff --check
No whitespace errors.
```

Windows line-ending warnings were observed when Git touched modified/new files. No whitespace errors were reported.

Secret scan command:

```text
rg -n "(sk-|api_key=|authorization:|bearer |password=|secret=|token=|-----BEGIN)" nexus/mq handoff/evidence/2026-05-22_4_19_WBS_7_18_7_THUNDER_IMPLEMENTATION_PACKAGE.md handoff/evidence/2026-05-22_4_19_WBS_7_18_7_THUNDER_IMPLEMENTATION_REPORT_FOR_NOVA.md
```

Classification:

- scanner marker definitions are expected;
- existing and new tests contain fake `token=...` strings as negative/redaction fixtures;
- report files mention the scan regex and fixture classification;
- no real credential or secret was introduced.

## 9. Residual Risk and Review Questions

Residual risks for Nova review:

- `quarantined` was added as a registry status; confirm this is acceptable for Layer 3 conflict handling.
- `agent_registry_store.py` fake-store normalization was extended for candidate metadata; confirm no persistence contract drift is introduced.
- `candidate_runtimes` was added to `AgentAccessReadModel`; confirm downstream consumers tolerate the additive field.
- Registry DB adapter remains a scoped deferral; confirm WBS 7.18.8.1 should stay adapter-boundary-only until separately authorized.

No source-edit expansion is requested beyond Nova findings. Runtime rerun remains a separate gate.
