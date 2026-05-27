# 4.19 Real-Agent Operating Environment Implementation Evidence

Owner: Thunder
Requester: Alex via Nova
Branch: `codex/4.19-real-agent-operating-env`
Implementation base dependency: `366377009940b0feef0fb808b582961d044ea777`
Merge-base with `origin/master`: `f27a7bcd3ecc720ee28c676fb9f0ecb0ddbe2a24`
Evidence package: `D:\Projects\Nexus\evidence\4.19\real-agent-operating-env\implementation-2026-05-27-thunder\`
Verdict: `READY_FOR_NOVA_REVIEW`

## Boundary

This is source/evidence implementation only. No runtime/UAT, broker/config/credential mutation, private-agent invocation, live business execution, deploy, merge approval, WBS PASS, `THUNDER_REAL_AGENT_OPERATING_ENVIRONMENT_READY`, or final readiness claim was performed.

## Implementation Summary

- Added source-only Runtime Lifecycle Controller for registration, readiness refs, heartbeat freshness, lifecycle controls, eligibility decisions, and reservation leases.
- Added heartbeat/presence controller, eligibility/reservation publish guard, integrated evidence package classifier, readiness taxonomy guard, A2A placeholder marker, runtime metrics projection, Agent Access projection fields, and role-aware Runbook.
- Hardened resident-controller dispatch so assignment publish requires explicit lifecycle decision id plus active reservation lease id before duplicate suppression can return accepted.
- Updated resident live loop to use an injected lifecycle provider for deterministic source-only tests; missing provider fails closed instead of minting lifecycle truth from Dispatch/UAT config.
- Normalized Candidate Adapter profile heartbeat defaults to `15s` interval and `60s` TTL.

## Verification

- `git diff --check`: `EXIT_CODE: 0` in `git-diff-check.txt`.
- `python -m compileall -q nexus/mq`: `EXIT_CODE: 0` in `compileall-nexus-mq.txt`.
- Focused real-agent pytest: `42 passed in 0.22s` in `focused-real-agent-pytest.txt`.
- Candidate Adapter + resident-controller focused slice: `81 passed in 3.18s` in `candidate-resident-focused-pytest.txt`.
- Regression slice: `85 passed in 2.52s` in `regression-slice-pytest.txt`.
- Full MQ suite: `588 passed, 19 warnings in 17.81s` in `full-mq-pytest.txt`.
- High-confidence secret scan: no matches in `secret-scan.txt`.

## Evidence Files

- `changed-files-source.txt`
- `changed-files-all.txt`
- `diff-summary.txt`
- `branch-base.txt`
- `git-diff-check.txt`
- `compileall-nexus-mq.txt`
- `focused-real-agent-pytest.txt`
- `candidate-resident-focused-pytest.txt`
- `regression-slice-pytest.txt`
- `full-mq-pytest.txt`
- `secret-scan.txt`
- `runbook-completeness.txt`
- `no-a2a-evidence.txt`
- `diagnostic-readiness-evidence.txt`
- `design-to-code-deviation-report.md`
- `CODE_TO_DESIGN_TRACEABILITY.md`
- `SHA256SUMS.txt`
- `sha256-verify.txt`

Manifest convention: `SHA256SUMS.txt` and `sha256-verify.txt` are excluded from the manifest to avoid self-referential checksum churn.

## Known Gaps / Later Gates

- Real NATS/client wiring and distributed runtime operation remain later runtime/UAT gate work.
- No global `nexus candidate` executable was added; CLI remains bounded to existing module invocation.
- No final readiness or WBS PASS claim is made by this package.
