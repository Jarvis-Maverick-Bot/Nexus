import { createHash } from "node:crypto";
import { execFile } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { promisify } from "node:util";

export const EXPECTED_SDK_VERSION = "0.135.0";
export const EXPECTED_TRANSITIVE_CODEX_VERSION = "0.135.0";
export const EXPECTED_SDK_INTEGRITY =
  "sha512-4FziwR9RmYexAkAUqnWBQRUcFGWpBeBwDJpJKlabnuUXxaKQtBtKMTEYBA27ymn8W6mxxDMmwZC+inw7foFFaA==";
export const SIDECAR_PROTOCOL_VERSION = "4.19.codex.sdk_sidecar.v1";
const execFileAsync = promisify(execFile);

export async function runRuntimeCompatibilityCheck({
  packageRoot,
  evidencePath,
  sdkModule,
  sidecarProtocolVersion,
  codexPathOverride = null,
  reviewedCodexCliVersions = [],
  reviewedCodexCliPaths = [],
  requireCodexPathOverride = false,
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
    const codexApp = await inspectCodexApp({
      codexPathOverride,
      reviewedCodexCliVersions,
      reviewedCodexCliPaths,
      requireCodexPathOverride,
    });
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
      reviewedCodexCliPaths,
      requireCodexPathOverride,
      codexApp,
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
  reviewedCodexCliPaths,
  requireCodexPathOverride,
  codexApp,
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
    codex_app: codexApp,
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
  if (evidence.codex_app.require_codex_path_override && !evidence.codex_app.codex_path_override) {
    return "CODEX_SDK_CODEX_PATH_OVERRIDE_REQUIRED";
  }
  if (evidence.codex_app.codex_path_override && !evidence.codex_app.reviewed_path_allowed) {
    return "CODEX_APP_VERSION_MISMATCH";
  }
  if (evidence.codex_app.codex_path_override && !evidence.codex_app.reviewed_version_allowed) {
    return "CODEX_APP_VERSION_MISMATCH";
  }
  if (evidence.codex_app.codex_path_override && !evidence.codex_app.sha256) {
    return "CODEX_SDK_RUNTIME_COMPATIBILITY_REVIEW_REQUIRED";
  }
  return null;
}

async function inspectCodexApp({
  codexPathOverride,
  reviewedCodexCliVersions,
  reviewedCodexCliPaths,
  requireCodexPathOverride,
}) {
  const normalizedPath = codexPathOverride || null;
  const evidence = {
    codex_path_override: normalizedPath,
    require_codex_path_override: requireCodexPathOverride,
    reviewed_versions: reviewedCodexCliVersions,
    reviewed_paths: reviewedCodexCliPaths,
    reviewed_path_allowed: !normalizedPath ? false : reviewedCodexCliPaths.includes(normalizedPath),
    version: null,
    reviewed_version_allowed: false,
    sha256: null,
    command_runner: {
      path: null,
      exists: false,
      sha256: null,
    },
    sandbox_setup: {
      path: null,
      exists: false,
      sha256: null,
    },
  };
  if (!normalizedPath) {
    return evidence;
  }
  try {
    const bytes = await readFile(normalizedPath);
    evidence.sha256 = sha256Hex(bytes);
  } catch {
    return evidence;
  }
  try {
    const { stdout } = await runVersionProbe(normalizedPath);
    evidence.version = stdout.trim();
    evidence.reviewed_version_allowed = reviewedCodexCliVersions.includes(evidence.version);
  } catch {
    evidence.version = null;
  }
  const siblingDiagnostics = await inspectSiblingDiagnostics(normalizedPath);
  evidence.command_runner = siblingDiagnostics.commandRunner;
  evidence.sandbox_setup = siblingDiagnostics.sandboxSetup;
  return evidence;
}

async function runVersionProbe(executablePath) {
  if (process.platform === "win32" && /\.(cmd|bat)$/i.test(executablePath)) {
    return execFileAsync(process.env.ComSpec || "cmd.exe", ["/c", executablePath, "--version"], { timeout: 10000 });
  }
  return execFileAsync(executablePath, ["--version"], { timeout: 10000 });
}

async function inspectSiblingDiagnostics(codexPathOverride) {
  const appDataCommandRunner = join(dirname(codexPathOverride), "codex-command-runner.exe");
  const appDataSandboxSetup = join(dirname(codexPathOverride), "codex-windows-sandbox-setup.exe");
  const vendorCommandRunner = join(dirname(codexPathOverride), "..", "codex-resources", "codex-command-runner.exe");
  const vendorSandboxSetup = join(dirname(codexPathOverride), "..", "codex-resources", "codex-windows-sandbox-setup.exe");
  return {
    commandRunner: await firstExistingDiagnostic([appDataCommandRunner, vendorCommandRunner]),
    sandboxSetup: await firstExistingDiagnostic([appDataSandboxSetup, vendorSandboxSetup]),
  };
}

async function firstExistingDiagnostic(paths) {
  for (const path of paths) {
    try {
      const bytes = await readFile(path);
      return {
        path,
        exists: true,
        sha256: sha256Hex(bytes),
      };
    } catch {
      // keep looking
    }
  }
  return {
    path: paths[0] || null,
    exists: false,
    sha256: null,
  };
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
