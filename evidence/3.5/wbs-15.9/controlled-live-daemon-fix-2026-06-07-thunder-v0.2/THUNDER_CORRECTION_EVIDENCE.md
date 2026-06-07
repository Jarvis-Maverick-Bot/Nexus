# Thunder WBS 15.9 Controlled-Live Daemon Correction Evidence - v0.2

Date: 2026-06-07
Owner: Thunder
Requester: Alex / Nova
Repo path: `D:\Projects\Nexus_wbs15_9_controlled_live_daemon`
Branch: `codex/wbs-15-9-controlled-live-daemon`
Base reviewed head: `be3a7ff2858ab8ba37a625828082c113241ba544`
Candidate verdict: `THUNDER_REVISED_IMPL_PACKAGE_READY_FOR_JARVIS_PRE_REVIEW`

## Review Authority

- Nova early review: `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\3.5-workflow-runtime-mq-architecture\review-evidence\nova\2026-06-07_3_5_WBS_15_9_CONTROLLED_LIVE_DAEMON_FIX_NOVA_REVIEW.md`
- Shared Docs review commit: `b5c0060 Review 3.5 controlled live daemon fix`
- Flow after resubmission: Thunder revise -> Jarvis engineering pre-review -> Nova final review -> possible G6 rerun authorization.

## Corrections

1. Missing controlled-live delivery now fails closed.
   - `CONTROLLED_LIVE_DELIVERY_NOT_OBSERVED` returns `accepted=false`.
   - CLI/status derives `blocked=true`, `daemon_started=false`, `cycles_completed=0`, and `block_reason=CONTROLLED_LIVE_DELIVERY_NOT_OBSERVED`.
   - Added negative runtime and CLI tests for publish success + ACK success + `consume` returns `None`.

2. Controlled UAT routing is run-scoped.
   - `controlled_3_5_uat` explicit test subjects are valid only under `nexus.3_5.test.3_5_wbs15_9_g6_20260607.*`.
   - `nexus.3_5.test.other_scope.*` now returns `UNAUTHORIZED_CONTROLLED_3_5_UAT_SUBJECT_SCOPE`.
   - Added negative route test for out-of-scope test subject.

## Changed Files

- `nexus/mq/foundation_daemon_runtime.py`
- `nexus/mq/protocol_routing.py`
- `nexus/mq/tests/test_foundation_daemon_controlled_live.py`
- `evidence/3.5/wbs-15.9/controlled-live-daemon-fix-2026-06-07-thunder-v0.2/THUNDER_CORRECTION_EVIDENCE.md`

## Red Test Evidence

Command:

```text
python -m pytest -q nexus/mq/tests/test_foundation_daemon_controlled_live.py
```

Pre-fix result after adding Nova regression tests:

```text
3 failed, 13 passed in 0.43s
```

Failures matched Nova findings:

- missing delivery returned `accepted=True`;
- CLI returned `blocked=False`;
- `nexus.3_5.test.other_scope.inbox` routed as valid.

## Verification

Controlled-live regression suite:

```text
python -m pytest -q nexus/mq/tests/test_foundation_daemon_controlled_live.py
16 passed in 0.35s
```

Focused daemon/endpoint suite:

```text
python -m pytest -q nexus/mq/tests/test_foundation_daemon_config.py nexus/mq/tests/test_foundation_daemon_packaging.py nexus/mq/tests/test_foundation_daemon_runtime.py nexus/mq/tests/test_thin_endpoint_contract.py nexus/mq/tests/test_foundation_daemon_controlled_live.py
47 passed in 1.74s
```

Diff check:

```text
git diff --check
exit 0; CRLF warnings only
```

Compile:

```text
python -m compileall -q nexus/mq
exit 0
```

Safe CLI smoke:

```text
python -m nexus.mq.foundation_daemon validate-config --config config/mq/foundation_daemon.example.yaml
exit 0; valid=true

python -m nexus.mq.foundation_daemon validate-config --config config/mq/foundation_daemon.controlled-live.example.yaml
exit 0; valid=true

python -m nexus.mq.foundation_daemon readiness --config config/mq/foundation_daemon.controlled-live.example.yaml
exit 1; controlled_live_authorized=true; controlled_live_ready=false; overall_ready=false

python -m nexus.mq.foundation_daemon run --config config/mq/foundation_daemon.example.yaml
exit 1; blocked=true; block_reason=LIVE_DAEMON_RUN_NOT_AUTHORIZED_FOR_SOURCE_GATE

python -m nexus.mq.foundation_daemon drain --config config/mq/foundation_daemon.controlled-live.example.yaml --timeout 10
exit 0; cleanup_evidenced=true; offline_ready=true

python -m nexus.mq.foundation_daemon stop --config config/mq/foundation_daemon.controlled-live.example.yaml --timeout 10
exit 0; cleanup_evidenced=true; offline=true
```

No-go scan:

```text
rg -n "127\.0\.0\.1:4222|production route|PRIVATE_AGENT_INVOCATION|BUSINESS_DISPATCH|secret-ref://|password|token|api_key|credential|nexus\.3_5\.test\.other_scope" nexus\mq config\mq evidence\3.5\wbs-15.9\controlled-live-daemon-fix-2026-06-07-thunder-v0.1 -S --glob "!**/__pycache__/**"
exit 0; findings are expected pre-existing source-only defaults, blocked-route constants, placeholders, and negative-test fixtures.
```

## Boundaries

- No production route used.
- No OpenClaw live NATS `127.0.0.1:4222` route used.
- No private-agent invocation.
- No business dispatch.
- No install/start/UAT.
- No credential mutation or exposure.
- No WBS 15.9 acceptance, G6 PASS, G7 acceptance, G8 unblocked, or 3.5 complete claim.

## Remaining Gate

This is a revised source package only. It is ready for Jarvis engineering pre-review before Nova final review and any possible G6 rerun authorization.
