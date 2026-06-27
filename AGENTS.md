# Nexus Codex Operating Guide

This repository uses Codex as the primary planning, execution, verification, and handoff surface for Nexus work. Do not depend on Mac OpenClaw Agent prompts, private sessions, auth, token, cache, or log content to move project work forward.

## Project Root

Use this checkout root as the repository root for the active branch/worktree.

Nexus is a mixed repository:

- Python package and tests: `nexus/`, `governance/`, `games/`, `tests/`
- Desktop client: `apps/l1gov-desktop-client/`
- Codex SDK sidecar: `tools/codex-sdk-sidecar/`
- Documentation and evidence: `docs/`, `evidence/`, `verification/`, `handoff/`

## Safety Boundaries

- Do not commit credentials, tokens, private hostnames, private operator context, `.env` files, sqlite databases, caches, logs, cookies, SSH keys, or private session material.
- Use only durable non-secret repository content and explicit user-provided material.
- Do not claim production readiness, live-readiness promotion, default-on dispatch, runtime start authorization, merge approval, UAT PASS, final PASS, grant approval, or external adoption without public verifiable authority.
- Treat historical evidence as a record of governed work, not as blanket authorization for live runtime behavior.

## Current Branch Intent

Branch `codex/edc-governance-desktop` is the planning reset branch for `EDC-PR-001`.

The next Nexus product target is the Agent Coding Team Delivery Console: a local-first project delivery workspace where Codex Planning, Codex Execution, and owner UAT can move work through bounded task cards, isolated worktrees, validation evidence, PR review, and delivery closeout.

Internal delivery identifiers use `EDC-PR-###`. GitHub pull request numbers are external system identifiers and must be recorded as mappings in `docs/codex/PR_PLAN.md`; do not use GitHub PR numbers as the internal work sequence.

`EDC-PR-000` maps to the closed superseded GitHub PR #22 / `codex/4.21-real-testproject-e2e-uat`. That branch may be used as a reference for lessons learned, but do not cherry-pick it wholesale. Its evidence-heavy, display-only implementation is not the new EDC delivery baseline.

## Planning Workflow

Codex Planning owns the planning loop under `docs/codex/`:

- Read current repo, branch, worktree, PR, docs, validation, and evidence state before writing plans.
- Keep target, scope, spec, PR plan, decisions, validation, and handoff notes in durable markdown.
- Convert planning work into bounded Execution or UAT task cards.
- Require evidence-before-claim: every completion claim needs a validation command or a documented reason validation was not run.

## Planning Role Boundary

Nexus Planning sessions follow `D:\Codex-Space\docs\CODEX_PLANNING_ROLE_STANDARD.md`.

Planning may inspect repo, branch, worktree, PR, docs, validation, and evidence state; maintain `AGENTS.md` and `docs/codex/*`; create task cards; review Execution reports; and run non-destructive planning validation.

Planning must not directly edit product code, tests, UI, runtime behavior, migrations, providers, scripts, or application behavior.

Implementation, cleanup, and UAT execution must be assigned through explicit task cards with branch/worktree, scope, non-goals, guardrails, validation, and completion-report requirements.

## Shared Docs And SecondBrain Boundary

Shared Docs and SecondBrain are reference surfaces, not Nexus delivery authority.

Authority order for Nexus work:

1. Alex's current explicit instruction.
2. Nexus repo current branch, PR state, tests, and repo-native docs.
3. Current accepted Nexus design or implementation-design documents.
4. Accepted historical review evidence and handoff indexes.
5. Approved organization governance doctrine when governance behavior is in scope.
6. Shared Docs `SecondBrain/` as curated reference memory only.

SecondBrain notes may inform Nexus design only through explicit citation in `docs/codex/SECOND_BRAIN_REFERENCE_MAP.md` or another current Nexus design artifact. SecondBrain material must not create Nexus scope by itself, must not assign Nova/OpenClaw delivery ownership, and must not override repo facts or current owner instruction.

## Execution Task Card Contract

Every Planning to Execution handoff must include:

- Background
- Goal
- Scope
- Non-goals
- File boundaries
- Acceptance criteria
- Validation commands
- Risks
- Write-back location

## Known Validation Entry Points

Use the narrowest command that matches the changed surface, then broaden when risk warrants it:

```powershell
python -m pytest
python -m pytest nexus/governance/tests
npm test --prefix apps/l1gov-desktop-client
```

Desktop startup and Tauri build commands require explicit authorization because they can materialize dependencies, generated files, and build outputs.
