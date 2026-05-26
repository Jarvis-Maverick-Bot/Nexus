# Candidate Adapter Implementation Risk Notes

## Preserved Boundaries

- No runtime start, MiniTest, UAT, deploy, merge, broker/firewall/config/credential mutation, private-agent invocation, business execution, or PASS claim.
- No resident-controller, NATS adapter, private-agent runner, production config, or Shared Docs edits.
- CLI scope is `python -m nexus.mq.candidate_adapter_cli ...`; no global `nexus candidate` executable was introduced.
- Result output is `result_candidate` only and does not represent business acceptance.

## Controls Implemented

- Broker endpoint validation rejects distributed-UAT OpenClaw `4222` and Jarvis-side loopback unless explicitly local-only.
- Subject policy rejects broad or unauthorized assignment subjects.
- Assignment intake is blocked unless registration, startup packet, readiness evidence, heartbeat freshness, and an active lifecycle state are present.
- Assignment ACK requires assignment id, idempotency key, lifecycle decision id, reservation lease id, matching runtime identity, matching protocol, matching no-go scope, and an active non-expired non-revoked lease.
- CLI ACK requires deterministic `--lease-json` input and does not invent lifecycle truth from config.
- Duplicate assignment id with a conflicting idempotency key is rejected.
- Event mapper strips raw transport/internal keys before exposing assignment payloads to candidate callers.
- Session state is file-backed, schema-versioned, and does not persist credential material.
- Tests use injected in-memory broker and lifecycle providers only.

## Residual Review Notes

- The first implementation intentionally does not wire a real NATS client or runtime broker loop.
- A later runtime gate must approve distributed UAT broker topology, firewall, auth, and environment variables before any live run.
- YAML profile loading remains deferred; JSON profile loading is implemented for the first typed contract without adding dependencies.
- The evidence writer is available for candidate event file refs, but API tests rely on deterministic event payloads and do not create live runtime evidence.
- Evidence checksums are generated with relative filenames and LF-normalized content so Nova can verify them from a clean checkout.
