# No-Go Scan Results

## Forbidden Auxiliary Affordance Scan

Command:

```powershell
rg -n -i 'submit canonical|make canonical|approve baseline|bypass no-go|override no-go|deploy now|execute refresh|mutate projection|submit live|dispatch now|call controller|closeout' apps\l1gov-desktop-client\src
```

Result: exit 1, no matches.

## Tauri Bridge Diff Scan

Command:

```powershell
git diff --name-only -- apps\l1gov-desktop-client\src-tauri
```

Result: no changed files.

## Existing Invoke Surface Scan

Command:

```powershell
rg -n --fixed-strings 'invoke(' apps/l1gov-desktop-client/src/main.js
```

Result:

```text
272:function invoke(command, args = {}) {
389:  const payload = await invoke("read_test_project_projection");
395:  const payload = await invoke("create_test_project");
403:  await invoke("cleanup_test_project");
413:  const payload = await invoke("save_project_init_draft", { payloadJson });
```

Classification: existing Slice 012 real local UAT bridge calls only. CP-005 did not add a new Tauri command or execution bridge.

## Runtime / Dispatch / Controller Scan

Command:

```powershell
rg -n -i 'private-agent invocation|live invocation|dispatch execution|controller call|route activation|adapter activation|transport activation|queue execution|message execution|replay execution|runtime replay|production readiness|deploy readiness|continuity activation|final pass' apps\l1gov-desktop-client\src apps\l1gov-desktop-client\src-tauri\src nexus\governance\tests\test_client_desktop_surface_slice012.py
```

Findings:

- `apps/l1gov-desktop-client/src/index.html:74` contains the existing ContextEnvelope display label `Live invocation`.
- `nexus/governance/tests/test_client_desktop_surface_slice012.py` contains existing negative fixture terms and no-go test strings.

Classification: display label and negative test fixtures only. No executable runtime, dispatch, controller, route, adapter, transport, MQ, private-agent, production-readiness, or final PASS path was added.
