# Nexus Agent Coding Team Workbench UX Spec

Date: 2026-06-27
Branch: `codex/edc-pr-006-ux-reset-workbench`
Internal PR: `EDC-PR-006`

## Source Reference

Figma file: https://www.figma.com/design/eDUWZ0Mbl9aaJLsv6aXEtT

This file remains a visual reference. Durable Nexus product decisions live in repo docs and task cards. Figma frames do not override current owner instruction, repo facts, file boundaries, validation evidence, or safety policy.

The Figma frames still provide useful surface intent, but EDC-PR-006 supersedes the prior single-board implementation split.

| Frame | Node ID | Product surface intent | New implementation interpretation |
| --- | --- | --- | --- |
| `00 UX Map` | `1:2` | UX map, navigation model, authority/runtime guardrails | Workbench shell IA and safety model reference |
| `01 Delivery Board` | `1:60` | Delivery board, project summary, work lanes, attention rail | Work Items board/list view, not the entire app |
| `02 Work Item Detail` | `1:181` | Task card detail, readiness checks, assignment/report actions | Separate Work Item Detail view |
| `03 Agent Team And Runtime` | `1:272` | Agent registry, runtime authorization, handoff/runtime panels | Separate Agents and Runtime/Worktrees views |
| `04 UAT And PR Closeout` | `1:361` | PR mapping, evidence gate, owner UAT decision | Separate PR/UAT Closeout view with Evidence/Runs support |

## Product Intent

Nexus is the Agent Coding Team Workbench: a local-first project delivery workspace where Codex Planning, Codex Execution, reviewer/reducer roles, and Alex owner UAT move bounded work through planning, isolated execution, validation, review, PR mapping, owner decision intake, and closeout.

The Workbench is not a production-readiness claim, an autonomous runtime approval surface, a replacement for owner UAT, or an OpenClaw private-session dependency. It is the visible operating layer for scope, authorization, assignment, evidence, blockers, and closeout state.

## EDC-PR-006 UX Reset

EDC-PR-004 / GitHub PR #30 and EDC-PR-005 / GitHub PR #31 are superseded as UX implementation baseline. They compressed too many workflows into one overloaded page and did not create clear reviewable page boundaries.

The replacement architecture is a Multica-style workbench IA adapted to Nexus constraints:

- persistent workspace shell;
- explicit navigation;
- separate views for different operator jobs;
- visible agent/work/runtime state;
- durable work item detail;
- evidence-before-claim;
- owner UAT separated from automated validation.

Multica is a product/IA reference only. Do not copy its Next.js, Go, Postgres, deployment, service architecture, or code.

## Primary Users And Operating Mode

- Planning: creates durable work items and complete Execution task cards with background, goal, scope, non-goals, file boundaries, acceptance criteria, validation commands, risks, and write-back location.
- Execution: works only from explicit task cards in named branches/worktrees, reports changed files, validation commands/results, blockers, residual risk, and PR readiness.
- Owner/UAT: reviews outcomes after EDC-PR-010, authorizes runtime startup when needed, records acceptance/rejection separately from automated validation, and controls final UAT/closeout decisions.
- Reviewer/reducer: compares evidence, review feedback, and parallel-agent outputs; owns fan-in decisions when multiple agents or branches are active.

Operating mode is bounded and local-first. The current task packet takes priority over broad memory retrieval. Runtime startup, dependency installation, live dispatch, broker mutation, merge, cleanup, and owner UAT claims require explicit owner authorization.

## Information Architecture

### Workspace Shell / Navigation

The shell is the first screen structure. It must show project identity, local path, current internal sequence, branch/worktree context, global authorization/status chips, primary navigation, and urgent attention state.

Navigation must change real views/pages. It must not be a single page with scroll anchors pretending to be sections.

### Work Items Board / List

Purpose: scan planned, assigned, running, review, blocked, UAT, done, failed, and cancelled work.

Must show internal `EDC-PR-###` ID separately from GitHub PR number, title, status, lane, assignee, branch/worktree, evidence state, owner UAT state, runtime authorization state, blocker chips, attention flags, and an entry point to Work Item Detail.

### Work Item Detail

Purpose: inspect and review a single task card and execution report.

Must show background, goal, scope, non-goals, file boundaries, acceptance criteria, validation commands, risks, write-back location, readiness checklist, assignment/run state, changed files, validation report, and explicit blocked/not-authorized actions.

### Agents / Team

Purpose: see accountable roles and assignment boundaries.

Must show Codex Planning, Codex Execution, reviewer/reducer, and Alex owner UAT roles; availability; current assignment; allowed actions; forbidden actions; last report; blockers; and reducer ownership for fan-out work.

### Runtime / Worktrees

Purpose: inspect execution environment without implying runtime authorization.

Must show named worktree path, branch, base, dirty/staged state summary, runtime authorization state, named command only when explicitly authorized, and blocked startup/dependency/broker/dispatch states.

### Evidence / Runs

Purpose: make evidence-before-claim visible.

Must show run records, command results, timestamps/refs when available, evidence state, changed files, completion report refs, and stale/missing evidence warnings.

Evidence states: `missing`, `stale`, `present`, `failed`, `not_run_by_scope`.

### PR / UAT Closeout

Purpose: close the loop without conflating automated validation and owner UAT.

Must show internal-to-GitHub PR mapping, evidence gates per internal PR, owner UAT decision state, closeout recommendation state, and merge/UAT PASS/production/live readiness blocked until owner authority exists.

Owner UAT must not be requested before EDC-PR-010 is ready.

### Inbox / Attention

Purpose: give operators a focused review queue.

Must include runtime startup hold, dependency install not authorized, live dispatch blocked, broker/NATS mutation blocked, owner UAT not accepted, missing reducer, stale/missing evidence, scope mismatch, and PR mapping gaps.

### Settings / Boundaries

Purpose: expose project and safety boundaries when needed.

Settings may include project root, allowed validation commands, local-test service ports, and explicit no-go surfaces. It must not store secrets or private session data.

## Workflow Model

1. Planning creates or updates a work item from current repo facts and accepted reference inputs.
2. Planning emits a complete Execution task card with explicit file boundaries, validation commands, risks, and write-back location.
3. Reviewer/reducer confirms the task is ready, assigns Execution, and records the branch/worktree boundary.
4. Execution works in the named isolated worktree and does not start runtime, install dependencies, mutate brokers, dispatch, or broaden scope unless the task card authorizes it.
5. Execution writes back changed files, validation commands, command results, blockers, residual risk, and PR readiness.
6. Reviewer/reducer checks evidence-before-claim, resolves fan-in/merge-order concerns, and moves the item to review or blocked state.
7. PR mapping is updated when GitHub creates an external PR number.
8. Owner UAT starts only after EDC-PR-010 is ready and Alex authorizes the review. Automated validation remains separate from owner acceptance.
9. Closeout records PR mapping, evidence gate status, owner UAT decision, and next task recommendation without claiming production readiness.

## Core State Model

Work item status: `Draft`, `Ready`, `Assigned`, `Running`, `Blocked`, `Review`, `UAT`, `Done`, `Failed`, `Cancelled`.

Runtime authorization state: `not_required`, `hold`, `authorized_for_named_command`, `blocked_by_policy`.

Owner UAT state: `not_ready`, `awaiting_owner`, `accepted_by_owner`, `rejected_by_owner`, `not_applicable`.

Evidence state: `missing`, `stale`, `present`, `failed`, `not_run_by_scope`.

PR mapping state separates internal `EDC-PR-###` identifiers from GitHub PR numbers. GitHub PR numbers are external mappings only and must not become the internal delivery sequence.

## No-Go And Safety States

The UI must show these states explicitly rather than hiding unavailable actions:

- runtime hold;
- missing owner authorization for runtime, dependency, broker, dispatch, branch, merge, cleanup, or UAT action;
- blocked by policy for secrets, private sessions, caches, logs, sqlite databases, generated auth material, cookies, SSH keys, or other prohibited surfaces;
- no owner UAT yet;
- missing reducer;
- stale evidence;
- scope mismatch.

## Implementation Split Recommendation

- `EDC-PR-006`: docs-only UX reset and PR stack replan from EDC-PR-003/#29.
- `EDC-PR-007`: desktop workspace shell and real navigation.
- `EDC-PR-008`: Work Items board/list and Work Item Detail surfaces.
- `EDC-PR-009`: Agents, runtime, and worktree surfaces.
- `EDC-PR-010`: Evidence/Runs, PR/UAT closeout, final startup readiness, and owner UAT preparation.

Do not begin owner UAT before EDC-PR-010. Do not add runtime startup or live dispatch unless a future task card explicitly authorizes the named command and side-effect boundary.

## Open UX Questions

- Should Work Items default to lane board, dense list, or split board/list toggle for the MVP?
- Should Work Item Detail be a route/page or a persistent split view from the board?
- What is the smallest useful run timeline surface for EDC-PR-010?
- How should owner UAT decisions be recorded when Alex provides results outside the desktop app?
- How much GitHub PR metadata should be read automatically versus entered as explicit mapping fields in repo docs?
- Which settings belong in the first UAT-ready build versus docs-only boundaries?

## Implementation Risks

- Reusing PR #30/#31 UI too directly could recreate the overloaded single-screen failure.
- Runtime controls can imply unsafe authority if hold/not-authorized states are not first-class.
- Owner UAT can be blurred with automated validation unless the state model keeps them separate.
- Internal `EDC-PR-###` identifiers can be confused with GitHub PR numbers unless mapping is consistently displayed.
- Parallel-agent workflow can create merge-order and ownership ambiguity unless reducer and editable-scope fields are required early.
- Multica-inspired IA can become stack copying unless future task cards keep Nexus/Tauri/local-first constraints explicit.
