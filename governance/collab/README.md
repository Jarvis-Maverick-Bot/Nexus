# Governance Collaboration Module

`governance/collab` contains collaboration protocol experiments, workflow records, and helper scripts for governed handoff between runtime participants.

This module is a governance-support surface. It is not the Runtime Lifecycle Controller, the Dispatch Controller, or the Candidate Agent Adapter.

## Scope

- message envelope and ACK contracts for collaboration records;
- local state and message-log helpers under `governance/data/`;
- workflow capture, review, and foundation-execution helpers;
- NATS-style listener and daemon experiments;
- protocol notes for collaboration flow and runtime contract mapping.

## Key Files

- `envelope.py` - Collaboration message envelope schema.
- `state_store.py` - JSON/JSONL-backed collaboration state and message log helpers.
- `handler.py` - Inbound command handling and ACK generation.
- `listener.py` - Listener entry point for collaboration messages.
- `collab_daemon.py` - Collaboration daemon experiment with guarded workflow execution.
- `runtime_contract_map.py` - Mapping between collaboration workflows and runtime contract boundaries.
- `COLLAB_FLOW_SPEC.md` - Collaboration protocol flow notes.
- `PHASE2_OPERATION_GUIDE.md` - Historical operation guide for the phase 2 collaboration path.
- `CONFIG_README.md` - Configuration notes.

## State Files

The default repo-local state location is:

```text
governance/data/collab_state.json
governance/data/collab_messages.jsonl
```

Local deployments may override paths through configuration. Do not hard-code private host paths, credentials, or operator-specific shares in public README content.

## Boundaries

- Collaboration ACKs and workflow events are evidence records, not production release approval.
- Listener or daemon operation does not authorize live runtime promotion, deploy, credential mutation, or config enablement.
- Runtime registration, readiness, heartbeat, eligibility, and leases belong to the Runtime Lifecycle Controller.
- Assignment intent, assignment publish requests, duplicate replay handling, and dispatch evidence belong to the Dispatch Controller.
