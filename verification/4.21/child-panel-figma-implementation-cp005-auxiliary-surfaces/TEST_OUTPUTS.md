# Test Outputs

## CP-005 Red Run

Command:

```powershell
python -m pytest nexus/governance/tests/test_client_desktop_surface_slice012.py -q
```

Result before implementation:

```text
4 failed, 25 passed in 0.18s
```

Expected failures were missing CP-005 auxiliary surface fixture keys, renderer hooks, display-only contract strings, and the existing app copy containing the forbidden static affordance term `closeout`.

## Focused Governance Test

Command:

```powershell
python -m pytest nexus/governance/tests/test_client_desktop_surface_slice012.py -q
```

Result after implementation:

```text
29 passed in 0.05s
```

## App Fixture Verifier

Attempted command:

```powershell
npm test
```

Result:

```text
npm : The term 'npm' is not recognized as the name of a cmdlet, function, script file, or operable program.
```

Fallback command using the bundled Node runtime, running the same verifier script:

```powershell
& 'C:\Users\John\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' scripts\verify-fixture.mjs
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

Result: exit 0. PowerShell output included expected CRLF conversion warnings only.
