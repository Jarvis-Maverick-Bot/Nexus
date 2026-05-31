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
  return {
    type: "result",
    status: overrides.status || "completed_execution",
    error_code: overrides.error_code || null,
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
