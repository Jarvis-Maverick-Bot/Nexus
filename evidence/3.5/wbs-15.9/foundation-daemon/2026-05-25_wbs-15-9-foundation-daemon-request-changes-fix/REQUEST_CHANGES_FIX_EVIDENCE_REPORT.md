# WBS 15.9 Foundation Daemon Request Changes Fix Evidence

Owner: Thunder
Requester: Alex via Nova
Candidate verdict: PASS

## Git Baseline

- Repo: `D:\Projects\Nexus`
- Branch: `codex/wbs-15-9-layer3-foundation-daemon`
- Base branch: `origin/master`
- Base commit: `bb241891a97057891d498b12f912a37d46c0657b`
- Merge-base: `bb241891a97057891d498b12f912a37d46c0657b`
- Prior reviewed head: `43edfa47bb8e71e5fdb04958dc636d14c778444c`
- Correction source commit: `974d2a1a5dee74db7b6d698bf2a7956464600008`
- Evidence commit: branch head after this package is committed

## Blocking Findings Addressed

1. Business/private-agent-like dispatch is now rejected before intake ACK.
   - Added negative tests for `Business_Message` and `private_agent.invoke` / `private_agent_invocation`.
   - Runtime returns no ACK and writes no durable intake record on these paths.
2. Intake ACK is now emitted only after pre-ACK evidence and durable intake record creation.
   - Added evidence-failure negative test confirming no ACK and no durable record when evidence is unavailable.
3. `readiness` now exits nonzero when `overall_ready=false`.
   - CLI returns code `2` while still emitting structured readiness JSON.
4. Lifecycle CLI surface now includes `run`, `drain`, and `stop`.
   - `run` is present but blocked in source gate with exit code `2` and `daemon_started=false`.
   - `drain` and `stop` emit non-live source-only JSON and do not signal or start any process.
5. Evidence checksums were regenerated after all file writes.
   - New package includes fresh `SOURCE_SHA256SUMS.txt` and `EVIDENCE_SHA256SUMS.txt`.
   - Previous package checksum manifests were also refreshed in this correction commit.

## Verification

- Focused foundation daemon tests: `27 passed`
  - Evidence: `focused-tests.log`
- Planned non-live regressions: `52 passed`
  - Evidence: `regression-tests.log`
- Compile check: pass
  - Evidence: `compileall.log`
- Diff whitespace check: pass
  - Evidence: `git-diff-check.log`
- CLI validate committed YAML: pass
  - Evidence: `cli-validate-config.json`
- CLI `start-once`: pass, `daemon_started=false`
  - Evidence: `cli-start-once.json`
- CLI `readiness`: structured JSON emitted, exit code verified as `2` because `overall_ready=false`
  - Evidence: `cli-readiness.json`
- CLI `run`: structured JSON emitted, exit code verified as `2`, blocked by source gate
  - Evidence: `cli-run.json`
- CLI `drain` and `stop`: structured non-live JSON emitted
  - Evidence: `cli-drain.json`, `cli-stop.json`

## Secret Scan

- Non-test changed source/config/template scan: no high-confidence secret matches.
  - Evidence: `secret-scan-non-test.log`
- Full changed-file scan has one intentional negative-test fixture: `sqlite:///tmp/db?token=abc` in `test_foundation_daemon_config.py`.
  - Evidence: `secret-scan.log`
  - Classification: test fixture only, not a credential.

## Checksum Evidence

- Source changed-file checksums: `SOURCE_SHA256SUMS.txt`
- Evidence file checksums: `EVIDENCE_SHA256SUMS.txt`
- Changed source file list: `changed-files-source.txt`

## Runtime Posture / No-Go Confirmation

- No daemon was installed, enabled, or started.
- No live NATS listener was launched.
- No broker/server/config/credential mutation was performed.
- No live publish, business dispatch, private-agent invocation, deployment, merge, 4.19 integrated UAT, WBS PASS, or final acceptance was performed.

## Deviations / Blockers

- No blockers for source re-review.
