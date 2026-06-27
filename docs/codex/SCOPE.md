# Nexus Agent Coding Team Delivery Console Scope

Date: 2026-06-27
Branch: `codex/edc-governance-desktop`
Internal PR: `EDC-PR-001`

## In Scope

Product scope for the next stage:

- A local-first Agent Coding Team Delivery Console.
- One active project workspace at a time for the MVP.
- Durable work items with task card fields required by the Nexus Codex operating guide.
- Agent roles for Codex Planning, Codex Execution, and owner UAT review.
- Assignment and run tracking for planned work, active execution, blockers, validation, review, and closeout.
- Project-internal worktree isolation under `.worktrees/` for execution tasks.
- Branch and PR mapping that separates internal `EDC-PR-###` identifiers from GitHub PR numbers.
- Evidence-before-claim validation records using non-secret durable files.
- Desktop surfaces under `apps/l1gov-desktop-client/` that show backlog, agents, active runs, validation evidence, PR status, and UAT state.
- Python governance/delivery contracts under `nexus/governance/` when implementation slices need shared behavior.
- Codex planning docs under `docs/codex/`.
- Repo-native reference mapping for accepted Shared Docs / SecondBrain design inputs.

## Out of Scope

- Production readiness or deployment.
- Cloud multi-tenant service behavior, billing, organizations, or mobile clients.
- Always-on autonomous daemon behavior.
- Live dispatch, controller activation, adapter transport activation, private agent invocation, dependency installation, or default-on runtime startup without explicit owner authorization.
- OpenClaw private sessions, auth, token, cache, logs, cookies, sqlite, or private generated material.
- Broad evidence-package migration from GitHub PR #22 / `EDC-PR-000`.
- Copying Multica's implementation stack or database/service architecture.
- Treating Shared Docs, SecondBrain, or external agent-platform notes as Nexus source authority.
- Assigning Nova/OpenClaw Nexus planning, execution, delivery, review-ledger, or periodic-review ownership.
- Large UI panel expansion that does not advance project delivery workflow.
- Dependency updates unless a task card explicitly authorizes them.
- Cleanup, deletion, merge, or branch mutation outside the branch/worktree explicitly named by the task.

## File Boundaries For EDC-PR-001

Allowed areas:

- `AGENTS.md`
- `docs/codex/**`

Excluded areas:

- product/runtime/source implementation;
- package locks, dependency files, generated output, runtime startup, and build output;
- verification evidence deletion/restoration or dirty worktree cleanup;
- branches or worktrees other than `codex/edc-governance-desktop`.

## Future Implementation Candidate Boundaries

Future implementation slices may touch these areas after owner approval:

- `apps/l1gov-desktop-client/src/**`
- `apps/l1gov-desktop-client/scripts/**`
- `apps/l1gov-desktop-client/src-tauri/src/**`
- `apps/l1gov-desktop-client/src-tauri/tauri.conf.json`
- `nexus/governance/**`
- `nexus/governance/tests/**`

Future slices must still exclude unless separately authorized:

- `.env*`
- `node_modules/`
- `src-tauri/gen/`
- `.edc-build/`
- generated build outputs
- sqlite databases
- cache/log/session/auth/token directories
- old GitHub PR #22 / `EDC-PR-000` verification evidence packages

## Local Test NATS Boundary

If a future slice needs NATS, use only the dedicated Nexus local-test broker:

- NATS: `127.0.0.1:7422`
- Monitor: `http://127.0.0.1:8422/varz`

Do not use or mutate any OpenClaw live NATS endpoint unless Alex explicitly authorizes it.

## UAT Boundary

Codex can start the desktop app only when Alex explicitly authorizes runtime startup. Codex local testing is not owner UAT. Owner UAT requires Alex observation or explicit owner-provided results.

## Shared Docs And SecondBrain Boundary

Shared Docs can provide historical governance/design/evidence context. SecondBrain can provide curated reference patterns. Neither creates implementation scope by itself.

For this branch, reusable SecondBrain inputs must be recorded as reference IDs or source-note paths in `docs/codex/SECOND_BRAIN_REFERENCE_MAP.md` before they influence implementation task cards.
