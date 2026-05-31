import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { cp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { runRuntimeCompatibilityCheck } from "../src/compatibility.mjs";

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

async function fixtureRoot(overrides = {}) {
  const root = mkdtempSync(join(tmpdir(), "nexus-sdk-compat-"));
  await cp("tools/codex-sdk-sidecar/package.json", join(root, "package.json"));
  await cp("tools/codex-sdk-sidecar/package-lock.json", join(root, "package-lock.json"));
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
