# Roadmap

This roadmap is intentionally public-safe and conservative. It describes direction, not a promise of dates or production readiness.

## Phase 1 - Public Repository Readiness

- Refresh README for external readers.
- Add license, contribution guide, security policy, issue templates, and pull-request template.
- Add project status and roadmap documents.
- Add curated public-safe explanations for evidence and governance artifacts.

## Phase 2 - Developer Onboarding

- Move stable setup instructions into `docs/quickstart.md`.
- Add a small "first run" example.
- Add labels and starter issues for documentation, tests, and governance examples.
- Add lightweight CI for tests that can run in a public GitHub environment.

## Phase 3 - Governance Model Documentation

- Document role/authority model.
- Document gate types and promotion boundaries.
- Document evidence-before-claim pattern.
- Document fail-closed examples.

## Phase 4 - Runtime Lifecycle Examples

- Provide a minimal candidate runtime lifecycle example:
  - registration
  - readiness
  - heartbeat
  - bounded assignment
  - result candidate
  - offline/cleanup
- Keep examples synthetic and non-production.

## Phase 5 - Ecosystem Integration

- Improve adapter examples for agentic development workflows.
- Document how Nexus can wrap external agents without granting unchecked authority.
- Build more public-safe examples of review, UAT, and release gates.
