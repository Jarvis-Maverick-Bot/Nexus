# Nexus Agent Coding Team Workbench Scope

Date: 2026-06-27
Branch: `codex/edc-pr-006-ux-reset-workbench`
Internal PR: `EDC-PR-006`

## In Scope

Product scope for the next stage:

- A local-first Nexus Agent Coding Team Workbench.
- One active project workspace at a time for the MVP.
- A real desktop shell with persistent navigation and page/view boundaries.
- Durable work items with the task-card fields required by the Nexus Codex operating guide.
- Separate views for Work Items board/list, Work Item Detail, Agents/Team, Runtime/Worktrees, Evidence/Runs, PR/UAT Closeout, Inbox/Attention, and Settings/Boundaries when needed.
- Agent roles for Codex Planning, Codex Execution, reviewer/reducer, and Alex owner UAT review.
- Assignment and run tracking for planned work, active execution, blockers, validation, review, and closeout.
- Project-internal worktree isolation under `.worktrees/` for execution tasks.
- Branch and PR mapping that separates internal `EDC-PR-###` identifiers from GitHub PR numbers.
- Evidence-before-claim validation records using non-secret durable files.
- Desktop surfaces under `apps/l1gov-desktop-client/` in future implementation slices only.
- Python governance/delivery contracts under `nexus/governance/` remain the accepted EDC-PR-002/003 foundation.
- Codex planning docs under `docs/codex/`.
- Repo-native reference mapping for accepted Shared Docs / SecondBrain design inputs.

## Out of Scope

- Treating EDC-PR-004 / GitHub PR #30 or EDC-PR-005 / GitHub PR #31 as the accepted UAT baseline.
- Single-screen UI sprawl that uses scroll anchors instead of real navigation/page boundaries.
- Production readiness or deployment.
- Cloud multi-tenant service behavior, billing, organizations, or mobile clients.
- Always-on autonomous daemon behavior.
- Live dispatch, controller activation, adapter transport activation, private agent invocation, dependency installation, or default-on runtime startup without explicit owner authorization.
- OpenClaw private sessions, auth, token, cache, logs, cookies, sqlite, SSH keys, or private generated material.
- Copying Multica's implementation stack, database, deployment, service architecture, or code.
- Treating Shared Docs, SecondBrain, or external agent-platform notes as Nexus source authority.
- Assigning Nova/OpenClaw Nexus planning, execution, delivery, review-ledger, or periodic-review ownership.
- Dependency updates unless a task card explicitly authorizes them.
- Cleanup, deletion, merge, or branch mutation outside the branch/worktree explicitly named by the task.

## File Boundaries For EDC-PR-006

Allowed areas:

- `docs/codex/TARGET.md`
- `docs/codex/SCOPE.md`
- `docs/codex/SPEC.md`
- `docs/codex/UX_SPEC.md`
- `docs/codex/PR_PLAN.md`
- `docs/codex/SECOND_BRAIN_REFERENCE_MAP.md` only if a reference note is needed
- `docs/codex/UX_REPLAN_EDC_PR_006.md`

Excluded areas:

- product/runtime/source implementation;
- `apps/l1gov-desktop-client/**` edits;
- `nexus/governance/**` edits;
- tests, package locks, dependency files, generated output, runtime startup, and build output;
- verification evidence deletion/restoration or dirty worktree cleanup;
- branches or worktrees other than `codex/edc-pr-006-ux-reset-workbench`.

## Future Implementation Candidate Boundaries

Future implementation slices may touch these areas only when their task cards authorize them:

- `apps/l1gov-desktop-client/src/**`
- `apps/l1gov-desktop-client/scripts/**`
- `apps/l1gov-desktop-client/src-tauri/src/**`
- `apps/l1gov-desktop-client/src-tauri/tauri.conf.json`
- `nexus/governance/**`
- `nexus/governance/tests/**`

Future slices must still exclude unless separately authorized: `.env*`, `node_modules/`, `src-tauri/gen/`, `src-tauri/target/`, `.edc-build/`, generated build outputs, sqlite databases, cache/log/session/auth/token/cookie/SSH directories, and old PR #22 evidence packages.

## Local Test NATS Boundary

If a future slice needs NATS, use only the dedicated Nexus local-test broker:

- NATS: `127.0.0.1:7422`
- Monitor: `http://127.0.0.1:8422/varz`

Do not use or mutate OpenClaw live NATS `127.0.0.1:4222` unless Alex explicitly authorizes it.

## UAT Boundary

The next owner UAT checkpoint is after EDC-PR-010. Codex local testing is not owner UAT. Owner UAT requires Alex observation or explicit owner-provided results. Codex must not claim owner acceptance, UAT PASS, merge approval, production readiness, or live readiness.

## Shared Docs And SecondBrain Boundary

Shared Docs can provide historical governance/design/evidence context. SecondBrain can provide curated reference patterns. Neither creates implementation scope by itself.

Multica remains an IA/product reference only. It does not authorize dependency installation, code copying, runtime adoption, service architecture changes, or external platform integration.
