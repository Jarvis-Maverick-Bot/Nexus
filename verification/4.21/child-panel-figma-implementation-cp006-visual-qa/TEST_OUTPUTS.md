# Test Outputs

## Focused Governance Test

Command:

```powershell
python -m pytest nexus/governance/tests/test_client_desktop_surface_slice012.py -q
```

Raw output: `outputs/pytest-output.txt`.

## App Fixture Verifier

Command:

```powershell
& 'C:\Users\John\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' apps\\l1gov-desktop-client\\scripts\\verify-fixture.mjs
```

Raw output: `outputs/bundled-node-verifier-output.txt`.

## json.tool

Raw output: `outputs/json-tool-output.txt`.

## Diff Check

Raw output: `outputs/git-diff-check-output.txt`.

## npm/npx PATH Limitation

`npx` is not available on PATH, so screenshot QA used bundled Playwright with installed Chrome and did not mutate package-manager state. Raw output: `outputs/npx-prerequisite-output.txt`.
