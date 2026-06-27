# Nexus Agent Coding Team Workbench Shell

Slice: `EDC-PR-007`

This is the Windows-first desktop shell surface for the Nexus Agent Coding Team Workbench. It uses deterministic fixture data and does not connect to any daemon, controller, transport, route, private agent, broker, NATS endpoint, or canonical state writer.

## Runtime Boundary

EDC-PR-007 does not authorize desktop startup, dependency installation, Tauri dev/build, Cargo commands, broker/NATS mutation, live dispatch, merge approval, owner UAT acceptance, UAT PASS, production readiness, or live readiness.

The shell is fixture-only and non-authoritative. Repository docs, task cards, validation evidence, GitHub PR mappings, and owner decisions remain authoritative.

## Shell Scope

The first screen identifies `Nexus Agent Coding Team Workbench` and provides real stateful navigation for these shell-level views:

- Work Items
- Work Item Detail
- Agents
- Runtime / Worktrees
- Evidence / Runs
- PR / UAT Closeout
- Inbox / Attention
- Settings / Boundaries

Each view is intentionally shallow in EDC-PR-007. Detailed implementation belongs to EDC-PR-008 through EDC-PR-010.

## Launch Notes

Future startup commands require explicit task-card authorization. When later authorized, a reviewer workstation needs Node/npm, Rust/Cargo, and WebView2 runtime available for Tauri startup.

## Superseded Prototype Boundary

EDC-PR-004 / GitHub PR #30 and EDC-PR-005 / GitHub PR #31 are superseded UX prototypes. They are not the active implementation baseline and not the UAT baseline.
