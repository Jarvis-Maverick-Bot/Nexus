# Test Outputs

## Targeted Desktop Surface Tests

Command:

```powershell
python -m pytest nexus/governance/tests/test_client_desktop_surface_slice012.py -q
```

Result:

```text
17 passed in 0.03s
```

## Real UAT Desktop Bridge Tests

Command:

```powershell
python -m pytest nexus/governance/tests/test_real_uat_desktop_bridge.py -q
```

Result:

```text
3 passed in 0.02s
```

## Local App Contract Tests

Command:

```powershell
python -m pytest nexus/governance/tests/test_local_app_shell_contract.py nexus/governance/tests/test_local_app_workspace_picker.py nexus/governance/tests/test_local_app_menu_command_map.py nexus/governance/tests/test_local_app_projection_surfaces.py nexus/governance/tests/test_local_app_read_only_mode.py nexus/governance/tests/test_local_app_no_go.py -q
```

Result:

```text
76 passed in 0.17s
```

## Full Governance Tests

Command:

```powershell
python -m pytest nexus/governance/tests -q
```

Result:

```text
654 passed in 0.85s
```

## Desktop Fixture Verifier

Command:

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

Result: exit 0. PowerShell displayed CRLF normalization warnings only; no whitespace errors.
