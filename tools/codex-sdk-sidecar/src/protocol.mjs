const REQUIRED_FIELDS = [
  "run_id",
  "assignment_id",
  "task_id",
  "runtime_instance_id",
  "workspace_ref",
  "repo_ref",
  "allowed_write_surfaces",
  "allowed_tools",
  "required_commands",
  "evidence_requirements",
  "no_go_scope",
];

const SECRET_PATTERNS = [
  /sk-[A-Za-z0-9]{20,}/,
  /(api[_-]?key|token|password|secret)\s*[=:]\s*\S+/i,
];

export function validateBridgeRequest(request) {
  const errors = [];
  if (!request || typeof request !== "object") {
    return ["CODEX_SDK_REQUEST_INVALID_JSON"];
  }
  if (request.schema_version !== "4.19.codex.sdk_bridge_request.v1") {
    errors.push("UNSUPPORTED_CODEX_SDK_BRIDGE_REQUEST_SCHEMA");
  }
  if (request.not_business_completion !== true) {
    errors.push("CODEX_SDK_REQUEST_CANNOT_BE_BUSINESS_COMPLETION");
  }
  for (const field of REQUIRED_FIELDS) {
    if (!hasValue(request[field])) {
      errors.push(`MISSING_CODEX_SDK_REQUEST_FIELD: ${field}`);
    }
  }
  collectSecretErrors(request, "codex_sdk_bridge_request", errors);
  return dedupe(errors);
}

export function buildSdkPrompt(request) {
  if (request.prompt_contract === "minimal_non_business_probe") {
    return buildMinimalNonBusinessProbePrompt(request);
  }
  return [
    `Run ID: ${request.run_id}`,
    `Assignment ID: ${request.assignment_id}`,
    `Task ID: ${request.task_id}`,
    "This is a bounded non-business Codex SDK assignment.",
    "This is not a Business Command and must not be reported as Business Command acceptance.",
    `Allowed write surfaces: ${(request.allowed_write_surfaces || []).join(", ")}`,
    `Required commands: ${(request.required_commands || []).join("; ")}`,
    `Evidence requirements: ${(request.evidence_requirements || []).join("; ")}`,
    `No-go scope: ${(request.no_go_scope || []).join("; ")}`,
  ].join("\n");
}

function buildMinimalNonBusinessProbePrompt(request) {
  return [
    "Nexus SDK bridge minimal non-business probe.",
    "",
    "Hard bounds:",
    "- Do not use tools.",
    "- Do not run shell commands.",
    "- Do not read files, including skill files or repository files.",
    "- Do not inspect the repository.",
    "- Do not launch a nested sidecar, harness, CLI, MCP server, or Codex process.",
    "- Do not write files.",
    "- Do not perform Business Command, production, or private-agent work.",
    "- Do not claim PASS, runtime promotion, or live-readiness.",
    "",
    "Return exactly one JSON object and no prose.",
    "The JSON object must contain:",
    "- run_id",
    "- assignment_id",
    "- status",
    "- not_business_completion",
    "- sdk_transport_probe",
    "- message",
    "",
    `Use run_id: ${request.run_id}`,
    `Use assignment_id: ${request.assignment_id}`,
    "",
    "Expected JSON:",
    JSON.stringify({
      run_id: request.run_id,
      assignment_id: request.assignment_id,
      status: "completed_execution",
      not_business_completion: true,
      sdk_transport_probe: "minimal",
      message: "SDK bridge minimal non-business probe response generated without tool use.",
    }),
  ].join("\n");
}

export function mapSdkEventsToResult(events) {
  const thread = events.find((event) => typeof event.thread_id === "string");
  const turn = events.find((event) => typeof event.turn_id === "string");
  return {
    type: "result",
    status: "completed_execution",
    thread_id: thread?.thread_id ?? null,
    turn_id: turn?.turn_id ?? null,
    evidence_refs: events.map((event) => `sdk-sidecar://event/${event.type || "unknown"}`),
  };
}

export function redacted(value) {
  let text = String(value);
  for (const pattern of SECRET_PATTERNS) {
    text = text.replace(pattern, (match, name) => (name ? `${name}=[REDACTED]` : "[REDACTED_OPENAI_KEY]"));
  }
  return text;
}

function hasValue(value) {
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  return value !== undefined && value !== null && value !== "";
}

function collectSecretErrors(value, path, errors) {
  if (typeof value === "string") {
    if (SECRET_PATTERNS.some((pattern) => pattern.test(value))) {
      errors.push(`SECRET_MATERIAL_VALUE: ${path}`);
    }
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => collectSecretErrors(item, `${path}[${index}]`, errors));
    return;
  }
  if (value && typeof value === "object") {
    for (const [key, nested] of Object.entries(value)) {
      collectSecretErrors(nested, `${path}.${key}`, errors);
    }
  }
}

function dedupe(values) {
  return values.filter((value, index) => value && values.indexOf(value) === index);
}
