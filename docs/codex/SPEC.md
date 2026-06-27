# Nexus Agent Coding Team Delivery Console Spec

Date: 2026-06-27
Branch: `codex/edc-governance-desktop`
Internal PR: `EDC-PR-001`

## Product Intent

Nexus should become a local-first Agent Coding Team Delivery Console for real project delivery work. The desktop client should move beyond governance fixture display and become the visible operating surface for planning, execution assignment, validation, PR review, UAT decision intake, and delivery closeout.

EDC is the engineering delivery control system for this workflow. It governs scope, task cards, worktree boundaries, validation evidence, PR mapping, and closeout decisions.

## UX Specification

The durable UX specification for this target lives in `docs/codex/UX_SPEC.md`. It records the Figma frame mapping, product surfaces, workflow model, state model, no-go/safety states, implementation split, open UX questions, and risks. This spec should reference `UX_SPEC.md` rather than duplicating frame-level details.

## Functional Requirements

### 0. Reference Intake

- Nexus repo remains the authority for source, tests, delivery state, and task execution.
- Shared Docs may provide historical governance/design/evidence context.
- SecondBrain may provide curated reference patterns only when cited in `docs/codex/SECOND_BRAIN_REFERENCE_MAP.md`.
- SecondBrain reference notes do not create scope without acceptance into the current Nexus target, scope, spec, task card, or owner instruction.

### 1. Delivery Project

- A project record identifies the local repository root, default base branch, active delivery branch, validation entry points, and evidence locations.
- The MVP may support one active project at a time.
- Project records must not include secrets, credentials, private sessions, cache paths, or logs as source-of-truth context.

### 2. Work Items

- A work item is the durable delivery unit.
- Required fields: internal ID, title, background, goal, scope, non-goals, file boundaries, acceptance criteria, validation commands, risks, write-back location, status, owner, assigned agent, branch, GitHub PR mapping, and UAT state.
- Initial statuses: `Draft`, `Ready`, `Assigned`, `Running`, `Blocked`, `Review`, `UAT`, `Done`, `Failed`, `Cancelled`.
- Work items must start from a current task packet before broad reference-memory retrieval.
- Work items must support blocked/deferred outcomes for missing authority, missing tools, failed validation, uncertainty, timeout, or runtime mismatch.

### 3. Agent Registry

- Initial roles: Codex Planning, Codex Execution, and Alex owner UAT.
- An agent record must expose role, availability, current assignment, last report, blockers, and allowed actions.
- Codex Planning may create task cards and review reports.
- Codex Execution may implement explicitly assigned task cards in the named branch/worktree.
- Owner UAT remains a human decision and cannot be self-authorized by Codex.
- Multi-agent fan-out requires explicit reducer ownership before work starts.
- Parallel agent execution requires editable-scope boundaries, shared-resource lock or handoff rules, and dependency-aware merge order.

### 4. Runtime And Worktree Execution

- Execution tasks use isolated project worktrees by default.
- Runtime startup, dependency installation, live dispatch, and broker mutation require explicit owner authorization.
- Each run records start state, branch, worktree path, files touched, validation commands, command results, blockers, and completion report.
- The system must distinguish "task prepared", "execution started", "validation passed", "review accepted", and "UAT accepted".
- Runtime identity, state, events, delivery handling, failure handling, and coordination must be modeled before role/persona abstractions are added.

### 5. Desktop Console

- The first useful desktop surface should show delivery state, not marketing or governance-only fixture panels.
- Required MVP views: backlog/work items, active runs, agents, validation/evidence, branch/PR mapping, and UAT state.
- The UI must label blocked or unauthorized actions as blocked behavior, not hidden failures.
- Operator surfaces are read-and-command views over authoritative delivery state, not separate sources of truth.

### 6. PR And Evidence Mapping

- Internal delivery identifiers use `EDC-PR-###`.
- GitHub PR numbers are external mappings recorded after GitHub creates them.
- Completion claims require fresh validation evidence or a documented reason validation was not run.
- Owner UAT notes must be separated from Codex automated checks.

## Non-Functional Requirements

- Local-first and reviewable before automation-first.
- No OpenClaw private dependency for Nexus delivery.
- No secrets, `.env`, sqlite databases, caches, logs, cookies, SSH keys, auth tokens, or private session material.
- Stable branch/worktree boundaries and explicit cleanup authorization.
- Evidence-before-claim for every delivery status.
- Narrow validation commands first; broader validation only when risk warrants it.
- Prefer durable structured files/contracts over private chat memory.
- Prefer structured, inspectable state and validation outputs over prose-only status.
- External tools, frameworks, and agent platforms require license, privacy, network, credential, sandbox, and output-behavior review before use.

## Acceptance Criteria For EDC-PR-001

- A fresh reviewer can understand the Agent Coding Team Delivery Console target from `docs/codex/TARGET.md`, `SCOPE.md`, `SPEC.md`, and `PR_PLAN.md`.
- A fresh reviewer can identify which Shared Docs / SecondBrain reference inputs influenced the design.
- The PR sequence uses internal `EDC-PR-###` identifiers and records GitHub PR numbers only as mappings.
- The closed GitHub PR #22 is mapped as `EDC-PR-000` and marked superseded.
- `EDC-PR-002` is defined as the first implementation slice, not started in this planning reset.
- `docs/codex/UX_SPEC.md` captures the Figma UX intent and maps it to future implementation slices.
- Planning reset changes do not touch product code, dependencies, package locks, runtime startup, generated files, or evidence cleanup.

## Validation Commands

Planning-doc-only changes:

```powershell
git diff --check
```

Expected implementation validations, selected by touched surface:

```powershell
python -m pytest nexus/governance/tests
npm test --prefix apps/l1gov-desktop-client
```

Desktop startup/Tauri commands are future-authorized-only unless Alex explicitly asks Codex to start the app.
