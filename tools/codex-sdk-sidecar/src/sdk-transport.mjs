import { mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { runRuntimeCompatibilityCheck } from "./compatibility.mjs";
import { deepRedact, normalizeSdkEvent, resultFromNormalizedEvents } from "./event-normalizer.mjs";
import { buildSdkPrompt } from "./protocol.mjs";

export async function runCodexSdkTransport({
  request,
  sdkModule,
  loadSdkModule = () => import("@openai/codex-sdk"),
  emit = () => {},
  packageRoot = fileURLToPath(new URL("../", import.meta.url)),
}) {
  if (request.live_sdk_authorized !== true) {
    const result = blockedResult("CODEX_SDK_LIVE_CALL_NOT_AUTHORIZED");
    emit(result);
    return result;
  }

  const evidenceRoot = request.evidence_root || join(tmpdir(), `nexus-codex-sdk-sidecar-${Date.now()}`);
  await mkdir(evidenceRoot, { recursive: true });
  let moduleToUse;
  try {
    moduleToUse = sdkModule || (await loadSdkModule());
  } catch (error) {
    const result = blockedResult("CODEX_SDK_MODULE_UNAVAILABLE", {
      error_message: String(error?.message || error),
    });
    await persistEnvelope(evidenceRoot, { request, result, compatibility: { ok: false }, events: [] });
    emit(result);
    return result;
  }
  const compatibility = await runRuntimeCompatibilityCheck({
    packageRoot,
    evidencePath: join(evidenceRoot, "runtime_compatibility_check.json"),
    sdkModule: moduleToUse,
    sidecarProtocolVersion: request.sidecar_protocol_version,
    codexPathOverride: request.codex_path_override,
    reviewedCodexCliVersions: request.reviewed_codex_cli_versions || [],
    reviewedCodexCliPaths: request.reviewed_codex_cli_paths || [],
    requireCodexPathOverride: request.live_sdk_authorized === true,
    sourceCommitHead: request.source_commit_head || request.source_identity?.source_commit_head || null,
    boundedSourceIdentity:
      request.bounded_source_identity ||
      request.source_identity?.bounded_source_identity ||
      "bounded-untracked-sdk-bridge-source-state",
    sidecarSourceRef: request.sidecar_source_ref || "tools/codex-sdk-sidecar",
    eventMappingContractVersion: request.event_mapping_contract_version || request.sidecar_protocol_version,
  });
  if (!compatibility.ok) {
    const result = blockedResult(compatibility.error_code, { compatibility });
    await persistEnvelope(evidenceRoot, { request, result, compatibility, events: [] });
    emit(result);
    return result;
  }

  const normalizedEvents = [];
  const rawEvents = [];
  const startedAt = new Date().toISOString();
  const controller = new AbortController();
  let timeoutFired = false;
  let timer = null;
  if (Number.isFinite(request.timeout_ms) && request.timeout_ms > 0) {
    timer = setTimeout(() => {
      timeoutFired = true;
      controller.abort();
    }, request.timeout_ms);
  }

  try {
    const codex = new moduleToUse.Codex({
      codexPathOverride: request.codex_path_override,
      env: request.sdk_env || {},
      config: request.sdk_config || {},
    });
    const thread = request.thread_id
      ? codex.resumeThread(request.thread_id, threadOptions(request))
      : codex.startThread(threadOptions(request));
    const prompt = buildSdkPrompt(request);
    const stream = await thread.runStreamed(prompt, {
      signal: controller.signal,
      outputSchema: request.output_schema,
    });
    if (timeoutFired) {
      const result = blockedResult("CODEX_SDK_TURN_TIMEOUT", {
        started_at: startedAt,
        timeout_at: new Date().toISOString(),
        compatibility,
      });
      await persistTransportEvidence(evidenceRoot, request, result, compatibility, rawEvents, normalizedEvents);
      emit(result);
      return result;
    }
    for await (const event of stream.events) {
      rawEvents.push(deepRedact(event));
      const normalized = normalizeSdkEvent(event);
      normalizedEvents.push(normalized);
      emit(normalized);
    }
    const result = resultFromNormalizedEvents(normalizedEvents);
    result.compatibility = { ok: compatibility.ok, evidence_path: compatibility.evidence_path };
    await persistTransportEvidence(evidenceRoot, request, result, compatibility, rawEvents, normalizedEvents);
    emit(result);
    return result;
  } catch (error) {
    if (hasCompletedTurn(normalizedEvents) && isPostTurnProcessTerminationDiagnostic(error)) {
      const result = resultFromNormalizedEvents(normalizedEvents);
      result.compatibility = { ok: compatibility.ok, evidence_path: compatibility.evidence_path };
      result.post_turn_diagnostic = {
        status: "observed_after_turn_completed",
        message: String(error?.message || error),
      };
      await persistTransportEvidence(evidenceRoot, request, result, compatibility, rawEvents, normalizedEvents);
      emit(result);
      return result;
    }
    const errorCode = timeoutFired || error?.name === "AbortError" ? "CODEX_SDK_TURN_TIMEOUT" : "CODEX_SDK_TRANSPORT_ERROR";
    const result = blockedResult(errorCode, {
      started_at: startedAt,
      timeout_at: timeoutFired ? new Date().toISOString() : null,
      error_message: String(error?.message || error),
      compatibility,
    });
    await persistTransportEvidence(evidenceRoot, request, result, compatibility, rawEvents, normalizedEvents);
    emit(result);
    return result;
  } finally {
    if (timer) {
      clearTimeout(timer);
    }
  }
}

function hasCompletedTurn(events) {
  return events.some((event) => event?.type === "turn.completed");
}

function isPostTurnProcessTerminationDiagnostic(error) {
  const message = String(error?.message || error || "");
  return /Failed to parse item:/i.test(message) && /SUCCESS:/i.test(message) && /process with PID/i.test(message) && /terminated/i.test(message);
}

function threadOptions(request) {
  return {
    workingDirectory: request.bounded_workdir,
    skipGitRepoCheck: request.skip_git_repo_check === true,
    sandboxMode: request.sandbox_mode || "read-only",
    approvalPolicy: request.approval_policy || "never",
    networkAccessEnabled: request.network_access_enabled === true,
    webSearchMode: request.web_search_mode || "disabled",
    webSearchEnabled: request.web_search_enabled === true,
    model: request.model,
    modelReasoningEffort: request.model_reasoning_effort,
    additionalDirectories: request.additional_directories || [],
  };
}

function blockedResult(errorCode, extras = {}) {
  return {
    type: "result",
    status: "blocked",
    error_code: errorCode,
    thread_id: null,
    turn_id: null,
    evidence_refs: [
      "sdk-sidecar://runtime-compatibility-check",
      "sdk-sidecar://sdk-transport-envelope",
    ],
    ...extras,
  };
}

async function persistTransportEvidence(evidenceRoot, request, result, compatibility, rawEvents, normalizedEvents) {
  await writeJsonl(join(evidenceRoot, "raw_sdk_events.jsonl"), rawEvents);
  await writeJsonl(join(evidenceRoot, "normalized_sdk_events.jsonl"), normalizedEvents);
  await persistEnvelope(evidenceRoot, { request, result, compatibility, events: normalizedEvents });
}

async function persistEnvelope(evidenceRoot, { request, result, compatibility, events }) {
  const envelope = {
    run_id: request.run_id,
    assignment_id: request.assignment_id,
    task_id: request.task_id,
    runtime_instance_id: request.runtime_instance_id,
    status: result.status,
    error_code: result.error_code || null,
    sdk_transport_status: result.sdk_transport_status || result.status,
    inner_codex_command_runner_status: result.inner_codex_command_runner_status || "not_classified",
    nexus_command_execution_status: result.nexus_command_execution_status || "not_classified",
    final_result_candidate_status: result.final_result_candidate_status || result.status,
    thread_id: result.thread_id || null,
    turn_id: result.turn_id || null,
    compatibility: {
      ok: compatibility.ok,
      error_code: compatibility.error_code || null,
      evidence_path: compatibility.evidence_path || null,
    },
    event_count: events.length,
    written_at: new Date().toISOString(),
  };
  await writeJson(join(evidenceRoot, "sdk_transport_envelope.json"), envelope);
}

async function writeJson(filePath, value) {
  await mkdir(dirname(filePath), { recursive: true });
  await writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`);
}

async function writeJsonl(filePath, values) {
  await mkdir(dirname(filePath), { recursive: true });
  await writeFile(filePath, values.map((value) => JSON.stringify(value)).join("\n") + (values.length ? "\n" : ""));
}
