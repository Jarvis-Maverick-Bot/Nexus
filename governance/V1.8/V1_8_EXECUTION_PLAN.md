# V1.8 Execution Plan

**Version:** 1.4  
**Date:** 2026-04-14  
**Last Updated:** M1-R1, M1-R2, M2-R1, M2-R2 completed (4/10 sprints)  
**Game:** Grid Escape  
**Objective:** Deliver the first real AI-native game through the Claw Studio + Viper operating model, CLI-first, with PMO Event Routing

---

## 1. Scope Traceability Overview

Every sprint task maps to one or more Scope Functions (F-scale from V1_8_SCOPE.md). No task exists without a Function root. Functions that are out-of-scope are explicitly excluded.

**Function reference prefix key:**
- F1.x = First AI-native game delivery proof
- F2.x = Agent game interaction via standardized CLI
- F3.x = PMO Smart Agent CLI-native operating path
- F4.x = Thin oversight / governance UI
- F5.x = PMO Event Routing
- F6.x = Bounded PMO command/control loop
- F7.x = Claw Studio Agent seats/components
- F8.x = Real Claw ↔ Viper handoff and return path
- F9.x = Validation and acceptance evidence
- F10.x = Delivery-grade artifact chain
- F11.x = Structured delivery decomposition model

---

## 2. Sprint-to-Function Map

| Sprint | Functions Targeted | Primary Goal |
|--------|-------------------|--------------|
| M1-R1 | F1.1.1–F1.2.4, F2.1.1–F2.2.5, F2.3.1–F2.3.3, F9.1.1, F10.1.1–10.1.2 | Grid Escape engine + CLI working |
| M1-R2 | F1.3.1–F1.3.4, F2.3.1–F2.3.3, F9.1.2 | Real Agent gameplay proof |
| M2-R1 | F3.1.1–F3.1.3, F3.2.1–F3.2.6, F9.1.3, F10.1.3 | PMO CLI surface delivered |
| M2-R2 | F3.3.1–F3.3.3, F9.1.3, F10.2.2 | PMO CLI integration proof |
| M3-R1 | F5.1.1–F5.3.4, F6.3.1–F6.3.3 | PMO Event Routing core |
| M3-R2 | F6.1.1–F6.3.3, F9.1.4 | Bounded command/control loop |
| M4-R1 | F7.1.1–F7.4.5, F9.2.1–F9.2.3 | Claw Studio Agent seats |
| M4-R2 | F4.1.1–F4.3.3, F9.2.1–F9.2.3 | Thin governance UI |
| M4-R3 | F8.1.1–F8.3.3, F10.2.3 | Real Claw ↔ Viper handoff |
| M4-R4 | F9.1.1–F9.3.3, F10.1.1–F10.3.3, F11.2.1–F11.2.3 | Validation evidence + delivery package |

---

## 3. Milestone 1 — Grid Escape Core Delivery

### Sprint M1-R1 — Grid Escape Engine + CLI Surface
**Functions:** F1.1.1, F1.1.3, F1.1.5, F1.2.1–F1.2.4, F2.1.1–F2.2.5, F2.3.1–F2.3.3, F9.1.1, F10.1.1–F10.1.2
**Duration:** 2 days
**Exit gate:** Game completable via CLI without error

#### Tasks

**Task 1.1 — Grid data model** (F1.1.1, F1.1.3)
- Define grid as N×M 2D array
- Cell type enum: WALL, OPEN, START, EXIT, AGENT
- Grid seed → deterministic generation
- BFS path verification per grid

**DoD:**
- [ ] Grid class accepts width, height, seed; produces identical cells on repeated instantiation with same seed
- [ ] CellType enum has all 5 types; cell_at() returns WALL for out-of-bounds coordinates
- [ ] BFS compute_optimal_path() returns ≥ 0 for each starter grid; returns -1 for unsolvable grid

**Verification:** `python -m pytest grid_escape/tests/test_pathfinding.py -v` passes

**Task 1.2 — Grid rendering** (F1.1.3, F2.1.1)
- ASCII renderer outputting `#/.S/E/A/*`
- `look` command returns current grid state
- Agent position reflected as `A` after first move

**DoD:**
- [ ] `look` command outputs ASCII grid matching grid dimensions
- [ ] Agent visible as `A` at current position after any move
- [ ] All cell types render as correct symbols (#, ., S, E, A)

**Verification:** Manual `echo 'look' | python grid_escape.py --grid ge-001` outputs valid grid

**Task 1.3 — Movement engine** (F1.1.3, F2.1.4, F2.2.2, F2.2.5)
- `move <dir>` with direction aliases (n/north, s/south, e/east, w/west)
- Boundary and wall collision → `BLOCKED`
- State update: agent position, visited trail
- Step counter increment

**DoD:**
- [ ] All 8 direction aliases (north/n, south/s, east/e, west/w and full names) are accepted
- [ ] Move into WALL or out-of-bounds returns `BLOCKED` with no state change
- [ ] Valid move updates agent_pos, increments step_count, appends to visited
- [ ] `python -m pytest grid_escape/tests/test_movement.py -v` passes

**Verification:** `echo -e 'move north\nmove south' | python grid_escape.py --grid ge-001` shows BLOCKED for wall collision

**Task 1.4 — Game commands** (F2.1.1–F2.1.4, F2.2.1–F2.2.5)
- `look` → full grid render
- `move <dir>` → move or error
- `status` → step count + state + position
- `restart` → grid reset, step reset
- `quit` → final output, session end

**DoD:**
- [ ] All 5 commands (`look`, `move`, `status`, `restart`, `quit`) are recognized
- [ ] Unknown command returns `UNKNOWN COMMAND` (not crash)
- [ ] `restart` resets agent_pos to start and step_count to 0
- [ ] `quit` outputs final step count and exits cleanly

**Verification:** `echo -e 'status\nrestart\nstatus' | python grid_escape.py --grid ge-001` shows 0 steps after restart

**Task 1.5 — Completion detection** (F1.1.2, F1.1.4, F2.2.4)
- Detect agent on EXIT cell
- Output: `ESCAPED|<steps>|<grid_id>|<timestamp>`
- State: ESCAPED, no further moves accepted

**DoD:**
- [ ] Agent reaching EXIT tile outputs exactly one `ESCAPED|<steps>|<grid_id>|<timestamp>` line
- [ ] After ESCAPED, subsequent moves output no state changes
- [ ] ESCAPED line contains all 4 pipe-separated fields, timestamp is ISO format

**Verification:** `python -m pytest grid_escape/tests/test_completion.py -v` passes

**Task 1.6 — Scoring tiers** (F1.1.4)
- Optimal path pre-computed at grid generation (BFS from S to E)
- Tier assignment: PERFECT / EXCELLENT / GOOD / COMPLETED / OVERMOVED
- Output tier on completion line

**DoD:**
- [ ] Optimal path stored per grid at generation time (BFS verified)
- [ ] Tier computed as: diff≤0 → PERFECT, diff≤2 → EXCELLENT, diff≤5 → GOOD, diff≤10 → COMPLETED, else → OVERMOVED
- [ ] Tier displayed in completion output

**Verification:** `python -m pytest grid_escape/tests/test_scoring.py -v` passes with known optimal values

**Task 1.7 — Starter grids (3)** (F1.1.5)
- ge-001: 7×7, optimal 8 steps, verified solvable
- ge-002: 8×8, optimal 12 steps, verified solvable
- ge-003: 10×10, optimal 18 steps, verified solvable
- Grid seed stored per grid for deterministic replay

**DoD:**
- [ ] All 3 grids load via `--grid <id>` argument without error
- [ ] BFS confirms optimal steps match spec (8, 12, 18 respectively)
- [ ] Running same grid twice with same seed produces identical grid
- [ ] All 3 grids are completable (path exists from S to E)

**Verification:** `python grid_escape.py --grid ge-001 --seed 42 | head` runs without error; BFS test confirms solvability

**Task 1.8 — Unit tests** (F1.2.2, F9.1.1)
- Test: BFS optimal path length per grid
- Test: move validation (valid/invalid/boundary)
- Test: completion detection
- Test: step counter accuracy
- Test: restart resets correctly

**DoD:**
- [ ] All 4 test files exist under `grid_escape/tests/`
- [ ] `python -m pytest grid_escape/tests/ -v` runs with 0 failures
- [ ] Each test file covers its named concern (pathfinding, movement, completion, scoring)

**Verification:** `python -m pytest grid_escape/tests/ --tb=short` output shows all tests PASSED

**Task 1.9 — README** (F2.3.2, F2.3.3)
- Interactive usage
- Batch/agent usage: `echo -e "look\nmove..." | python grid_escape.py`
- Command reference
- Completion line format

**DoD:**
- [ ] README.md covers interactive usage with example session
- [ ] README.md covers batch mode with agent example
- [ ] All 5 commands documented with syntax
- [ ] ESCAPED completion line format documented

**Verification:** README.md exists at `grid_escape/README.md` and contains all required sections

**Sprint M1-R1 Exit Gate Verification:**
- [ ] `python grid_escape.py --grid ge-001` runs without error
- [ ] `python grid_escape.py --grid ge-002` runs without error
- [ ] `python grid_escape.py --grid ge-003` runs without error
- [ ] `python -m pytest grid_escape/tests/ -v` — all tests PASSED
- [ ] `grid_escape/README.md` exists with interactive + batch usage documented

---

### Sprint M1-R2 — Agent Gameplay Proof
**Functions:** F1.3.1–F1.3.4, F2.3.1–F2.3.3, F9.1.2
**Duration:** 1 day
**Exit gate:** Jarvis completes ge-001 and ge-002 via CLI with evidence

#### Tasks

**Task 2.1 — Jarvis ge-001 run** (F1.3.1–F1.3.3)
- Jarvis invokes grid_escape.py with ge-001 in batch mode
- Jarvis issues `look` + navigation commands
- Jarvis reaches exit
- Completion line captured

**DoD:**
- [ ] Jarvis runs grid_escape.py with `--grid ge-001` in batch mode via echo/pipeline
- [ ] `ESCAPED|<steps>|ge-001|<timestamp>` line appears in output
- [ ] Steps ≥ optimal (8); run is COMPLETED tier or better
- [ ] Completion line captured in `evidence/gameplay/ge-001_completion.log`

**Verification:** `evidence/gameplay/ge-001_completion.log` exists and contains valid ESCAPED line

**Task 2.2 — Jarvis ge-002 run** (F1.3.1–F1.3.3)
- Same as Task 2.1 with ge-002 (8×8)

**DoD:**
- [ ] Jarvis runs grid_escape.py with `--grid ge-002` in batch mode
- [ ] `ESCAPED|<steps>|ge-002|<timestamp>` line appears in output
- [ ] Steps ≥ optimal (12); run is COMPLETED tier or better
- [ ] Completion line captured in `evidence/gameplay/ge-002_completion.log`

**Verification:** `evidence/gameplay/ge-002_completion.log` exists and contains valid ESCAPED line

**Task 2.3 — Evidence compilation** (F1.3.4, F9.1.2)
- Log both runs with step counts vs optimal
- Evidence doc: completion lines + step counts
- Confirm both runs within COMPLETED tier or better

**DoD:**
- [ ] `evidence/gameplay/ge-001_completion.log` and `ge-002_completion.log` both exist
- [ ] Each log shows step count vs optimal (8 and 12 respectively)
- [ ] Both runs are tier COMPLETED or better
- [ ] Evidence doc references both logs

**Verification:** Sprint M1-R2 exit gate: both log files exist with valid completion lines

**Sprint M1-R2 Exit Gate Verification:**
- [ ] `evidence/gameplay/ge-001_completion.log` exists with valid ESCAPED|<steps>|ge-001|<timestamp>
- [ ] `evidence/gameplay/ge-002_completion.log` exists with valid ESCAPED|<steps>|ge-002|<timestamp>
- [ ] ge-001 step count ≥ optimal (8); tier is COMPLETED or better
- [ ] ge-002 step count ≥ optimal (12); tier is COMPLETED or better
- [ ] Evidence doc summarizes both runs with step counts vs optimal

---

## 4. Milestone 2 — PMO Smart Agent CLI-Native Path

### Sprint M2-R1 — PMO Action Inventory + CLI Surface
**Functions:** F3.1.1–F3.1.3, F3.2.1–F3.2.6, F9.1.3, F10.1.3, F10.2.2
**Duration:** 2 days
**Exit gate:** All 7 PMO CLI commands respond correctly to valid input

#### Tasks

**Task 3.1 — PMO action inventory** (F3.1.1–F3.1.3)
- Enumerate all PMO Smart Agent interaction scenarios required for V1.8 delivery
- For each scenario: current UI dependency identified, CLI replacement path defined
- Inventory doc: `V1_8_PMO_ACTION_INVENTORY.md`

**Task 3.2 — PMO CLI command design** (F3.2.1–F3.2.6)
- Design 7 CLI commands (create-work-item, submit-artifact, request-transition, record-validation, signal-blocker, package-delivery, status)
- Define input args, output format, error format per command
- Commands must produce machine-parseable structured output
- Commands must NOT require browser or web UI

**Task 3.3 — `pmo_cli.py` implementation** (F3.2.1–F3.2.6)
- Implement all 7 commands
- Each command validates input, produces structured output
- Invalid input returns error (not crash)
- Command reference doc generated

**Task 3.4 — PMO CLI reference doc** (F10.2.2)
- `V1_8_PMO_CLI_REFERENCE.md`
- All 7 commands documented with syntax, examples, output format

**Task 3.5 — Integration smoke test** (F3.3.1–F3.3.3, F9.1.3)
- Test each command end-to-end against a live delivery item
- Log all command outputs
- Verify PMO state changes are recorded

**DoD:**
- [ ] All 7 commands executed against a live or simulated delivery item
- [ ] All outputs logged to `evidence/pmo_cli/pmo_cli_trace.log`
- [ ] Each command output is valid JSON with expected fields
- [ ] PMO state store reflects changes from create, submit, transition, validate commands

**Verification:** `evidence/pmo_cli/pmo_cli_trace.log` exists and contains 7 command traces

**Sprint M2-R1 Exit Gate Verification:**
- [ ] `V1_8_PMO_ACTION_INVENTORY.md` exists and lists all 7 PMO CLI commands
- [ ] `V1_8_PMO_CLI_REFERENCE.md` exists with all 7 commands documented
- [ ] All 7 commands produce valid JSON output (success or error)
- [ ] `python pmo_cli.py <cmd> --help` works for all 7 commands
- [ ] Smoke test: all 7 commands invoked; none crash
- [ ] `evidence/pmo_cli/pmo_cli_trace.log` exists with 7 command traces

---

### Sprint M2-R2 — PMO CLI Integration Proof
**Functions:** F3.3.1–F3.3.3, F9.1.3, F10.2.2
**Duration:** 1 day
**Exit gate:** Full PMO delivery trace via CLI without UI dependency

#### Tasks

**Task 4.1 — Create delivery item via CLI** (F3.2.1, F3.3.1)
- Jarvis runs `pmo create-work-item Grid-Escape-M1` via CLI
- Item created in PMO system
- CLI confirmation logged

**DoD:**
- [ ] `pmo create-work-item Grid-Escape-M1` returns JSON with `{"ok": true, "item_id": "WI-..."}`
- [ ] Item appears in PMO state store
- [ ] CLI confirmation logged

**Verification:** Command output logged; item_id captured in trace

**Task 4.2 — Submit Grid Escape artifact via CLI** (F3.2.2, F3.3.1)
- `pmo submit-artifact <item_id> <path>` pointing to grid_escape.py
- Artifact registered against item

**DoD:**
- [ ] Command executes without error against real item_id from Task 4.1
- [ ] Output confirms artifact submission
- [ ] Artifact registered against item in PMO store

**Verification:** Submission output logged; artifact path confirmed in PMO store

**Task 4.3 — Stage transition via CLI** (F3.2.3, F3.3.1)
- `pmo request-transition <item_id> <stage>` for stage advancement
- Transition recorded in PMO

**DoD:**
- [ ] Transition command executes without error
- [ ] Stage change recorded in PMO store
- [ ] New stage confirmed in subsequent `pmo status` query

**Verification:** Status before and after transition logged; stage changed confirmed

**Task 4.4 — Validation record via CLI** (F3.2.4, F3.3.1)
- `pmo record-validation <item_id> <result>` recording test pass

**DoD:**
- [ ] Validation recorded against item in PMO store
- [ ] Subsequent `pmo status` reflects validation result
- [ ] Pass/fail both handled correctly

**Verification:** Validation result appears in status output

**Task 4.5 — Full PMO CLI trace log** (F3.3.2, F3.3.3, F9.1.3)
- Compile all PMO CLI operations into trace log
- Confirm all 7 operations completed without browser
- Confirm PMO CLI path is real infrastructure, not demo-only

**DoD:**
- [ ] `evidence/pmo_cli/pmo_cli_trace.log` contains all 7 command invocations
- [ ] All commands executed without browser/UI dependency
- [ ] Trace shows complete delivery item lifecycle (create → submit → transition → validate → delivery)
- [ ] Evidence doc confirms PMO CLI is real infrastructure

**Verification:** Sprint M2-R2 exit gate: full lifecycle trace exists in evidence/pmo_cli/

**Sprint M2-R2 Exit Gate Verification:**
- [ ] Item created via `pmo create-work-item Grid-Escape-M1`; item_id returned
- [ ] Artifact submitted via `pmo submit-artifact <item_id> <path>`
- [ ] Stage transitioned via `pmo request-transition <item_id> <stage>`
- [ ] Validation recorded via `pmo record-validation <item_id> pass`
- [ ] `pmo status <item_id>` reflects all above changes
- [ ] `evidence/pmo_cli/pmo_cli_trace.log` contains complete delivery lifecycle

---

## 5. Milestone 3 — PMO Event Routing + Command/Control Loop

### Sprint M3-R1 — PMO Event Routing Core
**Functions:** F5.1.1–F5.3.4, F6.3.1–F6.3.3
**Duration:** 2 days
**Exit gate:** Routing engine resolves one real ownership/handling uncertainty case end-to-end

#### Tasks

**Task 5.1 — Event intake** (F5.1.1–F5.1.3)
- `pmo route-event <event_json>` accepts routing requests
- Intake captures: initiating Agent/Sub-agent, event type, context, timestamp
- Governance-visible event log entry created

**DoD:**
- [ ] `pmo route-event <json>` accepts valid JSON and returns intake acknowledgment
- [ ] Invalid JSON returns error (not crash)
- [ ] Event log entry created with event_id, type, initiator, timestamp
- [ ] Event ID returned to caller for tracking

**Verification:** `pmo route-event '{"type":"TEST","initiator":"test"}'` returns event_id

**Task 5.2 — Routing rule engine** (F5.2.1–F5.2.4)
- Deterministic rule-based lookup (no AI inference in V1.8)
- Rules stored as explicit table:

| Event Type | Destination Rule |
|------------|-----------------|
| `UNKNOWN_TOOL` | → Most recent Agent in context |
| `BLOCKER_ESCALATION` | → PMO |
| `CLARIFICATION_NEEDED` | → Nova |

- Rule additions for V1.8 bounded cases only
- Destination types: Agent / Sub-agent / PMO / Nova / Alex

**DoD:**
- [ ] Routing rules stored as explicit table (not embedded in code logic)
- [ ] `UNKNOWN_TOOL` routes to most recent Agent in context
- [ ] `BLOCKER_ESCALATION` routes to PMO
- [ ] `CLARIFICATION_NEEDED` routes to Nova
- [ ] Unknown event type defaults to PMO

**Verification:** Unit test confirms each rule maps to correct destination

**Task 5.3 — Routing execution** (F5.3.1)
- Forward event to determined destination
- Capture forwarding confirmation

**DoD:**
- [ ] Event is forwarded to the destination returned by rule engine
- [ ] Forwarding confirmation captured with destination and timestamp
- [ ] If destination is unreachable, error is returned (not silently dropped)

**Verification:** Routing engine returns `{"status": "forwarded", "destination": "...", "at": "..."}`

**Task 5.4 — Resolution return path** (F5.3.2–F5.3.3)
- Receive result from destination
- Relay result back to initiating Agent/Sub-agent
- Log relay confirmation

**DoD:**
- [ ] Resolution received from destination is captured
- [ ] Result relayed back to initiating Agent/Sub-agent
- [ ] Relay confirmation logged
- [ ] Full return path visible in event log

**Verification:** Event log shows: INTAKE → DETERMINE → ROUTE → RESOLVE → RELAY

**Task 5.5 — Routing proof case exercise** (F5.3.4, F6.3.1–F6.3.3)
- Trigger one real routing case (UNKNOW_TOOL or BLOCKER_ESCALATION)
- Exercise full intake → determination → routing → resolution → return loop
- Evidence: event log with full trace

**DoD:**
- [ ] One synthetic UNKNOWN_TOOL or BLOCKER_ESCALATION event injected
- [ ] Full routing loop exercised: intake → determine → route → resolve → relay
- [ ] `evidence/routing/routing_proof_case.log` exists with full event trace
- [ ] Event log shows all 5 steps with timestamps

**Verification:** Sprint M3-R1 exit gate: `evidence/routing/routing_proof_case.log` exists with complete trace

**Sprint M3-R1 Exit Gate Verification:**
- [ ] `pmo route-event <json>` accepts valid JSON; returns event_id
- [ ] Routing rules table covers: UNKNOWN_TOOL → Agent, BLOCKER_ESCALATION → PMO, CLARIFICATION_NEEDED → Nova
- [ ] Routing engine returns `{"status": "forwarded", "destination": "...", "at": "..."}`
- [ ] Event log shows all 5 steps: INTAKE → DETERMINE → ROUTE → RESOLVE → RELAY
- [ ] `evidence/routing/routing_proof_case.log` exists with complete synthetic routing trace

---

### Sprint M3-R2 — Bounded PMO Command/Control Loop
**Functions:** F6.1.1–F6.3.3, F9.1.4
**Duration:** 1 day
**Exit gate:** At least one sub-agent task launched and controlled via CLI

#### Tasks

**Task 6.1 — Control command implementation** (F6.1.1–F6.1.5, F6.3.1–F6.3.3)
Implement and test each:
- `pmo launch-subagent <task_id> <agent_type>` — launch approved sub-agent
- `pmo pause-task <task_id>` — pause active task
- `pmo inspect-task <task_id>` — request status
- `pmo terminate-task <task_id>` — terminate authorized task
- `pmo invoke-command <task_id> <cmd>` — invoke approved command

**DoD:**
- [ ] All 5 control commands (`launch-subagent`, `pause-task`, `inspect-task`, `terminate-task`, `invoke-command`) implemented
- [ ] Each command returns structured JSON (success or error)
- [ ] Invalid task_id returns error; unauthorized action returns `FORBIDDEN`
- [ ] Commands do not crash on valid input

**Verification:** Smoke test all 5 commands; none crash

**Task 6.2 — Authority gating** (F6.3.1–F6.3.3)
- All control actions scoped to V1.8 approved boundaries
- Out-of-scope actions return `FORBIDDEN` (not silently ignored)
- Control loop cannot expand into broad autonomous PMO claims

**DoD:**
- [ ] Out-of-scope control actions return `{"error": "FORBIDDEN", "reason": "..."}`
- [ ] FORBIDDEN is returned, not silent ignore
- [ ] V1.8 control surface is bounded; no autonomous PMO expansion
- [ ] Authority table documented and reviewed

**Verification:** Attempt out-of-scope action; `FORBIDDEN` returned, not empty/null

**Task 6.3 — Real control loop exercise** (F6.2.1–F6.2.3, F9.1.4)
- Launch a sub-agent task via CLI
- Inspect, pause, inspect again, terminate
- Log full control loop
- Return path confirmed

**DoD:**
- [ ] Sub-agent task launched via `pmo launch-subagent`
- [ ] Task paused via `pmo pause-task`; state confirmed as paused
- [ ] Task resumed or terminated; final state logged
- [ ] Full control loop trace logged

**Verification:** Sprint M3-R2 exit gate: control loop evidence exists with launch → inspect → pause → inspect → terminate trace

**Sprint M3-R2 Exit Gate Verification:**
- [ ] All 5 control commands (`launch-subagent`, `pause-task`, `inspect-task`, `terminate-task`, `invoke-command`) implemented and return valid JSON
- [ ] Out-of-scope action returns `{"error": "FORBIDDEN"}`
- [ ] Full control loop exercised: launch → inspect → pause → inspect → terminate
- [ ] Control loop trace logged in evidence

---

## 6. Milestone 4 — Claw Studio Agent + Governance + Handoff

### Sprint M4-R1 — Claw Studio Agent Seats (Planner + TDD)
**Functions:** F7.1.1–F7.3.3, F7.4.1, F7.4.2, F7.4.4, F9.2.1–F9.2.3
**Duration:** 2 days
**Exit gate:** Planner → TDD → code handoff chain proven in real V1.8 delivery task

**Pre-sprint artifact (T7.3-equivalent, not part of sprint task count):**
The 5 documented-only role stubs (Architect, CodeReviewer, Security, Docs, DBExpert) are defined as V1.9 targeting skill spec stubs. These are documented in `V1_8_AGENT_ROLES.md` as pre-sprint artifacts, not as sprint work. This is F7.4.1 and F7.4.3 work — Nova reviews the stubs before M4-R1 begins.

#### Tasks

**Task 7.1 — Skill spec: Planner** (F7.1.1–F7.1.3, F7.4.1)
- Define Planner role as skill spec
- Input: user story / work item description
- Output: decomposed task plan with acceptance criteria per task
- Document in `V1_8_AGENT_ROLES.md`

**DoD:**
- [ ] `V1_8_AGENT_ROLES.md` contains Planner skill spec section
- [ ] Skill spec defines: input contract, output contract, role boundary
- [ ] Skill spec reviewed and approved by Nova before instantiation

**Verification:** Planner skill spec exists in `agent_seats/planner/skill.md` and `V1_8_AGENT_ROLES.md`

**Task 7.2 — Skill spec: TDD** (F7.1.1–F7.1.3, F7.4.1)
- Define TDD role as skill spec
- Input: task specification from Planner
- Output: failing test first, then minimal passing implementation
- Document in `V1_8_AGENT_ROLES.md`

**DoD:**
- [ ] `V1_8_AGENT_ROLES.md` contains TDD skill spec section
- [ ] TDD input/output contracts explicitly defined
- [ ] TDD skill spec reviewed and approved by Nova before instantiation

**Verification:** TDD skill spec exists in `agent_seats/tdd/skill.md` and `V1_8_AGENT_ROLES.md`

**Task 7.4 — Planner instantiation** (F7.4.2)
- Instantiate Planner as a live sub-agent seat
- Confirm input/output contract matches spec

**DoD:**
- [ ] Planner sub-agent seat is live and responsive
- [ ] Live chat/log trace shows: user story in → task plan with acceptance criteria out
- [ ] Input/output contract matches skill spec definition
- [ ] Seat labeled as `instantiated` in `V1_8_AGENT_ROLES.md`

**Verification:** Chat/log trace captured showing Planner responds to test input with structured task plan; trace saved to `evidence/governance/planner_trace.md`

**Task 7.5 — TDD instantiation** (F7.4.2)
- Instantiate TDD as a live sub-agent seat
- Confirm input/output contract matches spec

**DoD:**
- [ ] TDD sub-agent seat is live and responsive
- [ ] Live chat/log trace shows: task spec in → failing test out → passing code out
- [ ] TDD cycle proven: failing test appears before passing code
- [ ] Input/output contract matches skill spec definition
- [ ] Seat labeled as `instantiated` in `V1_8_AGENT_ROLES.md`

**Verification:** Chat/log trace captured showing TDD responds with failing-test-first cycle; trace saved to `evidence/governance/tdd_trace.md`

**Task 7.6 — Handoff chain exercise** (F7.4.4)
- Feed a Grid Escape task through Planner → TDD → code
- Capture chat log showing handoff
- Verify TDD receives Planner output, produces failing test, code follows

**DoD:**
- [ ] Live handoff trace shows Planner → TDD → code chain executed end-to-end
- [ ] Trace shows: Planner receives task → outputs task plan → TDD receives plan → outputs failing test → outputs passing code
- [ ] Handoff is clean: Planner output directly feeds TDD input; TDD output directly enables code step
- [ ] Handoff trace saved to evidence

**Verification:** Sprint M4-R1 exit gate: `evidence/governance/handoff_chain_trace.md` exists with complete Planner → TDD → code chain trace

**Task 7.7 — Governance review** (F7.3.1–F7.3.3, F9.2.1–F9.2.3)
- Nova reviews and approves seat configuration
- Approved seats distinguished from draft/review-pending
- Unreviewed seat sprawl prevented

**DoD:**
- [ ] Nova reviews Planner and TDD seat configurations
- [ ] Approved seats marked as `approved` in `V1_8_AGENT_ROLES.md`
- [ ] No uninstantiated or draft seats claimed as approved
- [ ] Sign-off recorded in governance evidence

**Verification:** Nova sign-off exists in `evidence/governance/seat_approval_signoffs.md`

**Sprint M4-R1 Exit Gate Verification:**
- [ ] `V1_8_AGENT_ROLES.md` contains: Planner skill spec (instantiated), TDD skill spec (instantiated), 5 role stubs documented as V1.9 targets (pre-sprint artifact)
- [ ] Live Planner trace exists at `evidence/governance/planner_trace.md`; shows user story → task plan
- [ ] Live TDD trace exists at `evidence/governance/tdd_trace.md`; shows task spec → failing test → passing code
- [ ] Handoff chain trace exists at `evidence/governance/handoff_chain_trace.md`; shows complete Planner → TDD → code chain
- [ ] Nova sign-off recorded in `evidence/governance/seat_approval_signoffs.md`

---

### Sprint M4-R2 — Thin Governance UI + PMO Visibility
**Functions:** F4.1.1–F4.3.3, F9.2.1–F9.2.3
**Duration:** 1 day
**Exit gate:** PMO UI accessible on port 8000; CLI works if UI is offline

#### Tasks

**Task 8.1 — Workflow/status visibility** (F4.1.1, F9.2.1)
- PMO web UI: active delivery items visible with status
- Queue/progress view for V1.8 delivery queue
- Artifact/review visibility surface

**DoD:**
- [ ] PMO UI accessible on port 8000 via `uvicorn governance_ui.main:app`
- [ ] `/workflow` route shows active delivery items with status
- [ ] `/queue` route shows V1.8 delivery queue
- [ ] `/artifacts` route shows artifact/review visibility

**Verification:** UI serves on port 8000; all 3 routes return valid HTML/JSON

**Task 8.2 — Governance authority surfaces** (F4.2.1–F4.2.3)
- Human approval screens at required governance points
- Escalation/review visibility
- Lightweight inspection/comparison surfaces

**DoD:**
- [ ] `/approvals` route shows human approval surfaces for governance points
- [ ] Escalation/review items visible
- [ ] Inspection surfaces allow comparison of artifact versions

**Verification:** `/approvals` route serves; approval surfaces render for governance points

**Task 8.3 — UI dependency verification** (F4.3.1–F4.3.3)
- Shut down PMO UI — confirm PMO CLI commands still work
- UI confirmed as visibility/oversight only
- V1.8 not blocked by UI unavailability

**DoD:**
- [ ] PMO UI process stopped (port 8000 not listening)
- [ ] All PMO CLI commands still function without UI
- [ ] PMO CLI commands complete successfully without UI dependency
- [ ] Grid Escape game runs without UI

**Verification:** Sprint M4-R2 exit gate: UI offline; `pmo status` and game commands work

**Sprint M4-R2 Exit Gate Verification:**
- [ ] Governance UI serves on port 8000 (`uvicorn governance_ui.main:app`)
- [ ] `/workflow`, `/queue`, `/artifacts`, `/approvals` routes all serve valid content
- [ ] PMO UI process stopped (port 8000 no longer listening)
- [ ] All PMO CLI commands (`pmo status`, `pmo create-work-item`, etc.) still function
- [ ] Grid Escape game runs without UI dependency

---

### Sprint M4-R3 — Real Claw ↔ Viper Handoff
**Functions:** F8.1.1–F8.3.3, F10.2.3
**Duration:** 1 day
**Exit gate:** Claw → Viper handoff exercised with real Grid Escape engineering work

**Acceptance standard — real handoff vs. pseudo-handoff:**

This sprint must prove a **real exercised operational handoff**, not a document-mediated pseudo-handoff.

| | Pseudo-handoff (insufficient) | Real operational handoff (required) |
|---|---|---|
| Handoff package | Defined and documented | Defined AND acknowledged by Viper side |
| Viper execution | Work acknowledged but not executed | Viper executes bounded work and returns real outputs |
| Return receipt | Document created but no real outputs | Real outputs (code, evidence, or documented results) returned across boundary |
| Evidence | Document alignment | Cross-team trace showing actual work crossing the delivery boundary |

F8.3.1 (exercise in actual work, not paper-only) and F8.3.3 (return path is real, not omitted) are the binding constraints. If both teams merely acknowledge documents without executing real work across the boundary, the sprint exit gate is not met.

#### Tasks

**Task 9.1 — Handoff initiation** (F8.1.1–F8.1.3)
- Claw packages Grid Escape game definition, engineering constraints, success criteria
- Handoff package delivered to Viper side

**DoD:**
- [ ] Handoff package JSON created with: game_definition, engineering_constraints, success_criteria, participant
- [ ] Handoff package delivered to Viper side (documented channel/contact)
- [ ] Handoff ID assigned and logged
- [ ] Evidence: handoff package in `handoff/evidence/handoff_001.md`

**Verification:** `handoff/evidence/handoff_001.md` exists with complete handoff package

**Task 9.2 — Viper execution response** (F8.2.1–F8.2.3)
- Viper receives handoff
- Viper executes bounded engineering-enablement work
- Viper returns outputs/results across delivery boundary

**DoD:**
- [ ] Viper acknowledges receipt (timestamped acknowledgment, not just document existence)
- [ ] Viper executes bounded work within handoff scope — real engineering outputs produced
- [ ] Viper returns real outputs across the delivery boundary (code, evidence, or documented results)
- [ ] Return receipt created with: receipt_id, handoff_id, status, output summary
- [ ] No evidence of pseudo-handoff: handoff is acknowledged AND executed, not just documented

**Verification:** Return receipt exists in `handoff/evidence/return_receipt_001.md`; receipt shows real outputs, not just acknowledgment

**Task 9.3 — Handoff evidence capture** (F8.3.1–F8.3.3)
- Handoff package + Viper output + return receipt logged
- Return path confirmed
- Evidence doc: `V1_8_CLAW_VIPER_HANDOFF.md`

**DoD:**
- [ ] `V1_8_CLAW_VIPER_HANDOFF.md` exists in docs/
- [ ] Contains: handoff package ref, return receipt ref, evidence summary
- [ ] Return path confirmed (Claw Studio received Viper output)
- [ ] Both handoff and return receipt evidence linked

**Verification:** Sprint M4-R3 exit gate: `V1_8_CLAW_VIPER_HANDOFF.md` exists with complete handoff/return trace

**Sprint M4-R3 Exit Gate Verification:**
- [ ] Handoff package delivered to Viper side with documented delivery channel
- [ ] `handoff/evidence/handoff_001.md` exists with handoff package
- [ ] Viper acknowledges receipt with timestamped acknowledgment
- [ ] Viper returns **real outputs** (code, evidence, or documented results — not just acknowledgment)
- [ ] `handoff/evidence/return_receipt_001.md` exists and shows real outputs delivered
- [ ] `V1_8_CLAW_VIPER_HANDOFF.md` exists with both handoff and return receipt refs
- [ ] No pseudo-handoff: evidence shows actual cross-boundary work execution, not document alignment only

---

### Sprint M4-R4 — Validation Evidence + Delivery Package
**Functions:** F9.1.1–F9.3.3, F10.1.1–F10.3.3, F11.2.1–F11.2.3
**Duration:** 1 day
**Exit gate:** All 10 V1.8 Foundation closure test questions answerable "yes" with real evidence

#### Tasks

**Task 10.1 — Compile Grid Escape delivery package** (F10.1.1–F10.1.6, F11.2.1–F11.2.3)
- Game Brief
- Game Specification (this document — V1_8_SPEC.md)
- Production Handoff Package
- Build/output candidate evidence (grid_escape.py + grids)
- Validation/Test Record
- Game Delivery Package

**DoD:**
- [ ] Game Brief exists with game overview, rules, CLI usage
- [ ] V1_8_SPEC.md is current (v1.1) and references all F-scale functions
- [ ] grid_escape.py + 3 grids deliverable exists and runs
- [ ] All unit tests pass (pytest output)
- [ ] Game Delivery Package zip created under DELIVERABLES/

**Verification:** `DELIVERABLES/V1.8-Grid-Escape-v1.0.zip` exists

**Task 10.2 — Compile PMO evidence package** (F9.1.3, F9.1.4, F10.2.2, F10.2.3)
- PMO CLI command reference + operation logs
- PMO Event Routing proof (event log with full trace)
- Command/control loop evidence

**DoD:**
- [ ] `V1_8_PMO_CLI_REFERENCE.md` exists and is complete
- [ ] `evidence/pmo_cli/pmo_cli_trace.log` contains full CLI trace
- [ ] `evidence/routing/routing_proof_case.log` contains full routing trace
- [ ] Command/control loop evidence logged

**Verification:** `DELIVERABLES/V1.8-PMO-CLI-v1.0.zip` and `V1.8-Routing-Engine-v1.0.zip` both exist

**Task 10.3 — Compile Agent gameplay evidence** (F9.1.2)
- ge-001 + ge-002 completion logs
- Step counts vs optimal
- Score tiers

**DoD:**
- [ ] `evidence/gameplay/ge-001_completion.log` exists with valid ESCAPED line
- [ ] `evidence/gameplay/ge-002_completion.log` exists with valid ESCAPED line
- [ ] Each log shows step count and tier; both are COMPLETED or better
- [ ] Evidence doc summarizes both runs

**Verification:** Both gameplay log files exist with valid completion evidence

**Task 10.4 — Compile governance evidence** (F9.2.1–F9.3.3)
- Nova review approval for Claw Studio Agent seats
- Handoff evidence (Claw → Viper)
- Artifact chain completeness check

**DoD:**
- [ ] `evidence/governance/seat_approval_signoffs.md` exists with Nova sign-off
- [ ] `V1_8_CLAW_VIPER_HANDOFF.md` exists with handoff and return receipt refs
- [ ] Artifact chain is complete: no broken references between artifacts
- [ ] All evidence files linked from `V1_8_DELIVERY_PACKAGE.md`

**Verification:** `V1_8_DELIVERY_PACKAGE.md` exists and references all evidence files

**Task 10.5 — Closure test review** (F9.3.1–F9.3.3)
- Walk through all 10 Foundation closure test questions
- Each answered "yes" with reference to specific evidence artifact
- No theoretical-only completion claims
- V1.8 result strong enough to support V1.9 without foundation reopening

**DoD:**
- [ ] All 10 closure test questions reviewed
- [ ] Each question answered "yes" with specific evidence artifact reference
- [ ] No answers rely on theoretical-only completion
- [ ] Review signed off by Nova

**Verification:** Sprint M4-R4 exit gate: closure test review doc exists with all 10 answered yes

**Task 10.6 — Delivery package finalization** (F10.3.1–F10.3.3)
- `V1_8_DELIVERY_PACKAGE.md` — master index referencing all artifacts
- Nova + Alex sign off

**DoD:**
- [ ] `V1_8_DELIVERY_PACKAGE.md` exists in docs/
- [ ] Master index references all deliverable artifacts (zips, evidence, specs, plans)
- [ ] Nova sign-off recorded
- [ ] Alex sign-off recorded
- [ ] `DELIVERABLES/V1.8-Closure-Record.md` exists with final status

**Verification:** V1.8 delivery package is complete; all sign-offs obtained; closure declared

**Sprint M4-R4 Exit Gate Verification (V1.8 Final Closure):**
- [ ] `DELIVERABLES/V1.8-Grid-Escape-v1.0.zip` exists
- [ ] `DELIVERABLES/V1.8-PMO-CLI-v1.0.zip` exists
- [ ] `DELIVERABLES/V1.8-Routing-Engine-v1.0.zip` exists
- [ ] `DELIVERABLES/V1.8-Agent-Seats.zip` exists
- [ ] `evidence/gameplay/ge-001_completion.log` and `ge-002_completion.log` exist
- [ ] `evidence/pmo_cli/pmo_cli_trace.log` exists
- [ ] `evidence/routing/routing_proof_case.log` exists
- [ ] `evidence/governance/seat_approval_signoffs.md` exists with Nova sign-off
- [ ] `V1_8_CLAW_VIPER_HANDOFF.md` exists
- [ ] `V1_8_DELIVERY_PACKAGE.md` master index exists with all artifact refs
- [ ] All 10 closure test questions answered "yes" with evidence refs
- [ ] Nova sign-off on closure
- [ ] Alex sign-off on delivery

---

## 7. Dependencies Map

```
M1-R1 [T1.1–T1.9] ──────────────────────────────────────────────┐
                                                              ↓
M1-R2 [T2.1–T2.3] ─────────────────────────────────────────────┐
                                                              ↓
M2-R1 [T3.1–T3.5] ─────────────────────────────────────────────┤
                                                              ↓
M2-R2 [T4.1–T4.5] ─────────────────────────────────────────────┤
                                                              ↓
M3-R1 [T5.1–T5.5] ─────────────────────────────────────────────┤
                                                              ↓
M3-R2 [T6.1–T6.3] ─────────────────────────────────────────────┤
                                                              ↓
M4-R1 [T7.1–T7.7] ─────────────────────────────────────────────┤
                                                              ↓
M4-R2 [T8.1–T8.3] ─┐                                           │
                   ├───────────────────────────────────────────┤
M4-R3 [T9.1–T9.3] ─┤ ── Claw ↔ Viper (exercised after M1+M2+M3) ┤
                   │                                           ↓
M4-R4 [T10.1–T10.6] ←──────────────────────────────────────────┘
```

---

## 8. Sprint Summary Table

| Sprint | Functions | Task Count | Duration | Status |
|--------|-----------|-----------|----------|--------|
| M1-R1 | F1.1.1, F1.1.3, F1.1.5, F1.2.1–F1.2.4, F2.1.1–F2.2.5, F2.3.1–F2.3.3, F9.1.1, F10.1.1–10.1.2 | 9 | 2 days | **DONE** |
| M1-R2 | F1.3.1–F1.3.4, F2.3.1–F2.3.3, F9.1.2 | 3 | 1 day | **DONE** |
| M2-R1 | F3.1.1–F3.1.3, F3.2.1–F3.2.6, F9.1.3, F10.1.3, F10.2.2 | 5 | 2 days | **DONE** |
| M2-R2 | F3.3.1–F3.3.3, F9.1.3, F10.2.2 | 5 | 1 day | **DONE** |
| M3-R1 | F5.1.1–F5.3.4, F6.3.1–F6.3.3 | 5 | 2 days | pending |
| M3-R2 | F6.1.1–F6.3.3, F9.1.4 | 3 | 1 day | pending |
| M4-R1 | F7.1.1–F7.3.3, F7.4.1, F7.4.2, F7.4.4, F9.2.1–F9.2.3 | 6 | 2 days | pending |
| M4-R2 | F4.1.1–F4.3.3, F9.2.1–F9.2.3 | 3 | 1 day | pending |
| M4-R3 | F8.1.1–F8.3.3, F10.2.3 | 3 | 1 day | pending |
| M4-R4 | F9.1.1–F9.3.3, F10.1.1–F10.3.3, F11.2.1–F11.2.3 | 6 | 1 day | pending |

**Total:** 10 sprints, 48 tasks, ~13 days
**Completed:** 4/10 sprints (M1-R1, M1-R2, M2-R1, M2-R2)

---

## 9. Out of Scope (Functions Explicitly Excluded)

**Correction from prior version:** F1.1.2 is correctly "Define the game objective and completion condition" (F1.1.2 is NOT about routing). The exclusion of AI-powered routing inference is a scope-level statement, not a Function ID. It maps to the scope document's out-of-scope list: "AI-powered routing inference as the primary routing mechanism."

The following are explicitly out of scope for V1.8:

| Excluded Item | Reason |
|--------------|--------|
| AI-powered routing inference as primary routing mechanism | Explicitly ruled out in Foundation §6 — V1.8 uses deterministic rule lookup only |
| F4.x heavy UI features | UI must remain thin; heavy UI would block V1.8 closure |
| F7.4.3 instantiation of Architect/CodeReviewer/Security/Docs/DBExpert | F7.4.3 explicitly defines these as documented skill specs only (V1.9 targets); not excluded from scope, but not instantiated in V1.8 |
| F10.2.1 multi-game support | Portfolio operations belong to V1.9+ |
| Pub/Sub as generalized infrastructure | Formal Pub/Sub is V1.9 scope |
| Commercial launch/store/promotion | V2.0 territory |

---

## 10. Closure Test Reminder (from V1.8 Foundation §8)

V1.8 does not close unless all 10 questions below answer **yes** using real evidence:

1. Was a first real AI-native game delivered through the defined governed structure?
2. Is the delivered game materially agent-playable rather than only conceptually described?
3. Can at least one real Agent participant actually play and complete the game through the defined agent-facing interface?
4. Did Claw and Viper function together through a real handoff/execution path where needed?
5. Can all required PMO Smart Agent interaction scenarios be performed through CLI commands without depending on UI interaction?
6. Does the CLI also support the specific command set required for the first AI-native game itself?
7. Did PMO Event Routing successfully handle at least one real ownership/handling uncertainty case through a bounded routed-resolution loop?
8. Is UI dependency kept thin enough that the release is not blocked by heavy frontend buildout?
9. Are governance and PMO oversight still explicit at the right authority points?
10. Is the release strong enough to count as first-product proof without borrowing closure language from later versions?

Each sprint exit gate is designed to produce evidence directly addressable against these 10 questions.
