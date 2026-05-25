# WBS 7.19.14.5B Resident Controller Patch Evidence

Owner: Thunder
Requester: Alex / Nova
Date: 2026-05-26 Asia/Shanghai
Repo: `D:\Projects\Nexus`
Branch: `codex/wbs-7-19-14-5b-start-once-live-loop`
Candidate verdict: `5B_PATCH_READY_FOR_NOVA_REVIEW`

## Baseline

Required baseline:

```text
Nexus master: 6286a0a0c200646a2c8c86b508e96faa250a1d36
```

Observed before patch:

```text
HEAD/origin-master/merge-base were pinned to 6286a0a0c200646a2c8c86b508e96faa250a1d36 before creating the patch branch.
```

Local working-tree deviation before patch:

```text
Existing untracked resident-controller evidence packages only.
No unrelated source files were modified.
```

## Patch Summary

Implemented the accepted canonical command:

```powershell
python -m nexus.mq.resident_controller.cli start-once --config <path>
```

Source surfaces:

```text
nexus/mq/resident_controller/live_loop.py
nexus/mq/resident_controller/cli.py
nexus/mq/resident_controller/config.py
nexus/mq/tests/test_resident_controller_live_loop.py
nexus/mq/tests/test_resident_controller_config.py
```

Behavior added:

```text
Fail-closed bounded_uat authorization gate.
Env-ref-only NATS URL/auth resolution.
Default port 4222 rejection for 5B.
Run-scoped subscription expansion.
Allowed publish only for controller.init, assignment, assignment.duplicate_replay, and drain subjects.
Registration/readiness/heartbeat observation.
Bounded non-business assignment publish.
ACK/progress/evidence/result_candidate recorded only as candidate evidence.
Drain/offline observation before clean stop.
Machine-readable status and evidence package output.
```

No new primary CLI command was added. `run` and `run-live-loop` remain non-canonical and are not part of this patch.

## Thunder Local 5B Runtime Proof

UAT-only environment:

```powershell
$env:NEXUS_RESIDENT_CONTROLLER_NATS_URL = "nats://127.0.0.1:7422"
$env:NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF = "local-uat-auth-ref"
```

Broker:

```text
nats-server v2.14.1, local throwaway process, 127.0.0.1:7422, stopped after proof.
No production broker or 4222 port used.
```

Cleanup note:

```text
Post-run process audit found the pre-existing Windows local test NATS service listening on 4222.
It was not used by this proof; the proof used only 127.0.0.1:7422.
The temporary 7422 process was stopped. The existing local test service was left unchanged.
```

Command:

```powershell
python -m nexus.mq.resident_controller.cli start-once --config evidence/4.19/wbs-7.19.14/resident-controller/5B-patch-proof-2026-05-26/uat-only-resident-controller.yaml --output evidence/4.19/wbs-7.19.14/resident-controller/5B-patch-proof-2026-05-26/start-once-live.json
```

Result:

```text
EXIT:0
accepted=true
daemon_started=true
service_state=offline
evidence_package.review_ready=true
```

Observed runtime events include:

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

Runtime evidence:

```text
evidence/4.19/wbs-7.19.14/resident-controller/5B-patch-proof-2026-05-26/runtime-evidence/
```

## Verification

```text
focused resident tests: 36 passed
non-live regression package: 55 passed
compileall resident package: EXIT:0
git diff --check: EXIT:0
high-confidence secret scan: no matches
evidence SHA256SUMS verification: pass
```

## No-Go Confirmation

No production broker was used. No production port 4222 assumption was used. No production business dispatch was sent. No private agent was invoked. No credentials were exposed in reports. No broker/server/config/credential mutation was performed. No 5C, full WBS 7.19.14.5 PASS, 4.19 PASS, deploy, merge, or runtime promotion is claimed.

## Deviations And Blockers

Deviation:

```text
Thunder local proof uses a synthetic local participant. This supports 5B only and does not replace Jarvis-participating 5C evidence.
```

Deviation:

```text
A post-run cleanup check initially saw process name nats-server and attempted process stop before identifying it as the pre-existing Windows local test NATS service on 4222. The stop attempt was denied by Windows; no service state, config, credential, or broker data was changed.
```

Blockers:

```text
None for Nova source review of the 5B patch.
```
