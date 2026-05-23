# Structured Task Handoff Controller Pre-Edit Package - WBS 7.19.5

Status: `READY_FOR_NOVA_REVIEW`
Owner: Thunder
Requester: Alex / Nova governance lane
Prepared: 2026-05-23 CST
Scope: Read-only pre-edit planning package for WBS `7.19.5`

## 1. Verdict

Final candidate verdict: `READY_FOR_NOVA_REVIEW`.

This package is evidence/planning only. It does not authorize source implementation, implementation branch creation, runtime start, live dispatch, private-agent invocation, broker/config/credential mutation, deploy, merge, business execution, or WBS `7.19` PASS.

## 2. Repository Baseline

Nexus checkout inspected:

| Field | Value |
|---|---|
| Repo | `D:\Projects\Nexus` |
| Remote | `origin https://github.com/Jarvis-Maverick-Bot/Nexus` |
| Target base branch inspected | `master` |
| Submitted package branch | `codex/wbs-7-19-5-pre-edit-package` |
| Upstream | `origin/master` |
| Base commit / HEAD | `9d927ac8eab2f82afe386ea530eba835cdbc4cee` |
| Merge-base with `origin/master` | `9d927ac8eab2f82afe386ea530eba835cdbc4cee` |
| Working tree | clean by `git status --porcelain=v1 -b` |
| Branch relation | `## master...origin/master` |
| Submitted package path | `handoff/evidence/STRUCTURED_TASK_HANDOFF_CONTROLLER_PRE_EDIT_PACKAGE_2026-05-23.md` |

Shared Docs mirror inspected:

| Field | Value |
|---|---|
| Repo | `D:\Nova-Jarvis-Shared-Docs` |
| Branch | `main` |
| HEAD | `ddf38f7e8fac5f2355ecc0906b03dd78828e50da` |

Commands used for baseline:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse --abbrev-ref --symbolic-full-name '@{u}'
git merge-base HEAD origin/master
git status --porcelain=v1 -b
git remote -v
git -C 'D:\Nova-Jarvis-Shared-Docs' status --short
git -C 'D:\Nova-Jarvis-Shared-Docs' branch --show-current
git -C 'D:\Nova-Jarvis-Shared-Docs' rev-parse HEAD
```

## 3. Source Authority Inputs

| Input | Path | Status |
|---|---|---|
| WBS row | `working/00-project-governance/03-pre-coding/group-a-priority/4.19-multi-channel-agent-runtime-compatibility/4_19_EXECUTION_PLAN_WBS_V0_1.md`, row `7.19.5` | Read; confirms read-only pre-edit gate is open and implementation remains blocked |
| Pre-edit request | `implementation-design/THUNDER_WBS_7_19_5_STRUCTURED_TASK_HANDOFF_CONTROLLER_PRE_EDIT_REQUEST_2026-05-23.md` | Read; minimum package requirements applied |
| Solution authority | `solution-design/STRUCTURED_TASK_HANDOFF_CONTROLLER_SOLUTION_DESIGN_V0_2.md` | Read previously and used as top-level controller authority |
| Data model | `implementation-design/jarvis/2026-05-23_4.19-wbs7.19.2-structured-task-owner-handoff-data-model_jarvis_v0.3/` | Read; model and validation tasks mapped below |
| Routing policy | `implementation-design/jarvis/2026-05-23_4.19-wbs7.19.3-decomposition-routing-policy_jarvis_v0.2/` | Read; policy, RunLedger, LLM boundary, and test plan mapped below |
| WBS 7.19.2 review | `review-evidence/nova/2026-05-23_4_19_WBS_7_19_2_JARVIS_DESIGN_PACKAGE_REVIEW_V0_3.md` | Read; confirms v0.3 approved/promoted |
| WBS 7.19.3 review | `review-evidence/nova/2026-05-23_4_19_WBS_7_19_3_JARVIS_DESIGN_PACKAGE_REVIEW_V0_2.md` | Read; confirms v0.2 approved/promoted |
| WBS 7.19.4 approval | `review-evidence/nova/2026-05-23_4_19_WBS_7_19_4_ALEX_APPROVAL.md` | Read; confirms 7.19.5 may open for Thunder read-only pre-edit package |
| Boundary standard | `../../standards/THREE_LAYER_ARCHITECTURE_BOUNDARY_STANDARD_V0_2.md` | Read previously; canonical Layer 1/2/3 naming applied |
| Review profile | `review-reference/4_19_IMPLEMENTATION_REVIEW_PROFILE_V0_1.md` | Read; invariants, historical negative cases, and regression classes applied |

## 4. Current Nexus Surface Assessment

No existing implementation for `WorkflowConstraintSet`, `TaskEnvelope`, `TaskUnit`, `DecompositionPlan`, `OwnerHandoffPacket`, `RunLedger`, `RuntimeExecutionEvent`, `ModelCallTelemetry`, or `TaskAuditRecord` was found in Nexus. Current `rg` hits for handoff-related terms are limited to existing Layer 3 message-family payloads such as `Handoff_Message`, not the WBS 7.19 Structured Task Handoff Controller.

Relevant existing surfaces:

| Existing file | Current role | WBS 7.19 relationship |
|---|---|---|
| `nexus/mq/message_contracts.py` | 3.5-style envelope/payload validation and agent-transport overlay validation | Must remain Layer 3 transport authority; WBS 7.19 must reference, not redefine, ACK/retry/timeout/DLQ semantics |
| `nexus/mq/payloads.py` | Existing message payload dataclasses, including `HandoffMessagePayload` | Do not overload with controller data-model authority unless later design explicitly chooses a 3.5 carrier binding |
| `nexus/mq/dispatch_eligibility.py` | Existing deterministic dispatch eligibility evaluator | Useful reference for fail-closed candidate filtering; not the source of Layer 1 governance truth |
| `nexus/mq/dispatch_assignment.py` | Inert assignment candidate model and validator | Useful regression surface for `assignment != business completion`; no direct mutation planned in first implementation slice |
| `nexus/mq/agent_access_read_model.py` | Read-only Agent Access projection | Must stay read-only and non-authoritative for governance truth |
| `nexus/mq/candidate_runtime_controller.py` | WBS 7.18 candidate runtime controller preflight/assignment helper | Pattern reference only; WBS 7.19 controller must be separate and must not inherit old manual-controller PASS assumptions |
| `nexus/mq/candidate_runtime_scheduler.py` | Deterministic runtime claim builder | Pattern reference for idempotency and capacity-before-claim |
| `nexus/mq/durable_state.py` | SQLite durable state with generic `phase5_durable_record` support | Planned persistence adapter can reuse existing generic durable records without schema migration |

## 5. Planned Write Set

No files are edited by this pre-edit package. The following write set is proposed only for a future WBS `7.19.6` kickoff decision and subsequent implementation gate.

### Planned source files to create

| File | Responsibility |
|---|---|
| `nexus/mq/structured_task_models.py` | Dataclasses, enums, and `to_dict` helpers for `WorkflowConstraintSet`, `WorkspaceInitializationContextPlaceholder`, `RuntimeEligibilitySnapshot`, `SourceAuthoritySet`, `TaskEnvelope`, `TaskUnit`, `DecompositionPlan`, `OwnerHandoffPacket`, `TaskAuditRecord`, `EscalationRecord`, `RuntimeExecutionEvent`, and `ModelCallTelemetry` |
| `nexus/mq/structured_task_validation.py` | Deterministic schema/source/policy validation, required-field checks, no-go preservation, owner/verifier separation, Stage 00 placeholder-only checks, redaction classification, and fail-closed error vocabulary |
| `nexus/mq/structured_task_runledger.py` | `RunLedger` transition matrix and invalid transition guard preserving dispatch/ACK/running/completed/accepted separation |
| `nexus/mq/structured_task_policy.py` | Source-authority resolver, deterministic decomposition seed builder, dependency graph validator, route candidate filtering, no-route/ambiguous-owner/ambiguous-source results, and route validation |
| `nexus/mq/structured_task_llm_advisory.py` | Bounded LLM advisory interface that accepts only deterministic source context and eligible candidate sets, stores advisory output separately, and rejects malformed/out-of-bound suggestions |
| `nexus/mq/structured_task_persistence.py` | Thin persistence adapter over `DurableStateStore.create_phase5_durable_record`, `find_phase5_durable_record`, and `list_phase5_durable_records` for WBS 7.19 records without changing SQLite schema |
| `nexus/mq/structured_task_controller.py` | Orchestration facade for intake -> validation -> optional advisory -> route validation -> packet render -> audit evidence, with default safe/off policy and no runtime dispatch side effects |

### Planned test files to create

| File | Responsibility |
|---|---|
| `nexus/mq/tests/test_structured_task_models.py` | Required fields, enum values, relationship rules, `not_business_completion`, and serialization behavior |
| `nexus/mq/tests/test_structured_task_validation.py` | Missing source, stale source hash, missing DoD/evidence/no-go, owner/verifier conflict, unapproved Stage 00 change, secret-like value rejection |
| `nexus/mq/tests/test_structured_task_runledger.py` | Full RunLedger transition matrix, invalid skips, dispatch/ACK/running separation, completed-is-not-acceptance |
| `nexus/mq/tests/test_structured_task_policy.py` | Deterministic decomposition, dependency blocks, no eligible route, ambiguous owner, ambiguous source, stale Agent Access, owner/verifier separation |
| `nexus/mq/tests/test_structured_task_llm_advisory.py` | LLM advisory receives bounded context only, cannot invent source authority, cannot add owners outside eligible set, malformed output rejected |
| `nexus/mq/tests/test_structured_task_persistence.py` | Durable phase5 record persistence, idempotent dedupe, supersession, replay by source/policy hash, no destructive rollback |
| `nexus/mq/tests/test_structured_task_controller.py` | End-to-end non-runtime controller flow through packet candidate emission, evidence-before-packet gate, audit failure block, no live dispatch |

### Planned source files to modify

No existing source file must be modified in the first planned implementation slice.

Potential future modifications if Nova/Alex require narrower integration:

| File | Reason | Default plan |
|---|---|---|
| `nexus/mq/__init__.py` | Optional package exports | Leave unchanged unless implementation style requires public exports |
| `nexus/mq/agent_access_read_model.py` | Optional projection field for structured task controller status | Leave unchanged in first slice; use separate controller evidence records |
| `nexus/mq/message_contracts.py` | Optional later carrier binding for `OwnerHandoffPacket` over `Handoff_Message` | Leave unchanged; Layer 3 semantics must not be redefined by WBS 7.19 |
| `nexus/mq/durable_state.py` | Optional dedicated tables for structured task records | Leave unchanged; use existing `phase5_durable_record` to avoid migration |

## 6. Explicit Non-Target Files

The following files/surfaces are explicit non-targets for WBS `7.19.6` first implementation slice:

- `nexus/mq/adapter_nats.py`
- `nexus/mq/live_send_receive.py`
- `nexus/mq/live_transport_evidence.py`
- `nexus/mq/listener_runtime.py`
- `nexus/mq/listener_supervisor.py`
- `nexus/mq/agent_transport_binding.py`
- `nexus/mq/message_contracts.py`, unless later review explicitly approves carrier binding tests only
- `nexus/mq/payloads.py`, unless later review explicitly approves carrier binding tests only
- `nexus/mq/dispatch_assignment.py`
- `nexus/mq/dispatch_eligibility.py`
- `nexus/mq/agent_registry*.py`
- `nexus/mq/heartbeat*.py`
- `nexus/mq/private_*`
- `config/**`
- `governance/collab/**`
- `governance/ui/**`
- `governance/data/**`
- any broker, NATS, credential, daemon, runtime, deploy, or private-agent configuration

## 7. Migration, Config, and Feature Flags

| Area | Plan |
|---|---|
| Database migration | None planned. Use existing `phase5_durable_record` generic durable record store through `structured_task_persistence.py`. |
| Config files | None planned. No changes to `config/agents.yaml`, `config/agents_uat.yaml`, `.env`, NATS URL, broker, or credential config. |
| Feature flag | In-code policy object only, default safe/off: `StructuredTaskControllerPolicy(controller_enabled=False, llm_advisory_enabled=False, live_dispatch_enabled=False, business_acceptance_enabled=False)`. No runtime/config activation. |
| Runtime startup | Not planned and explicitly blocked. |
| Live dispatch | Not planned and explicitly blocked. |
| Credential handling | Opaque refs only; no secret values in records, tests, logs, evidence, or docs. |

## 8. Requirement-To-Surface Mapping

| Approved requirement | Planned code surface | Planned tests |
|---|---|---|
| Deterministic source authority is mandatory | `structured_task_models.py`, `structured_task_validation.py`, `structured_task_policy.py` | `test_structured_task_validation.py::test_missing_source_authority_fails_closed`, `test_structured_task_policy.py::test_ambiguous_source_fails_closed` |
| WBS/gate/DoD/no-go/evidence constraints are preserved | `structured_task_models.py`, `structured_task_validation.py` | `test_structured_task_models.py::test_task_unit_requires_dod_no_go_evidence_stop_conditions`, `test_structured_task_validation.py::test_no_go_drift_is_rejected` |
| Stage 00 workspace initialization remains placeholder-only | `structured_task_models.py`, `structured_task_validation.py` | `test_structured_task_validation.py::test_unapproved_workspace_initialization_change_blocks`, `test_structured_task_validation.py::test_stage00_schema_claim_attempt_is_rejected` |
| TaskEnvelope/TaskUnit/OwnerHandoffPacket schemas match WBS 7.19.2 | `structured_task_models.py` | `test_structured_task_models.py::test_wbs7192_required_object_fields`, `test_structured_task_models.py::test_owner_handoff_packet_requires_control_fields` |
| Evidence-before-handoff packet emission | `structured_task_controller.py`, `structured_task_persistence.py`, `structured_task_validation.py` | `test_structured_task_controller.py::test_audit_write_failure_blocks_packet`, `test_structured_task_persistence.py::test_packet_records_require_audit_ref` |
| Owner/verifier separation | `structured_task_validation.py`, `structured_task_policy.py` | `test_structured_task_validation.py::test_owner_equals_verifier_blocks_without_exception`, `test_structured_task_policy.py::test_self_verifying_candidate_excluded` |
| Deterministic decomposition and dependency validation | `structured_task_policy.py` | `test_structured_task_policy.py::test_decomposition_from_approved_wbs_row`, `test_structured_task_policy.py::test_blocked_dependency_blocks_route` |
| Routing uses identity, capability, authority, readiness, freshness, capacity, channel, tools/write surfaces | `structured_task_policy.py` | `test_structured_task_policy.py::test_route_candidate_filtering`, `test_structured_task_policy.py::test_stale_agent_access_blocks` |
| No eligible route and ambiguity fail closed | `structured_task_policy.py`, `structured_task_models.py` | `test_structured_task_policy.py::test_no_eligible_route_blocks`, `test_structured_task_policy.py::test_ambiguous_owner_escalates`, `test_structured_task_policy.py::test_ambiguous_source_fails_closed` |
| Bounded LLM advisory only | `structured_task_llm_advisory.py`, `structured_task_validation.py` | `test_structured_task_llm_advisory.py::test_llm_receives_only_bounded_source_context`, `test_structured_task_llm_advisory.py::test_llm_owner_not_eligible_rejected`, `test_structured_task_llm_advisory.py::test_scope_expansion_rejected` |
| RunLedger transition policy and completion-not-acceptance | `structured_task_runledger.py`, `structured_task_models.py` | `test_structured_task_runledger.py::test_runledger_rejects_invalid_state_skip`, `test_structured_task_runledger.py::test_dispatch_ack_running_separation`, `test_structured_task_runledger.py::test_completed_is_not_acceptance` |
| Layer 3 MQ semantics preserved | `structured_task_controller.py`, tests only reference `message_contracts.py` | `test_structured_task_controller.py::test_controller_does_not_publish_or_define_transport`, regression `test_message_contracts.py` |
| Agent Access is context/read model only | `structured_task_policy.py` | `test_structured_task_policy.py::test_agent_access_snapshot_is_not_governance_authority`, regression `test_agent_access_read_model.py` |
| Durable evidence and replay/idempotency | `structured_task_persistence.py`, `structured_task_runledger.py` | `test_structured_task_persistence.py::test_replay_same_source_policy_hash_is_idempotent`, `test_structured_task_persistence.py::test_superseded_plan_preserves_prior_record` |
| Model usage telemetry cannot be agent prose | `structured_task_llm_advisory.py`, `structured_task_models.py` | `test_structured_task_llm_advisory.py::test_missing_wrapper_telemetry_is_evidence_gap_not_zero_usage` |

## 9. Planned Implementation Task Breakdown

This is a planning breakdown only. It must not be executed until WBS `7.19.6` is separately approved.

| Task | Planned change | Primary tests |
|---|---|---|
| TSK-7.19.6-001 | Add `structured_task_models.py` with dataclass object model and relationship helpers | `test_structured_task_models.py` |
| TSK-7.19.6-002 | Add deterministic schema/source/no-go/owner/verifier/Stage 00 validation | `test_structured_task_validation.py` |
| TSK-7.19.6-003 | Add RunLedger transition guard | `test_structured_task_runledger.py` |
| TSK-7.19.6-004 | Add source/decomposition/routing policy functions | `test_structured_task_policy.py` |
| TSK-7.19.6-005 | Add bounded LLM advisory wrapper and telemetry checks | `test_structured_task_llm_advisory.py` |
| TSK-7.19.6-006 | Add persistence adapter over `DurableStateStore.phase5_durable_record` | `test_structured_task_persistence.py` |
| TSK-7.19.6-007 | Add controller orchestration facade with safe/off defaults and no side effects | `test_structured_task_controller.py` |
| TSK-7.19.6-008 | Run focused and regression suite, capture evidence, and prepare implementation report for Nova | commands in Section 10 |

## 10. Command And Test Plan

All commands are planned for the future implementation gate. They were not executed as implementation validation during this pre-edit package.

### Focused WBS 7.19 tests

```powershell
python -m pytest nexus/mq/tests/test_structured_task_models.py -q
python -m pytest nexus/mq/tests/test_structured_task_validation.py -q
python -m pytest nexus/mq/tests/test_structured_task_runledger.py -q
python -m pytest nexus/mq/tests/test_structured_task_policy.py -q
python -m pytest nexus/mq/tests/test_structured_task_llm_advisory.py -q
python -m pytest nexus/mq/tests/test_structured_task_persistence.py -q
python -m pytest nexus/mq/tests/test_structured_task_controller.py -q
```

Expected result after implementation: all focused tests pass.

Expected evidence files:

- `evidence/4.19/wbs-7.19/focused_models.log`
- `evidence/4.19/wbs-7.19/focused_validation.log`
- `evidence/4.19/wbs-7.19/focused_runledger.log`
- `evidence/4.19/wbs-7.19/focused_policy.log`
- `evidence/4.19/wbs-7.19/focused_llm_advisory.log`
- `evidence/4.19/wbs-7.19/focused_persistence.log`
- `evidence/4.19/wbs-7.19/focused_controller.log`

### 4.19 regression slice

```powershell
python -m pytest nexus/mq/tests/test_message_contracts.py -q
python -m pytest nexus/mq/tests/test_dispatch_eligibility.py nexus/mq/tests/test_dispatch_assignment.py -q
python -m pytest nexus/mq/tests/test_agent_access_read_model.py nexus/mq/tests/test_agent_access_evidence_export.py -q
python -m pytest nexus/mq/tests/test_candidate_runtime_controller.py nexus/mq/tests/test_candidate_runtime_scheduler.py -q
python -m pytest nexus/mq/tests/test_phase5_durable_state_listener_supervisor.py -q
```

Expected result after implementation: pass, with no new live NATS dependency and no hidden runtime start.

Expected evidence files:

- `evidence/4.19/wbs-7.19/regression_message_contracts.log`
- `evidence/4.19/wbs-7.19/regression_dispatch.log`
- `evidence/4.19/wbs-7.19/regression_agent_access.log`
- `evidence/4.19/wbs-7.19/regression_candidate_runtime.log`
- `evidence/4.19/wbs-7.19/regression_phase5_durable_state.log`

### Broad MQ suite and hygiene

```powershell
python -m pytest nexus/mq/tests -q
git diff --check origin/master..HEAD
git status --porcelain=v1 -b
rg -n "NATS_URL|password=|secret=|token=|api_key|BEGIN PRIVATE KEY|sk-" nexus tests evidence
```

Expected result after implementation:

- MQ suite passes or live-environment skips are explicitly explained.
- `git diff --check` is clean.
- working tree contains only approved implementation/evidence files.
- secret scan has no credential values; opaque refs are allowed only where intended.

Expected evidence files:

- `evidence/4.19/wbs-7.19/full_mq_suite.log`
- `evidence/4.19/wbs-7.19/diff_check.log`
- `evidence/4.19/wbs-7.19/git_status.log`
- `evidence/4.19/wbs-7.19/secret_scan.log`

## 11. Fail-Closed Controls

- Default controller policy is disabled and has no runtime dispatch side effect.
- Missing source authority, stale source hash, ambiguous source, missing DoD, missing evidence, missing no-go scope, unapproved Stage 00 change, owner/verifier conflict, no eligible route, ambiguous owner, stale Agent Access, LLM malformed output, out-of-set owner, audit write failure, missing telemetry, or secret-like material all block packet emission.
- `completed` in RunLedger remains result-candidate state only. It cannot imply Layer 1 acceptance.
- Agent Access snapshots are operational context only. They cannot supply WBS authority, DoD, acceptance, or source truth.
- Layer 3 message, ACK, retry, timeout, DLQ, replay, broker adapter, credential, and transport semantics are referenced only through existing 3.5 surfaces.
- Rollback is version supersession and evidence preservation, not destructive deletion.

## 12. Rollback And Cleanup Plan

If future implementation is rejected before merge:

1. Preserve implementation evidence and Nova review findings.
2. Revert the implementation branch or abandon the branch; do not mutate `master` without merge approval.
3. Mark structured task records as `superseded` in evidence, not deleted.
4. Remove only generated local runtime/test artifacts that are not submitted evidence.
5. Keep no broker, credential, daemon, or config state because none should be created by this planned slice.

If partial implementation passes tests but is not accepted:

1. Keep the branch for review.
2. Record unresolved findings in the implementation report.
3. Do not start runtime, publish assignments, or claim WBS `7.19` PASS.

## 13. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Controller model becomes too broad | Scope drift into PM/governance authority | Keep Layer 1 acceptance external and default policy safe/off |
| LLM advisory becomes hidden authority | Unauthorized scope/owner/route | Store advisory output separately and post-validate every field |
| Existing Handoff_Message is confused with OwnerHandoffPacket | Layer 3 payload drift | Keep structured task objects in separate WBS 7.19 modules; no message contract changes in first slice |
| Persistence schema migration expands scope | Larger blast radius | Use existing `phase5_durable_record` generic store |
| Agent Access becomes governance truth | Authority bypass | Treat Agent Access as read-only runtime context only |
| Completed run is counted as accepted work | False WBS/business progress | RunLedger `completed` remains candidate; Layer 1 acceptance is separate |
| Runtime/dispatch starts during implementation | No-go breach | No adapter/live modules targeted; tests assert no publish/subscribe/runtime-start side effects |
| Secret value appears in evidence | Security breach | Secret scan, redaction validation, opaque refs only |

## 14. No-Go Confirmation

Confirmed not performed by this pre-edit package:

- no source code edit;
- no implementation branch creation;
- no runtime start;
- no live dispatch;
- no private-agent invocation;
- no broker/config/credential mutation;
- no deploy;
- no merge;
- no business execution;
- no WBS `7.19` PASS claim;
- no Layer 3 ACK/retry/timeout/DLQ/broker semantic redefinition;
- no Agent Access governance-truth mutation;
- no LLM output authority over deterministic gates.

## 15. Deviations And Blockers

Deviations from the pre-edit request: none.

Current blockers before source implementation:

- WBS `7.19.6` implementation kickoff is not yet approved by Alex.
- Nova review of this WBS `7.19.5` package is required before any implementation kickoff decision.

## 16. Review Request

Submitted for Nova review as WBS `7.19.5` read-only pre-edit evidence.

Requested Nova decision:

- `ACCEPT_PRE_EDIT_PACKAGE_AND_PREPARE_WBS_7.19.6_DECISION`, or
- `REQUEST_CHANGES`, with explicit required corrections.
