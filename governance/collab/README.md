# NATS Collaboration Module — Nova Side

## Files

- `envelope.py` — Message envelope schema (message_id, collab_id, from, to, artifact_path, timestamp)
- `state_store.py` — Durable collab state (JSON) + message log (JSONL append-only)
- `handler.py` — Processes inbound commands, emits ACKs, updates state
- `listener.py` — Standing listener (long-lived process)
- `__init__.py` — Package init

## Running the listener

```bash
cd /Users/alex/Nova-Jarvis-Shared/working/01-projects/Nexus/V2.0/collab_module
/Users/alex/.openclaw/tools/nats-venv39/bin/python3 listener.py nova
```

## Subjects (4 separate)

- `gov.collab.command` — workflow-driving messages
- `gov.collab.ack` — acknowledgments (received/processed)
- `gov.collab.event` — state transitions (future)
- `gov.collab.notify` — Alex notifications (future)

## Message envelope (v0.2)

```json
{
  "message_id": "msg-xxx",
  "collab_id": "collab-v2-foundation-001",
  "message_type": "review_request",
  "protocol_version": "0.2",
  "from": "nova",
  "to": "jarvis",
  "artifact_type": "scope",
  "artifact_path": "\\\\192.168.31.124\\Nova-Jarvis-Shared\\working\\Nexus\\V2.0\\V2_0_SCOPE_V0_1.md",
  "payload": {},
  "summary": "Please review...",
  "timestamp": "2026-04-16T22:00:00+08:00"
}
```

## ACK envelope

```json
{
  "message_id": "ack-xxx",
  "ack_for": "msg-xxx",
  "collab_id": "collab-v2-foundation-001",
  "from": "jarvis",
  "to": "nova",
  "status": "received",
  "result": "review_started",
  "protocol_version": "0.2",
  "timestamp": "2026-04-16T22:00:01+08:00"
}
```

## State store

- `governance/data/collab_state.json` — current collab states
- `governance/data/collab_messages.jsonl` — append-only message log

State store is on Jarvis side (D:\Projects\gov_langgraph\governance\data\). Nova side is write-only log for her own visibility.
