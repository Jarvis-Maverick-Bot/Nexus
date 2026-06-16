# Source Checkout Proof

## Repository

Command:

```powershell
git rev-parse --show-toplevel
```

Result:

```text
D:/Projects/Nexus_cp001_child_panel_shell
```

## Branch

Command:

```powershell
git branch --show-current
```

Result:

```text
codex/4.21-child-panel-cp005-auxiliary-surfaces
```

## HEAD

Command:

```powershell
git rev-parse HEAD
```

Result:

```text
4ad9f6260697134f1587760a0af84a1e7003af50
```

## Working Tree During Evidence Capture

Command:

```powershell
git status --short
```

Result showed CP-005 implementation files modified and the CP-005 evidence directory untracked. No files were staged.
