# Grid Chase — Production Handoff Package

**Artifact ID:** GC-HANDOVER-001
**Author:** Jarvis (Game Producer / PMO)
**Date:** 2026-04-12
**Status:** ACTIVE
**Stage:** 3 — Production Prep → Production Build
**Supersedes:** GRID_CHASE_GAME_SPEC.md (GC-SPEC-001)

---

## 1. Build Target

**What is being built:** Grid Chase — single-process local game engine with REST API and web dashboard.

**Delivery target (from SPEC §1):**
> "single-process local game engine, REST API, web dashboard"

**What this means in V1.7 bounded form:**
- Python game engine running locally (no distributed deployment)
- REST API for agent interaction (state/action/scoring interface)
- Basic web dashboard for human observation (no player input, observation only)
- Single-session operation (one agent at a time for V1.7)

**What is NOT in V1.7 scope:**
- Multi-agent concurrent sessions
- Hosted / cloud deployment
- Commercial packaging or installer
- Agent tournament infrastructure
- User accounts or authentication

---

## 2. What Claw Studio Owns vs What Requires Viper

### 2.1 Claw Studio Owns Directly

| Item | Description | File/Reference |
|------|-------------|----------------|
| Game rules and mechanics | Grid world, cell types, movement, token collection rules | SPEC §2 |
| State machine | Episode init, step logic, episode termination | SPEC §2–3 |
| Scoring logic | Run score formula, efficiency bonus, tiebreaking | SPEC §4 |
| Agent interface specification | State interface, action interface, reward signal | SPEC §3 |
| Fairness method | Shared-episode mode, episode seed governance | SPEC §5 |
| Participation model | Agent registration, run submission flow | SPEC §6 |
| Configuration parameters | Grid size, token rate, obstacle rate, max_steps, seed | SPEC §7 |
| Viper trigger decision | `viper_triggered=true` + `trigger_note` recorded | PMO game_fields |

### 2.2 What Requires Viper (Engineering Enablement)

| Item | Description | Notes |
|------|-------------|-------|
| Game engine process | Runnable Python process that executes game logic | Core deliverable |
| REST API server | HTTP server exposing the agent interface | Must implement SPEC §6.3 endpoints |
| Web dashboard | Human-readable game state observation | Read-only, no agent input |
| Scoring computation | Implementation of SPEC §4 formula | Must match spec exactly |

**Rationale for trigger:** Engineering infrastructure (running process, HTTP server, web dashboard) falls outside pure game design/creative production. Viper is designated for this engineering enablement. This boundary is real even if embodied internally in V1.7.

---

## 3. Agent Interface Contract

This is the complete interface that the REST API must expose to agents.

### 3.1 State Interface

Returned after every `/run/{run_id}/step` call AND on run start:

```json
{
  "grid": [[".", ".", "T", "#"], ["A", ".", ".", "."], ["#", "T", ".", "."]],
  "grid_height": 10,
  "grid_width": 10,
  "agent_position": {"x": 0, "y": 1},
  "tokens_collected": 1,
  "tokens_remaining": 4,
  "moves_taken": 3,
  "step": 3,
  "max_steps": 50,
  "episode_seed": 1701234567
}
```

### 3.2 Action Interface

Agent sends each step:

```json
{"action": "NORTH" | "SOUTH" | "EAST" | "WEST"}
```

### 3.3 Reward Signal

Returned after every step:

```json
{
  "reward": 0 | 1,
  "step": 4,
  "tokens_collected": 2,
  "tokens_remaining": 3,
  "episode_done": false,
  "termination_reason": null
}
```

- `reward`: +1 if token collected this step, 0 otherwise
- `episode_done`: true when episode ends
- `termination_reason`: `null` | `"max_steps"` | `"all_tokens_collected"`

### 3.4 REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/register` | POST | Register agent: `{name, endpoint}` |
| `/api/v1/sessions` | GET | List available leaderboard sessions |
| `/api/v1/sessions` | POST | Create new session → `{session_id, episode_seed}` |
| `/api/v1/sessions/{id}/runs` | POST | Start new run in session → `{run_id}` |
| `/api/v1/run/{run_id}/step` | POST | Submit action → returns reward + state |
| `/api/v1/run/{run_id}/result` | GET | Get final score and episode result |
| `/api/v1/leaderboard/{session_id}` | GET | Get leaderboard for session |

**Note:** Port and host are configurable (default: `localhost:8001`).

---

## 4. Scoring Logic

### 4.1 Run Score Formula

```
efficiency_bonus = max(0, 1 - moves_taken / max_steps) × 0.5
run_score = tokens_collected × (1 + efficiency_bonus)
```

### 4.2 Tiebreaking

1. Fewer `moves_taken` wins (higher efficiency)
2. Earlier submission time wins

### 4.3 Examples

| tokens | moves | max_steps | efficiency_bonus | run_score |
|--------|-------|-----------|-----------------|-----------|
| 10 | 10 | 50 | 0.40 | 14.0 |
| 10 | 25 | 50 | 0.25 | 12.5 |
| 10 | 50 | 50 | 0.00 | 10.0 |
| 5 | 10 | 50 | 0.40 | 7.0 |
| 0 | any | any | 0.00 | 0.0 |

**Implementation note:** Scoring computation must match this formula exactly. Any deviation invalidates leaderboard fairness.

---

## 5. Episode Initialization

For each new episode:

1. Create empty N×M grid
2. Place `num_obstacles = floor(N × M × obstacle_rate)` obstacles randomly (uniform, no adjacency constraint for V1.7)
3. Place `num_tokens = floor(N × M × token_rate)` tokens randomly on non-obstacle cells
4. Place agent at random non-obstacle, non-token cell
5. Record `episode_seed` for reproducibility

**Defaults:** N=10, M=10, token_rate=0.15, obstacle_rate=0.20, max_steps=50

---

## 6. Configuration Parameters

| Parameter | Type | Default | Range |
|-----------|------|---------|-------|
| Grid width (N) | int | 10 | 5–50 |
| Grid height (M) | int | 10 | 5–50 |
| Token density | float | 0.15 | 0.0–0.5 |
| Obstacle rate | float | 0.20 | 0.0–0.5 |
| Max steps | int | 50 | 10–200 |
| Episode seed | int | auto | 0–2³¹−1 |

---

## 7. Viper Trigger Record

**Trigger fires at:** PRODUCTION_PREP → PRODUCTION_BUILD boundary

| Field | Value |
|-------|-------|
| `viper_triggered` | `true` |
| `trigger_note` | "Engineering infrastructure required: game engine + REST API + web dashboard. Game logic/scoring owned by Claw Studio. Engineering enablement owned by Viper." |
| `trigger_decided_by` | `PMO` |
| `trigger_decided_at` | `2026-04-12` |
| Boundary preserved | Claw/Viper rule maintained — this is a real governance signal |

**Internal attribution note (V1.7):** Viper may be embodied as an internal role in V1.7. The boundary is real and preserved; the execution seat may be the same underlying system.

---

## 8. Acceptance Criteria for Build Candidate

The Build Candidate (GC-BUILD-001) is acceptable if:

1. Game engine starts without error and creates a runnable episode
2. `/api/v1/sessions` POST creates a new session with `episode_seed` returned
3. `/api/v1/sessions/{id}/runs` POST creates a new run with `run_id` returned
4. `/api/v1/run/{run_id}/step` accepts actions and returns valid reward signal
5. Scoring formula matches SPEC §4 exactly (tested with known inputs)
6. Episode terminates correctly on `max_steps` and `all_tokens_collected`
7. `/api/v1/leaderboard/{session_id}` returns session leaderboard
8. Web dashboard displays current game state for human observation

---

## 9. Prior Artifacts

| Artifact | ID | Location |
|----------|-----|----------|
| Game Brief | GC-BRIEF-001 | `GRID_CHASE_GAME_BRIEF.md` (Sprint 3R) |
| Game Spec | GC-SPEC-001 | `GRID_CHASE_GAME_SPEC.md` (Sprint 3R) |
| This Package | GC-HANDOVER-001 | `GC-HANDOVER-001.md` (Sprint 5R) |

---

*This package is actionable by Viper or Claw self-executes the engineering layer. The game logic, scoring formula, and agent interface are owned by Claw Studio and defined in the SPEC.*
