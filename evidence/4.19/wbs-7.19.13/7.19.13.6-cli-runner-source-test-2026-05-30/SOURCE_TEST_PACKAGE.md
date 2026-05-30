# WBS 7.19.13.6 CliCodexSessionRunner Source/Test Package

Owner: Thunder, Codex App runtime call sign
Requester / decision authority: Alex
Reviewer: Nova
Prepared: 2026-05-30
Final candidate verdict: READY_FOR_NOVA_SOURCE_TEST_REVIEW

## Scope

This package implements and validates a source-level `CliCodexSessionRunner` candidate from the accepted Jarvis CLI design and corrected Option A proof.

This is not a live worker/UAT package. It does not start a persistent listener, governed broker dispatch, UAT, Business Command, broker/config/credential mutation, WindowsApps permission mutation, install repair, private-agent invocation, merge/deploy, PASS, final PASS, runtime promotion, or live-readiness path.

## Branch and Baseline

- Branch: `codex/wbs-7-19-13-6-codex-session-runner-cli`
- Base: `origin/master@71b101363efc5b6462dcb06d83cd7f580e865cfa`
- Accepted adapter branch integrated: `origin/codex/wbs-7-19-13-codex-runtime-adapter@9797addfc4f1b323a0124bac095a235a51a60332`
- Option A proof branch reference: `origin/codex/wbs-7-19-13-5-pre-edit-package`
- Option A accepted proof commit referenced by user/Nova: `6b0f27a8152dede25340f61db18491ab3662d940`

## Source Changes

Changed after accepted adapter integration:

- `nexus/mq/codex_session_runner.py`
- `nexus/mq/tests/test_codex_session_runner.py`

Implemented behavior:

- `DisabledCodexSessionRunner` remains unchanged and disabled by default.
- `CliCodexSessionRunner` is a source-level candidate only; it is instantiated explicitly and is not wired into a live worker start path.
- Explicit configured CLI path is preferred.
- Configured CLI path must pass probe contract.
- AppData-local fallback discovery is supported through `discover_appdata_codex_cli_candidates`.
- AppData fallback selects the newest passing version.
- Ambiguous same-version passing candidates fail closed with `CODEX_CLI_AMBIGUOUS_CANDIDATES`.
- WindowsApps/PATH access failure is represented as `CODEX_CLI_ACCESS_DENIED`.
- stdout parser tolerates UTF-8 BOM and UTF-16 BOM.
- stdout parser accepts only JSON object lines as Codex events and separates non-JSON stdout chatter.
- stderr capture is recorded separately as evidence.
- timeout path returns `CODEX_CLI_TIMEOUT` and records process cleanup evidence.
- successful source-level process result maps to non-business `completed_execution` status with evidence refs only; it is not PASS, final PASS, runtime promotion, or live-readiness.

## Path-Selection Rule Implemented

1. Prefer explicit configured CLI path.
2. Configured path must pass version/help/exec-help probe.
3. If no configured path exists, discover AppData-local candidates.
4. Probe each candidate.
5. Select the newest passing candidate by parsed semantic version.
6. If the newest version is tied across multiple candidates, fail closed with `CODEX_CLI_AMBIGUOUS_CANDIDATES`.
7. If only WindowsApps/PATH candidate fails with `Access is denied`, return `CODEX_CLI_ACCESS_DENIED` and do not mutate permissions.

## Tests Added

Added focused source tests for:

- configured path preference
- AppData fallback newest passing candidate
- WindowsApps `Access is denied` fail-closed behavior
- ambiguous same-version candidate fail-closed behavior
- optional UTF-8 BOM tolerance and non-JSON stdout separation
- successful CLI process mapping to evidence refs
- timeout/cleanup mapping without PASS claim

Existing tests still verify:

- bounded non-business request validation
- secret-like request rejection
- disabled runner remains blocked and does not start live Codex

## Verification

Logs:

- `logs/compileall_nexus_mq.log`: `python -m compileall nexus/mq`
- `logs/focused_codex_tests.log`: focused Codex adapter/session/worker tests
- `logs/full_nexus_mq_tests.log`: full `nexus/mq/tests` suite
- `logs/git_diff_check.log`: diff hygiene
- `logs/secret_and_no_go_scan.log`: high-confidence secret and no-go scan
- `logs/refs.log`: branch/head/base/status anchors
- `logs/clean_export_sha256_verify.log`: clean-export checksum verification

Observed results:

- compileall: passed
- focused Codex tests: `24 passed`
- full `nexus/mq/tests`: `654 passed, 19 warnings`
- `git diff --check`: passed
- secret/no-go scan: no high-confidence matches; existing token fixture is documented as intentional validation test data

## Completed Evidence

- Source implementation and focused tests are file-backed.
- Runtime path remains source-test only.
- No live worker, persistent listener, governed broker dispatch, UAT, Business Command, merge/deploy, runtime promotion, or live-readiness was performed.

## Remaining Blockers / Required Nova Decisions

- Nova must review and accept this WBS 7.19.13.6 source/test package before any later WBS 7.19.13.7 bounded non-business Codex Agent flow UAT can open.
- Live worker start remains unauthorized.
- Governed broker dispatch remains unauthorized.
- Business Command remains unauthorized.
- PASS/final PASS/live-readiness remain unauthorized.

## No-Go Statement

This package does not authorize or perform live worker start, persistent listener start, governed broker dispatch, UAT, Business Command, broker/config/credential mutation, WindowsApps permission mutation, install repair, private-agent invocation, merge/deploy, PASS, final PASS, runtime promotion, or live-readiness.
