# Nova Reproduction Runbook: WBS 7.19.14.5B Resident Controller Patch

Expected verdict if reproduction matches Thunder: `5B_PATCH_READY_FOR_NOVA_REVIEW`

## Preconditions

Use branch:

```text
codex/wbs-7-19-14-5b-start-once-live-loop
```

Do not use production NATS, port 4222, production credentials, private agents, or business dispatch.

## Local-Only Environment

Use an isolated broker port:

```powershell
$env:NEXUS_RESIDENT_CONTROLLER_NATS_URL = "nats://127.0.0.1:7422"
$env:NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF = "local-uat-auth-ref"
```

## Start Throwaway NATS

Use any local `nats-server` binary and bind only to 127.0.0.1:7422:

```powershell
nats-server -p 7422 -a 127.0.0.1 -js
```

Thunder used a locally downloaded `nats-server` v2.14.1 release binary in the evidence tools directory. The binary itself is not required as source authority.

## Start Synthetic 5B Participant

From repo root in a second shell:

```powershell
python evidence/4.19/wbs-7.19.14/resident-controller/5B-patch-proof-2026-05-26/synthetic_participant.py
```

This participant is local-only and non-business. It publishes registration/readiness/heartbeat and responds to controller init, assignment, and drain with candidate evidence events.

## Run Canonical Controller Command

From repo root in a third shell:

```powershell
python -m nexus.mq.resident_controller.cli start-once --config evidence/4.19/wbs-7.19.14/resident-controller/5B-patch-proof-2026-05-26/uat-only-resident-controller.yaml --output evidence/4.19/wbs-7.19.14/resident-controller/5B-patch-proof-2026-05-26/start-once-live.nova.json
```

Expected:

```text
exit 0
accepted=true
daemon_started=true
service_state=offline
status_snapshot.final_acceptance=false
status_snapshot.wbs_pass=false
evidence_package.review_ready=true
```

Expected record types:

```text
route_readiness
controller_init_published
registration_observed
readiness_observed
heartbeat_observed
bounded_assignment_published
ack_candidate_observed
progress_candidate_observed
evidence_candidate_observed
result_candidate_observed
drain_published
offline_observed
drain_offline
```

## Focused Checks

```powershell
python -m pytest nexus/mq/tests/test_resident_controller_config.py nexus/mq/tests/test_resident_controller_subject_policy.py nexus/mq/tests/test_resident_controller_observer_dispatcher.py nexus/mq/tests/test_resident_controller_evidence_recovery.py nexus/mq/tests/test_resident_controller_launchd.py nexus/mq/tests/test_resident_controller_cli_service.py nexus/mq/tests/test_resident_controller_live_loop.py -q
python -m pytest nexus/mq/tests/test_structured_task_models.py nexus/mq/tests/test_structured_task_validation.py nexus/mq/tests/test_structured_task_policy.py nexus/mq/tests/test_structured_task_runledger.py nexus/mq/tests/test_structured_task_persistence.py nexus/mq/tests/test_structured_task_controller.py nexus/mq/tests/test_structured_task_llm_advisory.py nexus/mq/tests/test_message_contracts.py nexus/mq/tests/test_durable_state.py -q
python -m compileall nexus\mq\resident_controller
git diff --check
```

Expected:

```text
focused resident tests pass
non-live regressions pass
compileall exits 0
git diff --check exits 0
```

## Cleanup

Stop the synthetic participant if still running, then stop the throwaway `nats-server` process.

Unset local-only env vars:

```powershell
Remove-Item Env:\NEXUS_RESIDENT_CONTROLLER_NATS_URL -ErrorAction SilentlyContinue
Remove-Item Env:\NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF -ErrorAction SilentlyContinue
```

## Known Limits

This proves 5B Thunder-local resident-controller live-loop behavior with a synthetic participant. It does not prove Jarvis-participating 5C, production readiness, full WBS 7.19.14.5 PASS, 4.19 PASS, or final acceptance.
