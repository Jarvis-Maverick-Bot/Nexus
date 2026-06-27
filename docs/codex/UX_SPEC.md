# Nexus Agent Coding Team Delivery Console UX Spec

Date: 2026-06-27
Branch: `codex/edc-governance-desktop`
Internal PR: `EDC-PR-001`

## Source Reference

Figma file: https://www.figma.com/design/eDUWZ0Mbl9aaJLsv6aXEtT

This file is a visual reference for the Agent Coding Team Delivery Console. Durable Nexus product decisions live in repo docs and task cards; Figma frames do not override current owner instruction, repo facts, file boundaries, validation evidence, or safety policy.

| Frame | Node ID | Product surface | Likely implementation slice |
| --- | --- | --- | --- |
| `00 UX Map` | `1:2` | UX map, navigation model, authority/runtime guardrails | `EDC-PR-001` spec alignment; later implementation reference |
| `01 Delivery Board` | `1:60` | Delivery board, project summary, work lanes, attention rail | `EDC-PR-004` desktop delivery board MVP |
| `02 Work Item Detail` | `1:181` | Task card detail, readiness checks, assignment/report actions | `EDC-PR-002` domain contracts; `EDC-PR-003` handoff loop |
| `03 Agent Team And Runtime` | `1:272` | Agent registry, runtime authorization, handoff/runtime panels | `EDC-PR-002` domain contracts; `EDC-PR-003` handoff loop |
| `04 UAT And PR Closeout` | `1:361` | PR mapping, evidence gate, owner UAT decision | `EDC-PR-005` owner UAT closeout |

## Product Intent

Nexus is the Agent Coding Team Delivery Console: a local-first project delivery workspace where Codex Planning, Codex Execution, owner UAT, and review/reducer roles move bounded work through planning, isolated execution, validation, review, PR mapping, UAT decision intake, and closeout.

The console is not a production-readiness claim, an autonomous runtime approval surface, a replacement for owner UAT, or an OpenClaw private-session dependency. It is the visible operating layer for scope, authorization, assignment, evidence, blockers, and closeout state.

## Primary Users And Operating Mode

- Planning: creates durable work items and complete Execution task cards with background, goal, scope, non-goals, file boundaries, acceptance criteria, validation commands, risks, and write-back location.
- Execution: works only from explicit task cards in named branches/worktrees, reports changed files, validation commands/results, blockers, residual risk, and PR readiness.
- Owner/UAT: reviews outcomes, authorizes runtime startup when needed, records acceptance/rejection separately from automated validation, and controls final UAT/closeout decisions.
- Reviewer/reducer: compares evidence, review feedback, and parallel-agent outputs; owns fan-in decisions when multiple agents or branches are active.

Operating mode is bounded and local-first. The current task packet takes priority over broad memory retrieval. Runtime startup, dependency installation, live dispatch, broker mutation, and owner UAT claims require explicit owner authorization.

## Information Architecture

- Delivery Board: project summary, internal delivery ID, staged/active work counts, GitHub PR mapping, work lanes, validation chips, and attention items.
- Work Item Detail: full task-card surface, readiness checklist, validation/report summary, assignment action, and block action.
- Agent Team/Runtime: agent roles, availability, current assignment, allowed actions, editable scope, runtime hold/authorization state, and handoff status.
- Evidence/Runs: execution runs, worktree path, branch, files touched, commands run, command results, blockers, and stale/missing evidence flags.
- PR/UAT Closeout: internal-to-GitHub PR mapping, evidence gates, review state, owner UAT decision options, and closeout recommendation state.

Navigation should expose Delivery Board, Work Items, Agents, Runs, Evidence, PR/UAT, and Settings. Settings is not an implementation priority unless needed to support project selection or explicit authorization boundaries.

## Workflow Model

1. Planning creates or updates a work item from current repo facts and accepted reference inputs.
2. Planning emits a complete Execution task card with explicit file boundaries, validation commands, risks, and write-back location.
3. Owner or reducer confirms the task is ready, assigns Execution, and records the branch/worktree boundary.
4. Execution works in the named isolated worktree and does not start runtime, install dependencies, mutate brokers, or broaden scope unless the task card authorizes it.
5. Execution writes back changed files, validation commands, command results, blockers, residual risk, and PR readiness.
6. Reviewer/reducer checks evidence-before-claim, resolves fan-in/merge-order concerns, and moves the item to review or blocked state.
7. If review is accepted, the work item enters owner UAT only when owner observation or owner-provided results are available.
8. Closeout records PR mapping, evidence gate status, owner UAT decision, and next task recommendation without claiming production readiness.

## Core State Model

Work item status:

- `Draft`: incomplete planning material or missing authority.
- `Ready`: complete task card and validation boundary are present.
- `Assigned`: named Execution agent and worktree/branch are selected.
- `Running`: Execution has started within the authorized boundary.
- `Blocked`: policy, authority, tool, validation, certainty, timeout, runtime, or dependency boundary prevents progress.
- `Review`: Execution reported results and evidence is ready for reviewer/reducer inspection.
- `UAT`: owner-facing review is authorized and awaiting owner decision.
- `Done`: owner/reviewer closeout criteria are satisfied for the bounded task only.
- `Failed`: validation or review failed and no immediate retry path is active.
- `Cancelled`: owner/reducer stopped the work item.

Readiness state:

- task card complete;
- file boundary explicit;
- validation commands explicit;
- branch/worktree boundary explicit;
- runtime/dependency side effects authorized or explicitly out of scope;
- reviewer/reducer owner identified when parallel work exists.

Runtime authorization state:

- `not_required`: task is docs/design/model-only and requires no runtime startup.
- `hold`: runtime command exists but must not be run yet.
- `authorized_for_named_command`: owner authorized a specific command and side-effect boundary.
- `blocked_by_policy`: requested action violates current safety or scope rules.

Owner UAT state:

- `not_ready`: review/evidence is incomplete.
- `awaiting_owner`: owner observation or result is needed.
- `accepted_by_owner`: owner explicitly accepted the bounded outcome.
- `rejected_by_owner`: owner rejected or requested revision.
- `not_applicable`: task has no owner-facing UAT requirement.

Evidence state:

- `missing`: no validation result or documented reason exists.
- `stale`: validation predates relevant changes.
- `present`: command/result or documented reason is attached.
- `failed`: command ran and failed.
- `not_run_by_scope`: task did not authorize or require executable validation.

PR mapping state separates internal `EDC-PR-###` identifiers from GitHub PR numbers. GitHub PR numbers are external mappings only and must not become the internal delivery sequence.

## No-Go And Safety States

The UI must show these states explicitly rather than hiding unavailable actions:

- runtime hold: a command exists but runtime startup is not authorized;
- not authorized: owner authorization is missing for runtime, dependency, broker, dispatch, branch, merge, or cleanup action;
- blocked by policy: requested scope touches secrets, private sessions, caches, logs, sqlite databases, generated auth material, or other prohibited surfaces;
- no owner UAT yet: automated validation may exist, but owner acceptance has not been provided;
- missing reducer: parallel/multi-agent work has no named fan-in owner;
- stale evidence: validation exists but no longer covers current changes;
- scope mismatch: requested edit falls outside the task card file boundary.

## Frame Intent And Surface Notes

### 00 UX Map

Intent: orient the product around project delivery, not governance-only display. The frame shows the global navigation, project path/branch context, authority/runtime pills, and a map of delivery board, work item detail, agent team, run timeline, PR closeout, and reference-boundary concepts.

Implementation meaning: use this as the IA guardrail for later slices. It does not require a separate map screen in the MVP unless it helps onboarding or review.

### 01 Delivery Board

Intent: show project status, internal delivery identifier, staged docs/work count, PR mapping, lane-based work state, validation chips, and attention items. The board should make blocked or unauthorized work visible.

Implementation meaning: desktop MVP should start here once contracts and handoff records exist. It needs read models for project summary, lanes, work cards, validation chips, and right-rail attention items.

### 02 Work Item Detail

Intent: expose the complete task card and the side-panel readiness/reporting state. The visible sections match the Execution task-card contract: background, goal, scope, non-goals, file boundaries, acceptance criteria, validation commands, risks, and write-back location.

Implementation meaning: domain contracts must validate task-card completeness before desktop assignment actions are meaningful. Assignment and block actions should write durable state, not just UI state.

### 03 Agent Team And Runtime

Intent: show agents as accountable delivery roles with status, assignment, scope, and allowed actions. Runtime state is separate from agent identity and must surface authorization/hold conditions.

Implementation meaning: implement agent/run/runtime state as inspectable records before adding any runtime command bridge. Runtime panels should support hold/not-authorized states from the start.

### 04 UAT And PR Closeout

Intent: map internal delivery items to GitHub PRs, show evidence gate state, and collect owner UAT decisions without treating Codex validation as owner acceptance.

Implementation meaning: closeout should depend on evidence state and owner decision state. GitHub PR creation, merge, close, or UAT PASS claims remain outside Codex authority unless separately authorized.

## Implementation Split Recommendation

- `EDC-PR-002`: define durable delivery domain contracts for project, work item, task card, agent, assignment, run, validation/evidence, PR mapping, runtime authorization, and owner UAT state.
- `EDC-PR-003`: define Planning-to-Execution and Execution-to-Planning handoff records, including task-card emission, completion report write-back, blocker reporting, and evidence freshness rules.
- `EDC-PR-004`: implement desktop Delivery Board MVP against the durable read model: project summary, lanes, work cards, validation chips, attention rail, and visible blocked/hold states.
- `EDC-PR-005`: implement owner UAT and PR closeout views: PR mapping, evidence gate, owner decision intake, and closeout recommendation.

Do not begin desktop implementation until the domain and handoff records can provide stable data. Do not add runtime startup or live dispatch in the board MVP.

## Open UX Questions

- Should the MVP include a separate `00 UX Map` screen, or should it remain a planning/reference artifact only?
- What is the smallest useful run timeline surface: a dedicated Runs view, a work-item side panel, or both?
- Which attention items belong in the Delivery Board right rail for the first implementation: blocked work, stale evidence, missing UAT, missing reducer, runtime hold, PR mapping gaps, or all of these?
- How should owner UAT decisions be recorded when Alex provides results outside the desktop app?
- What fields are required for reviewer/reducer closeout beyond validation evidence and owner UAT state?
- How much GitHub PR metadata should be read automatically versus entered as explicit mapping fields in repo docs?

## Implementation Risks

- Figma is visual intent, not source authority; later implementation must inspect current code and repo docs before editing product surfaces.
- Over-specifying UI behavior before domain contracts exist could create display-only panels with no durable state behind them.
- Runtime controls can imply unsafe authority if hold/not-authorized states are not first-class.
- Owner UAT can be blurred with automated validation unless the state model keeps them separate.
- Internal `EDC-PR-###` identifiers can be confused with GitHub PR numbers unless mapping is consistently displayed.
- Parallel-agent workflow can create merge-order and ownership ambiguity unless reducer and editable-scope fields are required early.
