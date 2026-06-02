import { redacted } from "./protocol.mjs";

export function normalizeSdkEvent(event) {
  const normalized = deepRedact(event && typeof event === "object" ? event : { value: event });
  if (!normalized.type) {
    normalized.type = "sdk.event";
  }
  return normalized;
}

export function resultFromNormalizedEvents(events, overrides = {}) {
  const threadId = firstString(events, "thread_id") || overrides.thread_id || null;
  const turnId = firstString(events, "turn_id") || overrides.turn_id || null;
  const usage = lastObject(events, "usage") || null;
  const innerFailure = firstInnerCommandRunnerFailure(events);
  const status = overrides.status || innerFailure?.status || "completed_execution";
  const errorCode = overrides.error_code || innerFailure?.error_code || null;
  return {
    type: "result",
    status,
    error_code: errorCode,
    sdk_transport_status: status,
    inner_codex_command_runner_status: innerFailure?.inner_codex_command_runner_status || "no_failure_observed",
    nexus_command_execution_status: innerFailure?.nexus_command_execution_status || "not_classified",
    final_result_candidate_status: status,
    thread_id: threadId,
    turn_id: turnId,
    usage,
    evidence_refs: [
      "sdk-sidecar://raw-sdk-events",
      "sdk-sidecar://normalized-sdk-events",
      "sdk-sidecar://runtime-compatibility-check",
    ],
  };
}

export function deepRedact(value) {
  if (typeof value === "string") {
    return redacted(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => deepRedact(item));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, nested]) => [key, deepRedact(nested)]));
  }
  return value;
}

function firstString(events, key) {
  for (const event of events) {
    const value = event?.[key];
    if (typeof value === "string" && value) {
      return value;
    }
  }
  return null;
}

function lastObject(events, key) {
  for (const event of [...events].reverse()) {
    const value = event?.[key];
    if (value && typeof value === "object" && !Array.isArray(value)) {
      return value;
    }
  }
  return null;
}

function firstInnerCommandRunnerFailure(events) {
  for (const event of events) {
    const item = event?.item;
    if (!item || item.type !== "command_execution" || item.status !== "failed") {
      continue;
    }
    const text = [
      item.aggregated_output,
      item.error,
      item.stderr,
      item.stdout,
      item.command,
    ]
      .filter((value) => typeof value === "string")
      .join("\n");
    if (/windows sandbox/i.test(text) && /spawn setup refresh/i.test(text)) {
      return {
        status: "blocked",
        error_code: "CODEX_SDK_INNER_COMMAND_RUNNER_FAILED",
        inner_codex_command_runner_status: "blocked",
        nexus_command_execution_status: "not_started",
      };
    }
  }
  return null;
}
