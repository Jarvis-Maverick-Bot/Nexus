# WBS 7.19.14.3 Resident Controller Implementation Report

Owner: Thunder
Requester: Alex
Reviewer: Nova
Date: 2026-05-25 CST
Repo: D:\Projects\Nexus
Branch: codex/wbs-7-19-14-3-resident-controller
Base commit: bb241891a97057891d498b12f912a37d46c0657b
Merge-base with origin/master: bb241891a97057891d498b12f912a37d46c0657b
Source implementation commit: e8b61174efb1ce56479aa5179c236b1b9c519097
Review cleanup commit: 785814b11db347f83af0071649c145ea4c0d8229
Second review cleanup commit: f1a2066eec4fae210d25dad9bc419291d996cbf0
Candidate verdict: READY_FOR_NOVA_REVIEW

## Authority Inputs

- D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\4.19-multi-channel-agent-runtime-compatibility\4_19_EXECUTION_PLAN_WBS_V0_1.md
- D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\4.19-multi-channel-agent-runtime-compatibility\solution-design\RESIDENT_CONTROLLER_SERVICE_PACKAGE_SOLUTION_DESIGN_ADDENDUM_V0_1.md
- D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\4.19-multi-channel-agent-runtime-compatibility\implementation-design\jarvis\2026-05-25_4_19_WBS_7_19_14_2_RESIDENT_CONTROLLER_SERVICE_PACKAGE_JARVIS_IMPL_DESIGN_V0_2\
- D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\4.19-multi-channel-agent-runtime-compatibility\review-evidence\nova\2026-05-25_4_19_WBS_7_19_14_2_RESIDENT_CONTROLLER_SERVICE_PACKAGE_NOVA_REVIEW_V0_2.md
- D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\4.19-multi-channel-agent-runtime-compatibility\review-evidence\nova\2026-05-25_4_19_WBS_7_19_14_3_ALEX_IMPLEMENTATION_KICKOFF.md

## Implemented Source Surfaces

- nexus/mq/resident_controller/config.py
  - Config validation, fail-closed unsafe policy rejection, refs-only redaction, deterministic config hash.
- nexus/mq/resident_controller/dispatcher.py
  - WBS 7.19.14 run-scoped subject policy, bounded non-business dispatch decision, duplicate suppression.
- nexus/mq/resident_controller/observer.py
  - Registry/readiness/heartbeat observation and stale runtime ineligibility.
- nexus/mq/resident_controller/evidence.py
  - Run-scoped evidence records, manifest, checksums, secret-scan result file, verdict report builder.
- nexus/mq/resident_controller/recovery.py
  - Restart recovery classification before replay.
- nexus/mq/resident_controller/service.py
  - Default-off service start decision, source-only route readiness evaluation, operational status snapshot, local drain/offline evidence record.
- nexus/mq/resident_controller/cli.py
  - Source-only CLI command surface: validate-config, status, start-once, drain, recover, build-evidence-package.
- config/resident_controller.example.yaml
  - Safe example config with refs only and disabled launch mode.
- packaging/launchd/com.nexus.resident-controller.example.plist
  - Disabled/default-off launchd template only.

## Focused Tests

- nexus/mq/tests/test_resident_controller_config.py
- nexus/mq/tests/test_resident_controller_subject_policy.py
- nexus/mq/tests/test_resident_controller_observer_dispatcher.py
- nexus/mq/tests/test_resident_controller_evidence_recovery.py
- nexus/mq/tests/test_resident_controller_cli_service.py
- nexus/mq/tests/test_resident_controller_launchd.py

Coverage includes default-off behavior, unsafe config rejection, deterministic config hash, exact subject policy matching, stale runtime ineligibility, non-business dispatch guard, duplicate suppression, evidence manifest/checksums, secret-scan blocking, restart replay classification, drain/offline local evidence, launchd default-off template, and UAT authorization gate.

## Request Changes Closure

Nova review `REQUEST_CHANGES` at Shared Docs commit `f43f263` listed four blockers. Cleanup status:

- CLI/service placeholder: closed by adding file-backed `validate-config`, machine-readable `status`, local `drain`, checkpoint `recover`, local evidence-package build, and source-only route readiness evaluation with evidence records.
- Evidence SHA256SUMS mismatch: closed by regenerating evidence after cleanup and calculating final checksums from staged Git index/blob content before committing the evidence package.
- Config hash nondeterministic: closed by removing `redacted_at` from the redacted snapshot used for hashing and adding a deterministic hash test.
- Publish subject allowlist overmatch: closed by exact-segment wildcard matching and a negative test for extra subject segments.

Nova rereview at Shared Docs commit `a0ab996` listed two remaining blockers. Second cleanup status:

- CLI `start-once` unwired: closed by adding `start-once --config <json|yaml> --broker-readiness <json> --output <json>` source-only route-readiness evaluation. It returns route readiness JSON with `daemon_started=false`; it does not connect to broker or start a daemon.
- Committed YAML example not accepted by `validate-config`: closed by loading `.yaml` / `.yml` through `yaml.safe_load`; `config/resident_controller.example.yaml` is covered by a focused CLI test.

## Verification Evidence

Evidence directory:

`evidence/4.19/wbs-7.19.14/resident-controller/wbs-7-19-14-3-implementation/`

| Log | Scope | Result |
| --- | --- | --- |
| focused_resident_controller.log | Resident controller focused tests | 29 passed |
| regression_dispatch_message.log | Dispatch eligibility, operational assignment, message contracts | 24 passed |
| regression_candidate_runtime.log | Candidate runtime regression set | 27 passed |
| regression_structured_task.log | Structured task controller regression set | 36 passed |
| compile_resident_controller.log | compileall resident controller package | exit 0 |
| source_diff_check.log | git diff base..HEAD --check | exit 0 |
| runtime_posture_scan.log | no live NATS/process/install patterns | exit 0 |
| secret_scan_changed_files.log | high-confidence secret scan across changed/evidence files | exit 0 |
| git_status.log | branch status after source commit | branch ahead with evidence only |

## Changed File Summary

Source commits e8b61174efb1ce56479aa5179c236b1b9c519097, 785814b11db347f83af0071649c145ea4c0d8229, and f1a2066eec4fae210d25dad9bc419291d996cbf0 add/update:

- config/resident_controller.example.yaml
- nexus/mq/resident_controller/__init__.py
- nexus/mq/resident_controller/cli.py
- nexus/mq/resident_controller/config.py
- nexus/mq/resident_controller/dispatcher.py
- nexus/mq/resident_controller/evidence.py
- nexus/mq/resident_controller/observer.py
- nexus/mq/resident_controller/recovery.py
- nexus/mq/resident_controller/service.py
- nexus/mq/tests/test_resident_controller_cli_service.py
- nexus/mq/tests/test_resident_controller_config.py
- nexus/mq/tests/test_resident_controller_evidence_recovery.py
- nexus/mq/tests/test_resident_controller_launchd.py
- nexus/mq/tests/test_resident_controller_observer_dispatcher.py
- nexus/mq/tests/test_resident_controller_subject_policy.py
- packaging/launchd/com.nexus.resident-controller.example.plist

## Runtime Posture

- No resident daemon was installed, enabled, or started.
- No WBS 7.19.14.5 UAT was run.
- No broker/server/config/credential mutation was performed.
- No live production dispatch, business execution, deploy, merge to master, runtime promotion, private-agent invocation, WBS PASS, or final acceptance was performed.
- Launchd artifact is a disabled/default-off example template only.
- CLI `start-once`, `drain`, and `recover` remain gated/source-only in this implementation package and do not start live runtime.

## Evidence Package Integrity

This implementation evidence package includes:

- command logs;
- this implementation report;
- manifest.json;
- SHA256SUMS;
- secret_scan_changed_files.log.

Checksums were generated after logs and report creation. The secret scan log reports exit 0 and no high-confidence secret findings.

## Deviations and Blockers

Deviations: none from WBS 7.19.14.3 source-only implementation scope.

Blockers: none for Nova source review.

Still blocked outside this candidate: resident service install/start, WBS 7.19.14.5 UAT, live dispatch, broker/config/credential mutation, deployment, merge to master, runtime promotion, private-agent invocation, WBS 7.19.14 PASS, WBS 7.19 PASS, and final acceptance.
