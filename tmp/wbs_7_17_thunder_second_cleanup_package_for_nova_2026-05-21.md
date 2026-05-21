# Thunder WBS 7.17 Second Cleanup Package for Nova Re-Review

Status: `THUNDER_WBS_7_17_SECOND_CLEANUP_PACKAGE_RETURNED / ADVERSARIAL_FAIL_CLOSED_GAPS_ADDRESSED / RUNTIME RERUN STILL BLOCKED`

## Review Context

- Repo: `D:\Projects\Nexus`
- Branch: `codex/wbs-7-17-live-mq-send-receive-correction`
- Prior cleanup HEAD: `20b5c317647da59797572f89f49246a8a1c4c202`
- Nova re-review verdict addressed: `REQUEST CHANGES / NOT READY FOR RUNTIME RERUN`

## Blocking Findings Addressed

### 1. Adapter fallback after invalid routing

Finding:

- `MqAdapterStub` / `MqAdapterNats` could still fallback after `route_execution_envelope_dict(...)` returned invalid, allowing an `agent_transport` envelope with invalid subject to land on a broad fallback subject.

Fix:

- `MqAdapterStub._resolve_subject(...)` now raises `ValueError("AGENT_TRANSPORT_ROUTING_INVALID: ...")` when an `agent_transport` envelope fails routing.
- `MqAdapterNats._resolve_subject(...)` now raises the same error for invalid `agent_transport` routing.
- `MqAdapterNats._publish_impl(...)` resolves/validates subject before opening broker connection, so invalid `agent_transport` envelopes fail locally before any broker action.

Regression:

- `test_adapters_fail_closed_on_invalid_agent_transport_route`

### 2. Command/review `reply_to_subject` routing gap

Finding:

- `route_execution_envelope_dict(...)` rejected broad explicit `subject` but did not fail closed when command/review used a broad `reply_to_subject`.

Fix:

- `_route_agent_transport_envelope_dict(...)` validates `reply_to_subject` for `Command_Message` and `Review_Task` before returning an inbox route.
- Broad reply routes such as `agent.thunder.callbacks` now fail routing with `AGENT_TRANSPORT_SUBJECT_OUT_OF_SCOPE`.

Regression:

- `test_agent_transport_command_rejects_broad_reply_to_subject_in_routing`

## Changed Files

- `nexus/mq/adapter.py`
- `nexus/mq/adapter_nats.py`
- `nexus/mq/protocol_routing.py`
- `nexus/mq/tests/test_wbs717_diagnostic_binding.py`
- `tmp/wbs_7_17_thunder_second_cleanup_package_for_nova_2026-05-21.md`

## Test Evidence

- `python -m py_compile nexus/mq/adapter.py nexus/mq/adapter_nats.py nexus/mq/protocol_routing.py`
  - Result: pass

- `python -m pytest nexus/mq/tests/test_message_contracts.py nexus/mq/tests/test_wbs717_diagnostic_binding.py nexus/mq/tests/test_wbs717_live_transport_evidence.py nexus/mq/tests/test_wbs717_live_send_receive_contract.py`
  - Result: `24 passed`

- MQ suite excluding live NATS adapter:
  - Command: `$tests = Get-ChildItem -Path nexus/mq/tests -Filter 'test_*.py' | Where-Object { $_.Name -ne 'test_adapter_nats.py' } | ForEach-Object { $_.FullName }; python -m pytest @tests`
  - Result: `354 passed, 13 warnings`

Not run as passing evidence:

- Full local MQ suite including live NATS adapter, because the current local environment has known NATS auth/no-server failures.

## Scans

- Production-source WBS hardcoding scan:
  - Pattern: `AGENT_TRANSPORT_DEFAULT_NO_GO_SCOPE|agent_transport_diagnostic|WBS 7.17|wbs_7_17|wbs717|WBS717|nexus\.wbs7_17`
  - Scope: `nexus/mq`, excluding tests
  - Result: no matches

- Secret scan over changed files:
  - Result: no matches

- `git diff --check`
  - Result: no whitespace errors; Windows line-ending normalization warnings only.

## No-Go Confirmation

Still not performed:

- Runtime/listener/daemon start
- Assignment publish
- Private-agent invocation
- Business execution
- Broker config mutation
- WBS 7.17 PASS marking
- WBS 7.18 work

## Re-Review Request

Please re-review the fail-closed behavior for:

- invalid agent_transport routing at adapter publish/resolve boundaries
- command/review broad `reply_to_subject` rejection
- preservation of generic 3.5 MQ transport semantics
