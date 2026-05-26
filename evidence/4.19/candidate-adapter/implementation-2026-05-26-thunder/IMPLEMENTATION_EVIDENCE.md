# 4.19 Candidate Agent Adapter Implementation Evidence

Owner: Thunder
Requester: Alex, via Nova review gate
Date: 2026-05-26
Branch: `codex/4.19-candidate-agent-adapter-api-cli`
Initial implementation code commit: `2a2afd9f46f896ac0d2200fb69dd9d86377e320f`
Nova REQUEST_CHANGES correction code commit: `63047b1667cf65e0f240ab7dca7a2b70c50ea591`
Nova redaction correction code commit: `76dcdbf22bb7165f596797e8677711a81d7a2f2f`
Nova API-output redaction correction code commit: `d839676696d36e601b080f36d4e67022095f34c3`
Source base: `origin/master@f27a7bcd3ecc720ee28c676fb9f0ecb0ddbe2a24`
Merge base: `f27a7bcd3ecc720ee28c676fb9f0ecb0ddbe2a24`
Final evidence package head: provided by the Thunder handoff because a commit cannot self-reference its own SHA without changing that SHA.
Verdict: READY_FOR_NOVA_REVIEW

## Authority Inputs

- Approved pre-edit branch: `codex/4.19-candidate-agent-adapter-pre-edit`
- Corrected pre-edit head: `be64bd2b053a59858f63ffff022bdc55e9cd8b08`
- Pre-edit package input: `D:\Projects\Nexus\evidence\4.19\candidate-adapter\pre-edit-2026-05-26-thunder\`
- Solution Design: `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\4.19-multi-channel-agent-runtime-compatibility\solution-design\MULTI_CHANNEL_AGENT_RUNTIME_COMPATIBILITY_MODEL_V0_1.md`
- Implementation Design: `D:\Nova-Jarvis-Shared-Docs\working\00-project-governance\03-pre-coding\group-a-priority\4.19-multi-channel-agent-runtime-compatibility\implementation-design\MULTI_CHANNEL_AGENT_RUNTIME_COMPATIBILITY_IMPLEMENTATION_DESIGN_V0_1.md`

## Implementation Summary

Implemented the approved Candidate Agent Adapter source-only API/CLI surface:

- `connect`
- `register`
- `ready`
- `heartbeat`
- `await-assignment`
- `ack`
- `progress`
- `evidence`
- `result`
- `drain`
- `offline`

The CLI surface is intentionally limited to:

```powershell
python -m nexus.mq.candidate_adapter_cli ...
```

No global `nexus candidate` executable or packaging entrypoint was added.

The implementation uses deterministic injected providers for assignment intake and lifecycle lease lookup in tests. It does not start a runtime, connect to NATS, mutate broker/firewall/config/credentials, invoke private agents, deploy, merge, execute business work, or claim PASS.

## Request Changes Corrections

Nova blocking findings corrected:

- Assignment intake and ACK now fail closed unless the session has registration, startup packet, readiness evidence, heartbeat freshness, and an allowed active lifecycle state.
- `await_assignment` rejects connected-only, registered-only, ready-without-heartbeat, stale, draining, and offline sessions before returning a normal assignment.
- `ack_assignment` rejects connected-only, registered-only, ready-without-heartbeat, stale, draining, and offline sessions before emitting intake ACK.
- CLI ACK now has a deterministic source-only contract: `python -m nexus.mq.candidate_adapter_cli ack --assignment-json <path> --lease-json <path> --session <path>`.
- CLI ACK stores active assignment state so later CLI `progress`, `evidence`, and `result` commands can complete against the same session file.
- `SHA256SUMS.txt` is regenerated with relative paths and LF-normalized clean-checkout hashes.

Nova redaction blocker corrected:

- Candidate-facing payload sanitization now recursively strips raw internal transport/message-package keys at every dict/list depth before assignment events or candidate action events are returned.
- The raw-key denylist now includes top-level and nested transport/message-package variants such as `raw_envelope`, `nats_subject`, `reply_to`, `headers`, `message_package`, `raw_message`, `transport_headers`, `transport_metadata`, `nats_headers`, and broker/internal envelope aliases.
- Focused negative tests cover nested raw-key removal for `assignment_available`, `progress`, `evidence`, `result_candidate`, `assignment_rejected`, `draining`, and `offline` payloads.
- Evidence-writer coverage verifies nested raw internal keys do not appear in written candidate event JSON.
- Manifest coverage convention: `SHA256SUMS.txt` and `sha256-verify.txt` are intentionally excluded from `SHA256SUMS.txt` because one is self-referential and the other is generated verification output for that manifest. All other files in the implementation evidence package are covered.

Nova API-output redaction blocker corrected:

- `await_assignment()` now returns a candidate-safe normalized assignment view in `CandidateAdapterOperationResult.payload["assignment"]`.
- The normalized assignment view preserves ACK-required assignment/control metadata: assignment id, idempotency key, lifecycle decision id, reservation lease id, runtime identity, protocol version, and no-go scope.
- Raw transport/message-package payload internals are recursively stripped from the assignment branch before API return or CLI JSON emission.
- Focused API and CLI negative tests prove no raw internal keys appear anywhere in the full serialized `await_assignment` result, including the `assignment` branch and companion `event` branch.

## Changed File Summary

See `changed-files.txt` for the complete branch-level file list.

Implementation source:

- 9 new `nexus/mq/candidate_adapter_*.py` modules.

Focused tests:

- 5 new `nexus/mq/tests/test_candidate_adapter_*.py` files.

Evidence:

- This evidence package under `evidence/4.19/candidate-adapter/implementation-2026-05-26-thunder/`.

## Verification Outputs

Command output files:

- `git-diff-check.txt`
- `compileall-nexus-mq.txt`
- `focused-pytest.txt`
- `full-mq-pytest.txt`
- `secret-scan.txt`
- `sha256-verify.txt`

Observed verification:

- Focused Candidate Adapter pytest slice: `61 passed`.
- Full MQ test suite: `554 passed, 19 warnings`.
- `python -m compileall -q nexus/mq`: exit code 0.
- `git diff --check`: clean.
- High-confidence secret scan: no matches.
- SHA256 manifest verification: all OK.

## Known Gaps And Boundaries

- No runtime, MiniTest, UAT, deploy, merge, broker/firewall/config/credential mutation, private-agent invocation, business execution, or PASS claim was performed.
- The in-memory broker/lifecycle providers are deterministic test doubles only.
- Distributed UAT broker profile/firewall/auth preflight remains gated by later Nova/Alex runtime authorization.
- No resident-controller, NATS adapter, private-agent runner, production config, or Shared Docs files were edited.
- `result_candidate` events are candidate evidence only and are not business acceptance.

## Final Candidate Verdict

READY_FOR_NOVA_REVIEW
