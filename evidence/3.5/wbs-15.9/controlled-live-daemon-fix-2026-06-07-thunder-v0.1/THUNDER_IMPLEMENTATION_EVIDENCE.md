# Thunder Implementation Evidence - WBS 15.9 Controlled Live Daemon Fix

Date: 2026-06-07
Owner: Thunder
Requester: Alex / Nova
Branch: `codex/wbs-15-9-controlled-live-daemon`
Base: `origin/master` at `99db1c4c931efc29f35c83d3dab6d0225ae87d2f`
Shared Docs authority head: `fa0ab0d8602fa666bb9ed0bf2ad154ab6f855baf`
Candidate verdict: `THUNDER_IMPL_PACKAGE_READY_FOR_JARVIS_REVIEW`

This evidence report is part of the source package commit. Use the final
Thunder handoff for the exact pushed branch head hash.

## Authority Inputs

- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\3.5-workflow-runtime-mq-architecture\3_5_COMPLETE_ACCEPTANCE_PATH_2026_06_07.md`
- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\3.5-workflow-runtime-mq-architecture\3_5_G7_LIVE_DAEMON_BLOCKER_RESOLUTION_PACKET_2026_06_07.md`
- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\3.5-workflow-runtime-mq-architecture\solution-design\subtopics\3_5_CONTROLLED_LIVE_DAEMON_MODE_ADDENDUM_V0_1.md`
- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\3.5-workflow-runtime-mq-architecture\implementation-design\3_5_WORKFLOW_RUNTIME_MQ_ARCHITECTURE_IMPLEMENTATION_DESIGN_V0_1.md`
- `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\3.5-workflow-runtime-mq-architecture\implementation-design\subtopics\3_5_CONTROLLED_LIVE_DAEMON_MODE_IMPLEMENTATION_UPDATE_PLAN_V0_1.md`

## Scope Implemented

- Added explicit `controlled_live` config authorization.
- Kept source-only/default-off run behavior blocked without controlled-live authority.
- Restricted controlled-live authorization to `nats://127.0.0.1:7422`, run scope `3_5_wbs15_9_g6_20260607`, exact test-scoped subjects, run-scoped state/evidence DSNs, `business_dispatch_enabled=false`, and `broker_setup_enabled=false`.
- Added controlled-live status/readiness fields.
- Added bounded diagnostic run path with injected-adapter tests and NATS adapter construction for later rerun only.
- Added evidence/state-before-ACK, duplicate suppression, retry/DLQ/recovery, and cleanup proof tests.
- Added controlled-live example config for rerun preparation: `config/mq/foundation_daemon.controlled-live.example.yaml`.

## Changed Files

- `config/mq/foundation_daemon.controlled-live.example.yaml`
- `nexus/mq/adapter_nats.py`
- `nexus/mq/foundation_daemon.py`
- `nexus/mq/foundation_daemon_config.py`
- `nexus/mq/foundation_daemon_lifecycle.py`
- `nexus/mq/foundation_daemon_runtime.py`
- `nexus/mq/foundation_daemon_status.py`
- `nexus/mq/protocol_routing.py`
- `nexus/mq/tests/test_foundation_daemon_config.py`
- `nexus/mq/tests/test_foundation_daemon_controlled_live.py`
- `evidence/3.5/wbs-15.9/controlled-live-daemon-fix-2026-06-07-thunder-v0.1/THUNDER_IMPLEMENTATION_EVIDENCE.md`

## Verification Commands

```text
python -m pytest -q nexus/mq/tests/test_foundation_daemon_config.py nexus/mq/tests/test_foundation_daemon_packaging.py nexus/mq/tests/test_foundation_daemon_runtime.py nexus/mq/tests/test_thin_endpoint_contract.py
baseline result before source changes: 30 passed in 1.39s
```

```text
python -m pytest -q nexus/mq/tests/test_foundation_daemon_controlled_live.py
red result before implementation: 9 failed, 3 passed
green result after implementation: 13 passed in 0.36s
```

```text
python -m pytest -q nexus/mq/tests/test_foundation_daemon_config.py nexus/mq/tests/test_foundation_daemon_packaging.py nexus/mq/tests/test_foundation_daemon_runtime.py nexus/mq/tests/test_thin_endpoint_contract.py nexus/mq/tests/test_foundation_daemon_controlled_live.py
final result: 44 passed in 1.72s
```

```text
git diff --check
result: pass, no whitespace errors
```

```text
python -m compileall -q nexus/mq
result: pass
```

```text
python -m nexus.mq.foundation_daemon validate-config --config config/mq/foundation_daemon.example.yaml
result: exit 0, valid=true, source_only/default_off config remains accepted
```

```text
python -m nexus.mq.foundation_daemon validate-config --config config/mq/foundation_daemon.controlled-live.example.yaml
result: exit 0, valid=true, controlled_live config accepted for local-test route only
```

```text
python -m nexus.mq.foundation_daemon readiness --config config/mq/foundation_daemon.controlled-live.example.yaml
result: expected nonzero in Thunder source-only environment; controlled_live_authorized=true, controlled_live_ready=false, broker_ready=false, jetstream_ready=false, consumer_ready=false
```

```text
python -m nexus.mq.foundation_daemon run --config config/mq/foundation_daemon.example.yaml
result: expected nonzero source-only block, block_reason=LIVE_DAEMON_RUN_NOT_AUTHORIZED_FOR_SOURCE_GATE
```

```text
python -m nexus.mq.foundation_daemon drain --config config/mq/foundation_daemon.controlled-live.example.yaml --timeout 10
result: exit 0, controlled_live=true, cleanup_evidenced=true, offline_ready=true
```

```text
python -m nexus.mq.foundation_daemon stop --config config/mq/foundation_daemon.controlled-live.example.yaml --timeout 10
result: exit 0, controlled_live=true, cleanup_evidenced=true, offline=true
```

## No-Go Compliance

- No production route used.
- No OpenClaw live NATS `127.0.0.1:4222` used.
- No live broker route was contacted by Thunder verification.
- No broker/config/credential mutation performed.
- No private-agent invocation.
- No business dispatch.
- No install/start/enable/UAT.
- No WBS 15.9 accepted claim.
- No G6 PASS claim.
- No 3.5 `complete_for_scope` claim.

## Remaining Boundary

This package is a source implementation candidate for Jarvis engineering
pre-review. Rerun G6 is still required after package review/authorization. The
controlled-live `run` path with a real NATS broker was not executed by Thunder
because that would cross the live-route boundary in this implementation package
task.
