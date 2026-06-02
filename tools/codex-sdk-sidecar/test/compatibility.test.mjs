import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { chmod, cp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { runRuntimeCompatibilityCheck } from "../src/compatibility.mjs";

const packageRoot = dirname(dirname(fileURLToPath(import.meta.url)));

class GoodCodex {
  startThread() {}
  resumeThread() {}
}

test("runtime compatibility writes evidence for pinned SDK and API surface", async () => {
  const root = await fixtureRoot();
  const evidencePath = join(root, "runtime_compatibility_check.json");

  const result = await runRuntimeCompatibilityCheck({
    packageRoot: root,
    evidencePath,
    sdkModule: { Codex: GoodCodex },
    sidecarProtocolVersion: "4.19.codex.sdk_sidecar.v1",
  });

  assert.equal(result.ok, true);
  const evidence = JSON.parse(readFileSync(evidencePath, "utf8"));
  assert.equal(evidence.ok, true);
  assert.equal(evidence.sdk.version, "0.135.0");
  assert.equal(evidence.sdk.transitive_codex_version, "0.135.0");
  assert.equal(evidence.api_surface.Codex, true);
  assert.equal(evidence.api_surface.startThread, true);
  assert.equal(evidence.api_surface.resumeThread, true);
  assert.equal(evidence.source_identity.bounded_source_identity, "bounded-untracked-sdk-bridge-source-state");
  assert.equal(evidence.sidecar_source_ref, "tools/codex-sdk-sidecar");
  assert.match(evidence.package_json.sha256, /^[a-f0-9]{64}$/);
  assert.match(evidence.package_lock.sha256, /^[a-f0-9]{64}$/);
  assert.equal(evidence.sidecar_protocol.event_mapping_contract_version, "4.19.codex.sdk_sidecar.v1");
  assert.equal(evidence.compatibility_result, "compatible");
  assert.deepEqual(evidence.errors, []);
});

test("runtime compatibility fails closed on SDK version mismatch", async () => {
  const root = await fixtureRoot({ packageDependency: "0.134.0" });

  const result = await runRuntimeCompatibilityCheck({
    packageRoot: root,
    evidencePath: join(root, "runtime_compatibility_check.json"),
    sdkModule: { Codex: GoodCodex },
    sidecarProtocolVersion: "4.19.codex.sdk_sidecar.v1",
  });

  assert.equal(result.ok, false);
  assert.equal(result.error_code, "CODEX_SDK_VERSION_MISMATCH");
});

test("runtime compatibility fails closed on missing API surface", async () => {
  const root = await fixtureRoot();

  const result = await runRuntimeCompatibilityCheck({
    packageRoot: root,
    evidencePath: join(root, "runtime_compatibility_check.json"),
    sdkModule: { Codex: class {} },
    sidecarProtocolVersion: "4.19.codex.sdk_sidecar.v1",
  });

  assert.equal(result.ok, false);
  assert.equal(result.error_code, "CODEX_SDK_API_SURFACE_MISSING");
});

test("runtime compatibility fails closed on lockfile transitive codex drift", async () => {
  const root = await fixtureRoot({ transitiveCodexVersion: "0.134.0" });

  const result = await runRuntimeCompatibilityCheck({
    packageRoot: root,
    evidencePath: join(root, "runtime_compatibility_check.json"),
    sdkModule: { Codex: GoodCodex },
    sidecarProtocolVersion: "4.19.codex.sdk_sidecar.v1",
  });

  assert.equal(result.ok, false);
  assert.equal(result.error_code, "CODEX_SDK_LOCKFILE_MISMATCH");
});

test("runtime compatibility fails closed on sidecar protocol drift", async () => {
  const root = await fixtureRoot();

  const result = await runRuntimeCompatibilityCheck({
    packageRoot: root,
    evidencePath: join(root, "runtime_compatibility_check.json"),
    sdkModule: { Codex: GoodCodex },
    sidecarProtocolVersion: "4.19.codex.sdk_sidecar.v0",
  });

  assert.equal(result.ok, false);
  assert.equal(result.error_code, "CODEX_SDK_RUNTIME_COMPATIBILITY_REVIEW_REQUIRED");
});

test("runtime compatibility fails closed when evidence cannot be written", async () => {
  const root = await fixtureRoot();
  const evidenceDirectory = join(root, "evidence-directory");
  await mkdir(evidenceDirectory);

  const result = await runRuntimeCompatibilityCheck({
    packageRoot: root,
    evidencePath: evidenceDirectory,
    sdkModule: { Codex: GoodCodex },
    sidecarProtocolVersion: "4.19.codex.sdk_sidecar.v1",
  });

  assert.equal(result.ok, false);
  assert.equal(result.error_code, "CODEX_SDK_RUNTIME_COMPATIBILITY_EVIDENCE_FAILED");
});

test("runtime compatibility requires reviewed codex path override for live transport", async () => {
  const root = await fixtureRoot();
  const evidencePath = join(root, "runtime_compatibility_check.json");

  const result = await runRuntimeCompatibilityCheck({
    packageRoot: root,
    evidencePath,
    sdkModule: { Codex: GoodCodex },
    sidecarProtocolVersion: "4.19.codex.sdk_sidecar.v1",
    requireCodexPathOverride: true,
  });

  assert.equal(result.ok, false);
  assert.equal(result.error_code, "CODEX_SDK_CODEX_PATH_OVERRIDE_REQUIRED");
  const evidence = JSON.parse(readFileSync(evidencePath, "utf8"));
  assert.equal(evidence.codex_app.require_codex_path_override, true);
  assert.equal(evidence.codex_app.codex_path_override, null);
});

test("runtime compatibility fails closed on unreviewed codex path override", async () => {
  const root = await fixtureRoot();
  const codexPath = await fakeCodex(root, "codex-cli 0.130.0-alpha.5");

  const result = await runRuntimeCompatibilityCheck({
    packageRoot: root,
    evidencePath: join(root, "runtime_compatibility_check.json"),
    sdkModule: { Codex: GoodCodex },
    sidecarProtocolVersion: "4.19.codex.sdk_sidecar.v1",
    requireCodexPathOverride: true,
    codexPathOverride: codexPath,
    reviewedCodexCliVersions: ["codex-cli 0.130.0-alpha.5"],
  });

  assert.equal(result.ok, false);
  assert.equal(result.error_code, "CODEX_APP_VERSION_MISMATCH");
});

test("runtime compatibility accepts reviewed codex path override and records diagnostics", async () => {
  const root = await fixtureRoot();
  const codexPath = await fakeCodex(root, "codex-cli 0.130.0-alpha.5");

  const result = await runRuntimeCompatibilityCheck({
    packageRoot: root,
    evidencePath: join(root, "runtime_compatibility_check.json"),
    sdkModule: { Codex: GoodCodex },
    sidecarProtocolVersion: "4.19.codex.sdk_sidecar.v1",
    requireCodexPathOverride: true,
    codexPathOverride: codexPath,
    reviewedCodexCliVersions: ["codex-cli 0.130.0-alpha.5"],
    reviewedCodexCliPaths: [codexPath],
  });

  assert.equal(result.ok, true);
  const evidence = JSON.parse(readFileSync(join(root, "runtime_compatibility_check.json"), "utf8"));
  assert.equal(evidence.codex_app.reviewed_path_allowed, true);
  assert.equal(evidence.codex_app.reviewed_version_allowed, true);
  assert.equal(evidence.codex_app.version, "codex-cli 0.130.0-alpha.5");
  assert.match(evidence.codex_app.sha256, /^[a-f0-9]{64}$/);
  assert.equal(evidence.codex_app.command_runner.exists, true);
  assert.equal(evidence.codex_app.sandbox_setup.exists, true);
});

async function fixtureRoot(overrides = {}) {
  const root = mkdtempSync(join(tmpdir(), "nexus-sdk-compat-"));
  await cp(join(packageRoot, "package.json"), join(root, "package.json"));
  await cp(join(packageRoot, "package-lock.json"), join(root, "package-lock.json"));
  if (overrides.packageDependency) {
    const packageJson = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
    packageJson.dependencies["@openai/codex-sdk"] = overrides.packageDependency;
    await writeFile(join(root, "package.json"), JSON.stringify(packageJson, null, 2));
  }
  if (overrides.transitiveCodexVersion) {
    const packageLock = JSON.parse(readFileSync(join(root, "package-lock.json"), "utf8"));
    packageLock.packages["node_modules/@openai/codex"].version = overrides.transitiveCodexVersion;
    await writeFile(join(root, "package-lock.json"), JSON.stringify(packageLock, null, 2));
  }
  await mkdir(join(root, "evidence"), { recursive: true });
  return root;
}

async function fakeCodex(root, version) {
  const codexPath = join(root, process.platform === "win32" ? "codex.cmd" : "codex");
  const commandRunner = join(root, "codex-command-runner.exe");
  const sandboxSetup = join(root, "codex-windows-sandbox-setup.exe");
  if (process.platform === "win32") {
    await writeFile(codexPath, `@echo off\r\necho ${version}\r\n`);
  } else {
    await writeFile(codexPath, `#!/bin/sh\necho '${version}'\n`);
    await chmod(codexPath, 0o755);
  }
  await writeFile(commandRunner, "fake command runner");
  await writeFile(sandboxSetup, "fake sandbox setup");
  return codexPath;
}
