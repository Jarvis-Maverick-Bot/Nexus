import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

export const EXPECTED_SDK_VERSION = "0.135.0";
export const EXPECTED_TRANSITIVE_CODEX_VERSION = "0.135.0";
export const EXPECTED_SDK_INTEGRITY =
  "sha512-4FziwR9RmYexAkAUqnWBQRUcFGWpBeBwDJpJKlabnuUXxaKQtBtKMTEYBA27ymn8W6mxxDMmwZC+inw7foFFaA==";
export const SIDECAR_PROTOCOL_VERSION = "4.19.codex.sdk_sidecar.v1";

export async function runRuntimeCompatibilityCheck({
  packageRoot,
  evidencePath,
  sdkModule,
  sidecarProtocolVersion,
  codexPathOverride = null,
  reviewedCodexCliVersions = [],
  sourceCommitHead = null,
  boundedSourceIdentity = "bounded-untracked-sdk-bridge-source-state",
  sidecarSourceRef = "tools/codex-sdk-sidecar",
  eventMappingContractVersion = SIDECAR_PROTOCOL_VERSION,
}) {
  const startedAt = new Date().toISOString();
  let packageJson = null;
  let packageLock = null;
  let evidence;
  try {
    const packageJsonBytes = await readFile(`${packageRoot}/package.json`);
    const packageLockBytes = await readFile(`${packageRoot}/package-lock.json`);
    packageJson = JSON.parse(packageJsonBytes.toString("utf8"));
    packageLock = JSON.parse(packageLockBytes.toString("utf8"));
    evidence = buildEvidence({
      startedAt,
      packageJson,
      packageLock,
      packageJsonSha256: sha256Hex(packageJsonBytes),
      packageLockSha256: sha256Hex(packageLockBytes),
      sdkModule,
      sidecarProtocolVersion,
      codexPathOverride,
      reviewedCodexCliVersions,
      sourceCommitHead,
      boundedSourceIdentity,
      sidecarSourceRef,
      eventMappingContractVersion,
    });
  } catch (error) {
    evidence = {
      ok: false,
      error_code: "CODEX_SDK_LOCKFILE_MISMATCH",
      compatibility_result: "blocked",
      errors: [{ code: "CODEX_SDK_LOCKFILE_MISMATCH", message: String(error?.message || error) }],
      started_at: startedAt,
      checked_at: new Date().toISOString(),
      error: String(error?.message || error),
      source_identity: {
        source_commit_head: sourceCommitHead,
        bounded_source_identity: boundedSourceIdentity,
      },
      sidecar_source_ref: sidecarSourceRef,
    };
  }

  const writeResult = await writeEvidence(evidencePath, evidence);
  if (!writeResult.ok) {
    return {
      ok: false,
      error_code: "CODEX_SDK_RUNTIME_COMPATIBILITY_EVIDENCE_FAILED",
      evidence_path: evidencePath,
      write_error: writeResult.error,
    };
  }
  return { ...evidence, evidence_path: evidencePath };
}

function buildEvidence({
  startedAt,
  packageJson,
  packageLock,
  packageJsonSha256,
  packageLockSha256,
  sdkModule,
  sidecarProtocolVersion,
  codexPathOverride,
  reviewedCodexCliVersions,
  sourceCommitHead,
  boundedSourceIdentity,
  sidecarSourceRef,
  eventMappingContractVersion,
}) {
  const rootPackage = packageLock.packages?.[""] || {};
  const lockedSdk = packageLock.packages?.["node_modules/@openai/codex-sdk"] || {};
  const lockedCodex = packageLock.packages?.["node_modules/@openai/codex"] || {};
  const declaredSdkVersion = packageJson.dependencies?.["@openai/codex-sdk"] || null;
  const rootLockedSdkVersion = rootPackage.dependencies?.["@openai/codex-sdk"] || null;
  const apiSurface = inspectApiSurface(sdkModule);
  const evidence = {
    ok: true,
    error_code: null,
    started_at: startedAt,
    checked_at: new Date().toISOString(),
    package_json: {
      name: packageJson.name,
      version: packageJson.version,
      declared_sdk_version: declaredSdkVersion,
      sha256: packageJsonSha256,
    },
    package_lock: {
      lockfile_version: packageLock.lockfileVersion,
      root_declared_sdk_version: rootLockedSdkVersion,
      sdk_integrity: lockedSdk.integrity || null,
      sha256: packageLockSha256,
    },
    sdk: {
      expected_version: EXPECTED_SDK_VERSION,
      version: lockedSdk.version || null,
      transitive_codex_version: lockedCodex.version || null,
      effective_loaded_version: lockedSdk.version || null,
      effective_transitive_codex_version: lockedCodex.version || null,
    },
    source_identity: {
      source_commit_head: sourceCommitHead,
      bounded_source_identity: boundedSourceIdentity,
    },
    sidecar_source_ref: sidecarSourceRef,
    api_surface: apiSurface,
    sidecar_protocol: {
      expected: SIDECAR_PROTOCOL_VERSION,
      provided: sidecarProtocolVersion || null,
      event_mapping_contract_version: eventMappingContractVersion,
    },
    codex_app: {
      codex_path_override: codexPathOverride || null,
      reviewed_versions: reviewedCodexCliVersions,
    },
    compatibility_result: "compatible",
    errors: [],
  };

  const errorCode = firstCompatibilityError(evidence);
  if (errorCode) {
    evidence.ok = false;
    evidence.error_code = errorCode;
    evidence.compatibility_result = errorCode === "CODEX_SDK_RUNTIME_COMPATIBILITY_REVIEW_REQUIRED" ? "review_required" : "blocked";
    evidence.errors = [{ code: errorCode }];
  }
  return evidence;
}

function inspectApiSurface(sdkModule) {
  const Codex = sdkModule?.Codex;
  return {
    Codex: typeof Codex === "function",
    startThread: typeof Codex?.prototype?.startThread === "function",
    resumeThread: typeof Codex?.prototype?.resumeThread === "function",
  };
}

function firstCompatibilityError(evidence) {
  if (evidence.package_json.declared_sdk_version !== EXPECTED_SDK_VERSION) {
    return "CODEX_SDK_VERSION_MISMATCH";
  }
  if (evidence.package_lock.root_declared_sdk_version !== EXPECTED_SDK_VERSION) {
    return "CODEX_SDK_LOCKFILE_MISMATCH";
  }
  if (evidence.sdk.version !== EXPECTED_SDK_VERSION) {
    return "CODEX_SDK_LOCKFILE_MISMATCH";
  }
  if (evidence.sdk.transitive_codex_version !== EXPECTED_TRANSITIVE_CODEX_VERSION) {
    return "CODEX_SDK_LOCKFILE_MISMATCH";
  }
  if (evidence.package_lock.sdk_integrity !== EXPECTED_SDK_INTEGRITY) {
    return "CODEX_SDK_LOCKFILE_MISMATCH";
  }
  if (!evidence.api_surface.Codex || !evidence.api_surface.startThread || !evidence.api_surface.resumeThread) {
    return "CODEX_SDK_API_SURFACE_MISSING";
  }
  if (evidence.sidecar_protocol.provided !== SIDECAR_PROTOCOL_VERSION) {
    return "CODEX_SDK_RUNTIME_COMPATIBILITY_REVIEW_REQUIRED";
  }
  if (evidence.codex_app.codex_path_override && evidence.codex_app.reviewed_versions.length === 0) {
    return "CODEX_APP_VERSION_MISMATCH";
  }
  return null;
}

async function writeEvidence(evidencePath, evidence) {
  try {
    await mkdir(dirname(evidencePath), { recursive: true });
    await writeFile(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`);
    return { ok: true };
  } catch (error) {
    return { ok: false, error: String(error?.message || error) };
  }
}

function sha256Hex(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}
