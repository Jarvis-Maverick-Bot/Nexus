# Nexus Agent Coding Team Workbench Spec

Date: 2026-06-27
Branch: `codex/edc-pr-006-ux-reset-workbench`
Internal PR: `EDC-PR-006`

## Product Intent

Nexus should become a local-first Agent Coding Team Workbench for real project delivery work. The desktop client should move beyond governance fixture display and beyond the rejected single-screen delivery board/closeout prototype.

The Workbench is the visible operating surface for planning, execution assignment, validation, PR review, owner UAT decision intake, and delivery closeout. EDC governs scope, task cards, worktree boundaries, validation evidence, PR mapping, and closeout decisions.

## Reset Decision

EDC-PR-004 / GitHub PR #30 and EDC-PR-005 / GitHub PR #31 are not UAT-accepted product UX. They overloaded one screen with delivery board, details, agent/runtime state, evidence, PR/UAT closeout, and blocked commands. They are superseded as the implementation baseline.

The next implementation base is EDC-PR-003 / GitHub PR #29, `codex/edc-pr-003-codex-handoff-loop`, because it preserves durable delivery contracts and the handoff loop without inheriting the failed desktop UX direction.

## UX Specification

The durable UX specification lives in `docs/codex/UX_SPEC.md`. The EDC-PR-006 replan rationale lives in `docs/codex/UX_REPLAN_EDC_PR_006.md`.

Implementation task cards should reference these docs rather than reviving the rejected PR #30/#31 single-screen design.

## Functional Requirements

### 0. Reference Intake

- Nexus repo remains the authority for source, tests, delivery state, and task execution.
- Shared Docs may provide historical governance/design/evidence context.
- SecondBrain may provide curated reference patterns only when cited in `docs/codex/SECOND_BRAIN_REFERENCE_MAP.md`.
- Multica is an IA/product reference only and does not authorize copying its Next.js, Go, Postgres, deployment, service architecture, or code.

### 1. Workbench Shell

- The desktop experience must have a workspace shell with stable navigation.
- Primary navigation must move between real views/pages, not scroll anchors on one long screen.
- The shell shows project identity, branch/worktree context, internal delivery sequence, authorization boundary, and high-priority attention state.

### 2. Work Items

- A work item is the durable delivery unit.
- Required fields: internal ID, title, background, goal, scope, non-goals, file boundaries, acceptance criteria, validation commands, risks, write-back location, status, owner, assigned agent, branch, GitHub PR mapping, and UAT state.
- Work Items board/list and Work Item Detail are separate surfaces.
- Initial statuses: `Draft`, `Ready`, `Assigned`, `Running`, `Blocked`, `Review`, `UAT`, `Done`, `Failed`, `Cancelled`.

### 3. Agent Registry

- Initial roles: Codex Planning, Codex Execution, reviewer/reducer, and Alex owner UAT.
- Agent records expose role, availability, current assignment, last report, blockers, allowed actions, and forbidden actions.
- Codex Planning creates task cards and reviews reports.
- Codex Execution implements explicit task cards in named branches/worktrees.
- Owner UAT remains a human decision and cannot be self-authorized by Codex.
- Multi-agent fan-out requires explicit reducer ownership before work starts.

### 4. Runtime And Worktrees

- Execution tasks use isolated project worktrees by default.
- Runtime startup, dependency installation, live dispatch, and broker mutation require explicit owner authorization.
- Runtime/worktree state is a separate view from agent identity.
- Each run records start state, branch, worktree path, files touched, validation commands, command results, blockers, and completion report.
- The system distinguishes task prepared, execution started, validation passed, review accepted, owner UAT accepted, and closeout accepted.

### 5. Evidence And Runs

- Evidence/Runs is a first-class view.
- Completion claims require fresh validation evidence or a documented reason validation was not run.
- Missing, stale, failed, or scope-exempt validation must be visible.
- Evidence is non-secret durable state; it must not include credentials, private sessions, logs, caches, sqlite databases, cookies, SSH keys, or auth tokens.

### 6. PR And UAT Closeout

- Internal delivery identifiers use `EDC-PR-###`.
- GitHub PR numbers are external mappings recorded after GitHub creates them.
- PR/UAT closeout is a separate view from the work item board.
- Owner UAT notes and decisions are separate from Codex automated checks.
- The next owner UAT checkpoint is after EDC-PR-010, not PR #31.

### 7. Inbox / Attention

- Inbox/Attention surfaces blocked work, stale evidence, missing owner UAT, runtime hold, dependency install not authorized, live dispatch blocked, broker mutation blocked, missing reducer, and scope mismatches.
- Attention state should drive review and rework without implying Codex can self-authorize unsafe actions.


### 8. Command Drafts And Backend Projection

EDC-PR-011 adds a bounded operational projection layer. The Workbench may show draft-only commands such as `evaluate_assignment_candidate`, `prepare_execution_handoff_draft`, `request_owner_uat_decision_draft`, `refresh_projection_draft`, and `record_validation_evidence_draft`.

These drafts are validated data records, not executable authority. Validators must reject live dispatch, runtime startup, dependency installation, broker/NATS mutation, PR merge, owner UAT acceptance, production readiness, live readiness, missing handoff/write-back fields, and EDC/GitHub PR identifier mixing.

The domain model keeps `AgentDefinitionRecord`, `RuntimeProviderProfile`, `RuntimeInstanceRecord`, and `RunSessionRecord` separate. A Codex session or run may be execution state for an agent, but it is not the Agent identity.
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

## Acceptance Criteria For EDC-PR-006

- A fresh reviewer can understand why EDC-PR-004/#30 and EDC-PR-005/#31 were superseded as UX implementation baseline.
- Docs identify EDC-PR-003/#29 as the new implementation base.
- The product target is `Nexus Agent Coding Team Workbench`.
- The next UAT baseline is EDC-PR-010, not #31.
- `docs/codex/UX_SPEC.md` defines a multi-view workbench architecture.
- `docs/codex/PR_PLAN.md` separates internal `EDC-PR-###` IDs from GitHub PR numbers and replans EDC-PR-006..010.
- Planning reset changes do not touch product code, dependencies, package locks, runtime startup, generated files, cleanup, or secrets.

## Validation Commands

Planning-doc-only changes:

```powershell
git status --short --branch
git diff --check
git diff -- docs/codex/TARGET.md docs/codex/SCOPE.md docs/codex/SPEC.md docs/codex/UX_SPEC.md docs/codex/PR_PLAN.md docs/codex/UX_REPLAN_EDC_PR_006.md
```

Expected implementation validations for later slices, selected by touched surface:

```powershell
python -m pytest nexus/governance/tests
npm test --prefix apps/l1gov-desktop-client
```

Desktop startup, Tauri, Cargo, pnpm dev, dependency installation, broker/NATS mutation, and live dispatch require explicit future task-card authorization.
