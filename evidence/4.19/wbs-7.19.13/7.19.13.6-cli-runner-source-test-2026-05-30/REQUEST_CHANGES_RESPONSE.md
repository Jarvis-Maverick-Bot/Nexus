# WBS 7.19.13.6 CliCodexSessionRunner Request-Changes Response

Owner: Thunder, Codex App runtime call sign
Requester / decision authority: Alex
Reviewer: Nova
Prepared: 2026-05-30
Final candidate verdict: READY_FOR_NOVA_SOURCE_TEST_REVIEW

## Review Result Received

Nova returned a second `REQUEST_CHANGES` for WBS 7.19.13.6 source/test branch `codex/wbs-7-19-13-6-codex-session-runner-cli` at `e00345701ed7b5a73ace159a22be88d4e56a2faf`.

Accepted as on-path:

- configured CLI path preference
- AppData fallback/newest candidate selection
- WindowsApps access-denied fail-closed selection
- BOM/non-JSON stdout filtering
- disabled runner remains default/fail-closed
- clean-export checksum verification and diff hygiene

WBS 7.19.13.6 is not accepted until this correction package is reviewed. WBS 7.19.13.7 remains blocked.

## Corrections Applied

### 1. Runner Result Contract

`CodexSessionRunnerResult` now carries source-testable fields for:

- `started`
- `exit_code`
- `error_code`
- `changed_file_refs`
- `disallowed_write_refs`
- `no_go_refs`
- `cleanup_refs`
- `drain_refs`
- `offline_refs`
- `result_candidate_ref`

Focused tests prove successful execution mapping, timeout mapping, cleanup refs, quarantine refs, and result candidate refs.

### 2. Duplicate / Idempotency Protection

`CliCodexSessionRunner` now keeps a per-assignment request fingerprint cache.

Implemented behavior:

- exact replay returns public status `blocked`, not `duplicate_suppressed`
- exact replay returns `CODEX_DUPLICATE_SUPPRESSED`
- exact replay reuses the previous `result_candidate_ref`
- exact replay adds `codex-cli://duplicate/replay-suppressed`
- changed request for the same `assignment_id` also returns `CODEX_DUPLICATE_SUPPRESSED`
- duplicate replay/conflict does not launch a second process
- `CODEX_DUPLICATE_REQUEST_CONFLICT` is not emitted without a reviewed addendum

### 3. Write-Boundary Enforcement

Implemented source-testable write guards:

- dirty-worktree preflight guard using `git status --short`
- pre/post Git status snapshots
- changed-file refs on result
- allowed write-surface checks from `request.allowed_write_surfaces`
- prohibited write-surface checks from `CodexCliRunnerConfig.prohibited_write_surfaces`
- disallowed writes quarantine with `CODEX_WRITE_SURFACE_VIOLATION`
- no-go writes quarantine with `CODEX_NO_GO_SCOPE_VIOLATION`
- drain/offline refs for quarantine paths
- pre/post Git status timeout, OS error, or nonzero exit fail closed instead of returning an empty clean snapshot
- pre-run Git status failure blocks before process launch
- post-run Git status failure quarantines with `codex-cli://drain/git-status-unavailable`

Focused tests prove dirty-worktree blocking, disallowed-write quarantine, no-go-write quarantine, no process launch on dirty/pre-status failure guards, and post-status failure quarantine.

### 4. CLI Probe Fail-Closed Behavior

`probe_codex_cli_path` now fails closed for version/help/exec-help:

- timeout: `CODEX_CLI_PROBE_TIMEOUT`
- permission error: `CODEX_CLI_ACCESS_DENIED`
- OS error: `CODEX_CLI_NOT_FOUND`
- nonzero version/help/exec-help remains explicit failure

Focused tests cover timeout, help permission error, and exec-help OS error.

### 5. Negative Path Tests

Added tests for:

- exact duplicate replay suppression using `CODEX_DUPLICATE_SUPPRESSED`
- changed duplicate request suppression using `CODEX_DUPLICATE_SUPPRESSED`
- absence of public `duplicate_suppressed` result status
- dirty worktree blocking
- Git status timeout/OS error/nonzero fail-closed behavior
- disallowed write-surface quarantine
- no-go write-surface quarantine
- result contract fields on success and timeout
- probe timeout/permission/OS-error fail-closed paths

## Verification

Updated logs:

- `logs/compileall_nexus_mq.log`
- `logs/focused_codex_tests.log`
- `logs/full_nexus_mq_tests.log`
- `logs/git_diff_check.log`
- `logs/secret_and_no_go_scan.log`
- `logs/refs.log`
- `logs/clean_export_sha256_verify.log`

Observed results:

- `python -m compileall nexus/mq`: passed
- focused Codex tests: `37 passed`
- full `nexus/mq/tests`: `667 passed, 19 warnings`
- `git diff --check`: passed
- high-confidence secret/no-go scan: passed
- clean-export checksum verification: passed

## No-Go Statement

No WBS 7.19.13.7 work was performed. No live worker, persistent listener, broker dispatch, UAT, Business Command, broker/config/credential mutation, WindowsApps permission mutation, install repair, private-agent invocation, merge/deploy, PASS, final PASS, runtime promotion, or live-readiness path was executed or claimed.
