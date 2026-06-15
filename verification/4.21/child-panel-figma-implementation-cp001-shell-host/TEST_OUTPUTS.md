# Test Outputs

## TDD Red Run

Command:

```powershell
python -m pytest nexus/governance/tests/test_client_desktop_surface_slice012.py -q
```

Initial CP-001 tests failed as expected:

- missing `context-envelope`
- visible `Mission Control` label still present
- missing shell panel routes

Compact layout contract was also added red-first and failed on missing responsive order.

## Targeted CP-001 Tests

Command:

```powershell
python -m pytest nexus/governance/tests/test_client_desktop_surface_slice012.py -q
```

Result:

```text
14 passed in 0.02s
```

## Full Governance Tests

Command:

```powershell
python -m pytest nexus/governance/tests -q
```

Result:

```text
651 passed in 1.11s
```

## Desktop Fixture Verifier

Command:

```powershell
& 'C:\Users\John\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' scripts/verify-fixture.mjs
```

Working directory:

```text
D:\Projects\Nexus_cp001_child_panel_shell\apps\l1gov-desktop-client
```

Result:

```text
slice012 desktop real UAT surface verified
```

## Diff Check

Command:

```powershell
git diff --check
```

Result: exit 0. Git emitted Windows line-ending warnings only.
