# Collaboration Flow Specification v0.2

> **Supersedes:** v0.1
> **Date:** 2026-04-21
> **Purpose:** Define complete Foundation Create flow with contract-driven runtime

---

## Three Deliverables

### 1. Runtime Contract Map (`runtime_contract_map.py`)

Source of truth for every message_type. Each contract defines:

| Field | Meaning |
|-------|---------|
| `executor` | Which agent handles this step |
| `current_owner` | Business workflow owner at this step |
| `mandatory_output` | Business message that MUST be produced |
| `allowed_results` | Valid result values for this step |
| `completion_condition` | What counts as "done" — NOT ACK |
| `notify_policy` | Who must be notified, when, and via what channel |
| `auto_continue` | Whether handler should auto-submit next step |

**Key rule:** ACK is never the completion condition. Only a business message constitutes completion.

---

### 2. Doctrine Bridge (`doctrine_bridge.py`)

Loads doctrine files from shared drive into structured snapshots:

```
DOCTRINE_PATHS:
  v2_0_foundation_baseline → V2_0_FOUNDATION_V0_2.md
  v2_0_scope               → V2_0_SCOPE_V0_2.md
  v2_0_prd                 → V2_0_PRD_V0_2.md
```

At handler initialization, `load_doctrine_snapshot(doctrine_loading_set)` produces a `LoadedDoctrine` with all content parsed and available to the executor.

Executor judges draft against doctrine snapshot, not hardcoded rules.

---

### 3. Foundation Create Revised Sequence

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ FOUNDATION CREATE — FULL SEQUENCE                                           │
└─────────────────────────────────────────────────────────────────────────────┘

ALEX          NOVA AGENT         NATS              JARVIS DAEMON         ALEX (TG)
 │                │                │                     │                  │
 │ "Start V2.0    │                │                     │                  │
 │  Foundation    │                │                     │                  │
 │  Create"        │                │                     │                  │
 │───────────────▶│                │                     │                  │
 │                │                │                     │                  │
 │                │ [HANDLER]                      [HANDLER]               │
 │                │ start_foundation_create handler                     │
 │                │  • state: open / nova / awaiting_foundation_draft     │
 │                │  • contract: mandatory_output = review_request       │
 │                │    (not ACK)                                         │
 │                │                │                     │                  │
 │                │── gov.collab ──────────────────────────▶│              │
 │                │  command: review_request                 │              │
 │                │  payload: {artifact_path, review_scope}              │
 │                │                                                     │
 │                │                │◀──── received ACK ─────│              │
 │                │                │     (transport only)    │              │
 │                │                │                     [HANDLER]         │
 │                │                │    review_request handler              │
 │                │                │     • executor = jarvis               │
 │                │                │     • contract.mandatory_output        │
 │                │                │       = review_response                │
 │                │                │     • load doctrine snapshot          │
 │                │                │     • execute review inline            │
 │                │                │     • judgment = approved | revision   │
 │                │                │      _required | blocked               │
 │                │                │                     │                  │
 │                │                │◀── gov.collab ──────│              │
 │                │                │  command: review_response             │
 │                │                │  payload: {review_result, judgment}    │
 │                │                │                     │                  │
 │◀─────────── Telegram ───────────────────────────────────────────────│
 │                │                │                     │                  │
 │  "Foundation   │                │                     │                  │
 │   Review       │                │                     │                  │
 │   Complete"    │                │                     │                  │
 │                │                │◀──── received ACK ─────│              │
 │                │ [HANDLER]    │                     │                  │
 │                │ review_response handler              │                  │
 │                │  • if approved: send complete       │                  │
 │                │  • if revision: await new draft      │                  │
 │                │  • if blocked: notify Alex           │                  │
 │                │                │                     │                  │
 │                │── gov.collab ──────────────────────────▶│              │
 │                │  command: complete                   │              │
 │                │                                                     │
 │                │                │◀──── received ACK ─────│              │
 │                │                │                     [HANDLER]         │
 │                │                │    complete handler                    │
 │                │                │     • state: completed                 │
 │                │                │     • Telegram: "Foundation Complete"   │
 │                │                │                     │                  │
 │◀─────────── Telegram ───────────────────────────────────────────────│
 │                │                │                     │                  │
```

---

## Channel Topology

| Channel | Use |
|---------|-----|
| `gov.collab.command` | All business messages (command, response, complete, exit) |
| `gov.collab.ack` | Transport-layer ACK only: `received` or `processed` |
| `gov.collab.event` | Workflow events for logging (not business responses) |
| Telegram | Human notifications from Jarvis only |

**Rule: ACK is transport-layer only. Business completion is a command-channel message.**

---

## ACK Discipline

```
Agent A sends message X to Agent B via gov.collab.command
  → Agent B receives X
    → Sends [received ACK] via gov.collab.ack to A
    → Runs handler for X
    → Handler MUST produce: mandatory_output (a command-channel message)
    → Sends [processed ACK] via gov.collab.ack to A
  → Agent B sends mandatory_output Y to Agent A via gov.collab.command
  → Agent A receives Y
    → Sends [received ACK] via gov.collab.ack to B
```

**No ACK = No receive claim. No mandatory_output = Incomplete step.**

---

## Step Contracts (Runtime Contract Map)

### `start_foundation_create`
| Field | Value |
|-------|-------|
| executor | nova |
| current_owner | nova |
| mandatory_output | `review_request` |
| completion_condition | `review_request` delivered to jarvis on gov.collab.command |
| notify_policy | none |
| auto_continue | True |

### `review_request`
| Field | Value |
|-------|-------|
| executor | jarvis |
| current_owner | jarvis |
| mandatory_output | `review_response` |
| allowed_results | `approved`, `revision_required`, `blocked` |
| completion_condition | `review_response` delivered to nova on gov.collab.command |
| notify_policy | Telegram to Alex on complete |
| auto_continue | True |

### `review_response`
| Field | Value |
|-------|-------|
| executor | nova |
| current_owner | nova |
| mandatory_output | `complete` (on approved) or new draft (on revision) |
| allowed_results | `approved`, `revision_required`, `blocked` |
| completion_condition | `complete` delivered OR new `review_request` submitted |
| notify_policy | Telegram to Alex for all results |
| auto_continue | False |

### `complete`
| Field | Value |
|-------|-------|
| executor | jarvis |
| current_owner | nova |
| mandatory_output | none (terminal) |
| completion_condition | state = completed |
| notify_policy | Telegram to Alex |
| auto_continue | False |

### `exit`
| Field | Value |
|-------|-------|
| executor | jarvis |
| current_owner | nova |
| mandatory_output | none |
| completion_condition | state = exited + Telegram notified |
| notify_policy | Telegram to Alex immediately |
| auto_continue | False |

---

## Observable Results

| Step | Observable Result |
|------|-------------------|
| start_foundation_create | State: `open`, `pending=awaiting_foundation_draft` |
| review_request emitted | `review_request` on NATS command channel to jarvis |
| review_response received | Telegram to Alex with result |
| complete | Telegram: "Foundation Create — COMPLETE" |
| exit | Telegram: "Foundation Create — EXITED" |

---

## What Changed from v0.1

1. Added `runtime_contract_map.py` — machine-readable contract registry
2. Added `doctrine_bridge.py` — doctrine loading as structured snapshots
3. Handler consults contract to determine mandatory_output (not hardcoded)
4. Worker sweep explicitly skips steps where handler owns execution
5. Exit handler now has explicit Telegram notification (per contract)

---

## Files

```
governance/collab/
  COLLAB_FLOW_SPEC.md       ← this file
  runtime_contract_map.py    ← step contract registry
  doctrine_bridge.py         ← doctrine → runtime contract loader
  handler.py                 ← contract-driven handlers
  review_executor.py         ← doctrine-aware executor
  collab_daemon.py           ← worker guard per contract
```
