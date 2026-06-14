# Nexus L1 Governance Desktop UX Test Surface

Slice: `L1GOV-SLICE-012`

This is the Windows-first Tauri desktop app test surface for UX-driven review of 4.21 Layer 1 Governance flows. It uses deterministic fixture data and does not connect to any daemon, controller, transport, route, private agent, or canonical state writer.

## Windows-first launch

Prerequisites for a reviewer workstation:

- Node/npm available on PATH.
- Rust/Cargo available on PATH.
- WebView2 runtime available on Windows.

Launch command from this directory:

```powershell
npm install
npm run dev
```

The expected app window title is `Nexus L1 Governance UX Test Surface`.

Verification in the Slice 012 evidence run used an app-local Rust GNU toolchain and portable w64devkit under `.toolchain/`, with no root package-manager or system PATH mutation:

```powershell
npm run build:windows-gnu
src-tauri\target\x86_64-pc-windows-gnu\debug\nexus-l1gov-desktop-client.exe
```

## macOS compatibility

The app structure is Tauri-compatible for macOS, but macOS launch evidence is not verified on macOS in this Windows run. A macOS reviewer should run the same install and launch commands from this directory after installing platform prerequisites.

## Boundary

Kernel and Governance Service remain authority. The desktop app is non-authoritative and renders fixture-backed display state only.

PR #20 remains draft/reference only and must not be merged as final Slice 012 delivery.
