# No-Go Scan Results

## nexus.mq Import Scan

Command:

```powershell
rg -n "nexus\.mq|from nexus\.mq|import nexus\.mq" apps/l1gov-desktop-client/src apps/l1gov-desktop-client/src-tauri/src nexus/governance/tests/test_client_desktop_surface_slice012.py
```

Result: no matches, exit 1 from `rg` because no matches were found.

## Changed App Source No-Go Scan

Command:

```powershell
rg -n -i "private-agent invocation|live invocation|dispatch execution|controller call|route activation|adapter activation|transport activation|work-packet execution|owner-path call|lower-layer request submission|production readiness|deploy readiness|continuity activation|final pass" apps/l1gov-desktop-client/src apps/l1gov-desktop-client/src-tauri/src
```

Result:

```text
apps/l1gov-desktop-client/src\index.html:74:              <dt>Live invocation</dt>
```

Classification: display-only ContextEnvelope field label. It is not an executable path, button, Tauri bridge command, route, adapter, controller, dispatch, deploy, credential, or private-agent invocation.

## Broad Governance Test Fixture Scan

The broad scan across `nexus/governance/tests` also finds existing negative no-go fixtures and assertions for forbidden terms. These are test evidence and regression fixtures, not executable app behavior.

## Conclusion

No CP-001 executable runtime/live/dispatch/controller/route/adapter/transport/deploy/config/credential/private-agent path was added.
