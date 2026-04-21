# collab_config.json — Configuration Guide

## Rule

**Local config files are never uploaded to Git.** The repo only holds `collab_config.json.template`. Each machine (Jarvis, Nova) maintains its own local `collab_config.json` with real values. If local config is accidentally staged, unstage it immediately.

## File Purpose

`governance/collab/collab_config.json` holds all runtime configuration for the NATS collaboration system. No hardcoded values in code.

---

## Template: `collab_config.json.template`

```json
{
  "my_id": "",
  "sender_id": "",
  "target_id": "",
  "nats_url": "",
  "subjects": {
    "command": "",
    "ack": "",
    "event": "",
    "notify": ""
  },
  "poll_interval": 30,
  "heartbeat_interval": 60,
  "shutdown_grace": 30,
  "data_dir": null,
  "protocol_version": "0.2"
}
```

---

## Field Definitions

| Field | Who Uses It | Meaning |
|-------|------------|---------|
| `my_id` | daemon (`CollabDaemon`) | Identity of this agent. Messages addressed to this ID are processed. |
| `sender_id` | `phase2_test_sender.py` | Identity of the message sender (who am I). |
| `target_id` | `phase2_test_sender.py` | Identity of the message recipient (who am I talking to). |
| `nats_url` | Both daemon and sender | Full URL of the NATS server, e.g. `nats://192.168.31.64:4222` |
| `subjects.command` | Both | NATS subject for command messages, e.g. `gov.collab.command` |
| `subjects.ack` | Both | NATS subject for ACK messages, e.g. `gov.collab.ack` |
| `subjects.event` | Both | NATS subject for event messages, e.g. `gov.collab.event` |
| `subjects.notify` | Both | NATS subject for notification messages, e.g. `gov.collab.notify` |
| `poll_interval` | daemon worker | Seconds between worker recovery sweeps. Default: 30. |
| `heartbeat_interval` | daemon heartbeat | Seconds between heartbeat logs. Default: 60. |
| `shutdown_grace` | daemon stop | Seconds to wait before force-kill on shutdown. Default: 30. |
| `data_dir` | daemon | Path to data directory. `null` = default `governance/data/`. |
| `protocol_version` | Both | Protocol version. Default: `0.2`. |

---

## Example: Jarvis Local Config

```json
{
  "my_id": "jarvis",
  "sender_id": "jarvis",
  "target_id": "nova",
  "nats_url": "nats://192.168.31.64:4222",
  "subjects": {
    "command": "gov.collab.command",
    "ack": "gov.collab.ack",
    "event": "gov.collab.event",
    "notify": "gov.collab.notify"
  },
  "poll_interval": 30,
  "heartbeat_interval": 60,
  "shutdown_grace": 30,
  "data_dir": null,
  "protocol_version": "0.2"
}
```

## Example: Nova Local Config

```json
{
  "my_id": "nova",
  "sender_id": "nova",
  "target_id": "jarvis",
  "nats_url": "nats://192.168.31.64:4222",
  "subjects": {
    "command": "gov.collab.command",
    "ack": "gov.collab.ack",
    "event": "gov.collab.event",
    "notify": "gov.collab.notify"
  },
  "poll_interval": 30,
  "heartbeat_interval": 60,
  "shutdown_grace": 30,
  "data_dir": null,
  "protocol_version": "0.2"
}
```

---

## Setup Steps

**For every new machine:**

1. Copy `collab_config.json.template` to `collab_config.json`
2. Fill in all fields with values for that machine
3. Never commit `collab_config.json` to Git

**NATS server must be running before starting the daemon or sender.**

Standard NATS start:
```bash
nats-server -a 0.0.0.0 -p 4222
```

Verify connectivity:
```bash
nc -zv 127.0.0.1 4222
```

---

## Files in This Directory

| File | Committed to Git? | Purpose |
|------|-------------------|---------|
| `collab_config.json.template` | YES | Blank template with field documentation |
| `collab_config.json` | NO | Local runtime config (machine-specific) |
| `collab_daemon.py` | YES | Daemon process |
| `handler.py` | YES | Message handler + skill registry |
| `envelope.py` | YES | Message envelope schema |
| `state_store.py` | YES | Durable state store |
| `phase2_test_sender.py` | YES | Test sender script |

---

## How NATS Subjects Work

`subjects` in config defines the routing topics. All agents must use the same subjects to communicate.

- `gov.collab.command` — command messages (review_request, decision_proposal, etc.)
- `gov.collab.ack` — ACK responses (received, processed)
- `gov.collab.event` — workflow events
- `gov.collab.notify` — notifications

All values come from config. No hardcoded subject strings in code.