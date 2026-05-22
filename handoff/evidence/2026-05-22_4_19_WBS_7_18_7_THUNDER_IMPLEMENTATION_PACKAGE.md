# WBS 7.18.7 Thunder Implementation Package

Status: `IMPLEMENTATION_PACKAGE_RETURNED / SOURCE EDITS COMPLETE / READY_FOR_NOVA_REVIEW`
Owner: Thunder
Date: 2026-05-22 CST
Nexus branch: `codex/wbs-7-18-candidate-agent-persistent-runtime-enablement`

## 1. Base and Branch Evidence

- Repo: `D:\Projects\Nexus`
- Stacked base branch at kickoff: `codex/wbs-7-17-live-mq-send-receive-correction`
- Base HEAD at fresh check: `94254924871d473bbf0f59d31b795c838804316a`
- Merge-base with `origin/master`: `8f5bd1ec18a9f1211434f2bf0f3d3200a476bb87`
- Implementation branch created: `codex/wbs-7-18-candidate-agent-persistent-runtime-enablement`
- Shared Docs policy correction: `D:\Nova-Jarvis-Shared-Docs` is read-only reference material only. This package is stored in the Nexus implementation branch.

## 2. Scope Summary

Implemented additive Layer 3 candidate runtime compatibility surfaces:

- generic candidate profile/runtime identity validation;
- adapter-boundary candidate runtime registry wrapper over existing registry service/fake store;
- lifecycle fail-closed checks;
- capacity-before-claim contract;
- deterministic controller/scheduler claim candidate builder;
- read-only candidate runtime Agent Access projection;
- non-secret candidate runtime evidence shape.

No 3.5 live transport semantics were changed. WBS 7.17 files were regression-only.

## 3. Changed Files

Existing files modified:

- `nexus/mq/agent_registry.py`
- `nexus/mq/agent_registry_store.py`
- `nexus/mq/agent_access_read_model.py`

New source files:

- `nexus/mq/candidate_runtime_identity.py`
- `nexus/mq/candidate_runtime_lifecycle.py`
- `nexus/mq/candidate_runtime_capacity.py`
- `nexus/mq/candidate_runtime_registry.py`
- `nexus/mq/candidate_runtime_controller.py`
- `nexus/mq/candidate_runtime_scheduler.py`
- `nexus/mq/candidate_runtime_projection.py`
- `nexus/mq/candidate_runtime_evidence.py`

New tests:

- `nexus/mq/tests/test_candidate_runtime_identity.py`
- `nexus/mq/tests/test_candidate_runtime_lifecycle.py`
- `nexus/mq/tests/test_candidate_runtime_capacity.py`
- `nexus/mq/tests/test_candidate_runtime_registry.py`
- `nexus/mq/tests/test_candidate_runtime_controller.py`
- `nexus/mq/tests/test_candidate_runtime_scheduler.py`
- `nexus/mq/tests/test_candidate_runtime_projection.py`
- `nexus/mq/tests/test_candidate_runtime_evidence.py`
- `nexus/mq/tests/test_candidate_runtime_no_go.py`

## 4. Design Mapping

| Requirement | Implementation |
|---|---|
| Generic candidate-agent, no Jarvis hardcoding | `CandidateAgentProfile`, `CandidateRuntimeIdentity`; tests cover Jarvis and synthetic future candidate. |
| Runtime identity tuple | Identity fields include runtime instance, type/provider/version, host, owner, profile ref, source refs, trust/credential refs. |
| Registry adapter boundary only | `CandidateRuntimeRegistry` wraps `AgentRegistryService`; no production DB/backend added. |
| Duplicate active runtime fail-closed | Conflict returns `DUPLICATE_ACTIVE_CANDIDATE_RUNTIME` and quarantines existing local test row. |
| Startup/readiness/lifecycle fail-closed | `evaluate_candidate_runtime_lifecycle(...)`. |
| Capacity-before-claim | `CandidateRuntimeCapacitySnapshot` and `evaluate_capacity_before_claim(...)`. |
| Deterministic scheduler | `build_candidate_runtime_claim(...)`, no LLM dispatch dependency. |
| Business execution blocked | Business assignment requests return `BUSINESS_DISPATCH_NOT_AUTHORIZED`; claims set `business_execution_allowed=False`. |
| Agent Access read-only projection | `build_candidate_runtime_projection(...)` and `candidate_runtimes` extension in `AgentAccessReadModel`. |
| No-secret evidence | `candidate_runtime_evidence.py` validates with existing secret scanner. |

## 5. Test Evidence

Focused WBS 7.18 tests:

```text
python -m pytest nexus/mq/tests/test_candidate_runtime_identity.py nexus/mq/tests/test_candidate_runtime_lifecycle.py nexus/mq/tests/test_candidate_runtime_registry.py nexus/mq/tests/test_candidate_runtime_controller.py nexus/mq/tests/test_candidate_runtime_scheduler.py nexus/mq/tests/test_candidate_runtime_capacity.py nexus/mq/tests/test_candidate_runtime_projection.py nexus/mq/tests/test_candidate_runtime_evidence.py nexus/mq/tests/test_candidate_runtime_no_go.py
27 passed
```

Registry/heartbeat/dispatch/Agent Access regression:

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

Warnings observed:

- NATS dependency deprecation warnings from `nats.aio.subscription`.
- Existing pytest warnings for legacy tests returning `bool` in `test_mq_skeleton.py`.

## 6. Hygiene and Secret Scan

Diff hygiene:

```text
git diff --check
No whitespace errors.
Windows warning only: LF will be replaced by CRLF when Git touches three modified files.
```

Secret scan command:

```text
rg -n "(sk-|api_key=|authorization:|bearer |password=|secret=|token=|-----BEGIN)" nexus/mq
```

Result classification:

- Hits in scanner marker definitions are expected.
- Hits in tests are negative/redaction fixtures, including new candidate runtime tests using fake `token=...` values to prove rejection/redaction.
- No real secret value was introduced.

## 7. No-Go Confirmation

Confirmed not performed:

- no runtime/listener/daemon start;
- no persistent live registration;
- no assignment publish;
- no private-agent invocation;
- no broker/server/config/credential mutation;
- no business execution;
- no Layer 1 MQ responsibility moved into 4.19;
- no Layer 2 workflow/task semantics moved into 4.19;
- no WBS `7.18` PASS claim.

## 8. Audit Notes

- WBS 7.18.7 is intentionally stacked on WBS 7.17 correction branch as accepted by Alex's forwarded instruction.
- `WBS_7_18_8_1_REGISTRY_DB_ADAPTER_SCOPE` remains `ADAPTER_BOUNDARY_ONLY_SCOPED_DEFERRAL`; no concrete production DB backend was added.
- Existing `AgentRegistryRecord` received optional candidate runtime metadata fields. They are backward-compatible defaults and are included in normalized fake-store rows for readback/audit.
- `AgentAccessReadModel` now accepts `candidate_runtime_projection` into a new `candidate_runtimes` read-only collection.
- 3.5 transport files were not edited.
