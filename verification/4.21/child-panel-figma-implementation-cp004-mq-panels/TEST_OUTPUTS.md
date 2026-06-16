# Test Outputs

## TDD Red Check

`python -m pytest nexus/governance/tests/test_client_desktop_surface_slice012.py -q`

Initial CP-004 tests failed before implementation:

- `KeyError: 'mq_management'`
- missing `mq_queue_overview`
- missing `Queue Overview`
- missing `queue_execution`

## Verification Commands

`git diff --check origin/codex/4.21-real-testproject-e2e-uat...HEAD`

Result: exit 0, clean.

`python -m pytest nexus/governance/tests/test_client_desktop_surface_slice012.py -q`

Result: `25 passed in 0.03s`.

`python -m pytest nexus/governance/tests/test_real_uat_desktop_bridge.py -q`

Result: `3 passed in 0.02s`.

`python -m pytest nexus/governance/tests/test_local_app_shell_contract.py nexus/governance/tests/test_local_app_workspace_picker.py nexus/governance/tests/test_local_app_menu_command_map.py nexus/governance/tests/test_local_app_projection_surfaces.py nexus/governance/tests/test_local_app_read_only_mode.py nexus/governance/tests/test_local_app_no_go.py -q`

Result: `76 passed in 0.19s`.

`python -m pytest nexus/governance/tests -q`

Result: `662 passed in 0.83s`.

`node scripts/verify-fixture.mjs` using bundled Codex Node from `C:\Users\John\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe`

Result: `slice012 desktop real UAT surface verified`.

`npm test`

Result: local shell does not expose `npm` on PATH. The package test script is `node scripts/verify-fixture.mjs`; that verifier was run directly with bundled Node and passed.

`Get-ChildItem verification/4.21 -Recurse -Filter *.json | ForEach-Object { $null = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json }`

Result: `JSON_PARSE_OK`.