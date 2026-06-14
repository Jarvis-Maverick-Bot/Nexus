# L1GOV-SLICE-012 UX Client Test Surface

This static browser surface supports UX-driven review of the 4.21 Layer 1 Governance client direction. It is fixture backed and non-authoritative.

Open from the repository root:

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory nexus/governance/client_test_surface/slice012
```

Then open:

```text
http://127.0.0.1:8765/index.html
```

The page uses deterministic fixture data from `fixtures/slice012_state.json`. Browser interactions change display state only. Kernel and Governance Service remain authority, and the surface performs no canonical mutation.
