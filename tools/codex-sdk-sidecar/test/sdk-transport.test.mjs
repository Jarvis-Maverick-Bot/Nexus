import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { runCodexSdkTransport } from "../src/sdk-transport.mjs";

const REVIEWED_CODEX_VERSION = "codex-cli 0.130.0-alpha.5";
const REVIEWED_CODEX_PATH = fakeReviewedCodexPath();

test("transport uses startThread and normalizes streamed SDK events", async () => {
  const emitted = [];
  const evidenceRoot = mkdtempSync(join(tmpdir(), "nexus-sdk-transport-"));
  const sdkModule = fakeSdkModule([
    { type: "thread.started", thread_id: "thread-001" },
    { type: "turn.started" },
    { type: "item.completed", item: { type: "agent_message", text: "hello" } },
    { type: "turn.completed", usage: { input_tokens: 1, cached_input_tokens: 0, output_tokens: 1, reasoning_output_tokens: 0 } },
  ]);

  const result = await runCodexSdkTransport({
    request: request({ evidence_root: evidenceRoot }),
    sdkModule,
    emit: (event) => emitted.push(event),
  });

  assert.equal(result.status, "completed_execution");
  assert.equal(sdkModule.calls.startThread, 1);
  assert.equal(sdkModule.calls.resumeThread, 0);
  assert.deepEqual(emitted.map((event) => event.type), [
    "thread.started",
    "turn.started",
    "item.completed",
    "turn.completed",
    "result",
  ]);
  const rawEvents = readFileSync(join(evidenceRoot, "raw_sdk_events.jsonl"), "utf8");
  assert.match(rawEvents, /thread.started/);
  const envelope = JSON.parse(readFileSync(join(evidenceRoot, "sdk_transport_envelope.json"), "utf8"));
  assert.equal(envelope.thread_id, "thread-001");
  assert.equal(envelope.compatibility.ok, true);
});

test("transport resumes existing thread when request has thread_id", async () => {
  const sdkModule = fakeSdkModule([{ type: "turn.completed", usage: {} }]);

  await runCodexSdkTransport({
    request: request({ thread_id: "thread-existing" }),
    sdkModule,
    emit: () => {},
  });

  assert.equal(sdkModule.calls.startThread, 0);
  assert.equal(sdkModule.calls.resumeThread, 1);
  assert.equal(sdkModule.calls.resumeId, "thread-existing");
});

test("transport aborts on timeout and fails closed", async () => {
  let aborted = false;
  const sdkModule = {
    Codex: class {
      startThread() {
        return {
          async runStreamed(_prompt, options) {
            options.signal.addEventListener("abort", () => {
              aborted = true;
            });
            await new Promise((resolve) => setTimeout(resolve, 50));
            return { events: asyncGenerator([]) };
          },
        };
      }
      resumeThread() {
        return this.startThread();
      }
    },
  };

  const result = await runCodexSdkTransport({
    request: request({ timeout_ms: 1 }),
    sdkModule,
    emit: () => {},
  });

  assert.equal(aborted, true);
  assert.equal(result.status, "blocked");
  assert.equal(result.error_code, "CODEX_SDK_TURN_TIMEOUT");
});

test("transport redacts raw SDK event evidence", async () => {
  const evidenceRoot = mkdtempSync(join(tmpdir(), "nexus-sdk-redact-"));
  const syntheticSecretTail = "abcdefghijklmnopqrst";
  const sdkModule = fakeSdkModule([
    { type: "item.completed", item: { type: "agent_message", text: "sk-" + syntheticSecretTail } },
    { type: "turn.completed", usage: {} },
  ]);

  await runCodexSdkTransport({
    request: request({ evidence_root: evidenceRoot }),
    sdkModule,
    emit: () => {},
  });

  const rawEvents = readFileSync(join(evidenceRoot, "raw_sdk_events.jsonl"), "utf8");
  assert.doesNotMatch(rawEvents, new RegExp(syntheticSecretTail));
  assert.match(rawEvents, /REDACTED_OPENAI_KEY/);
});

test("transport maps inner command-runner sandbox failure to blocked result", async () => {
  const evidenceRoot = mkdtempSync(join(tmpdir(), "nexus-sdk-inner-command-failure-"));
  const sdkModule = fakeSdkModule([
    { type: "thread.started", thread_id: "thread-sandbox-failure" },
    {
      type: "item.completed",
      item: {
        type: "command_execution",
        status: "failed",
        exit_code: -1,
        aggregated_output: 'execution error: Io(Custom { kind: Other, error: "windows sandbox: spawn setup refresh" })',
      },
    },
    { type: "turn.completed", usage: {} },
  ]);

  const result = await runCodexSdkTransport({
    request: request({ evidence_root: evidenceRoot }),
    sdkModule,
    emit: () => {},
  });

  assert.equal(result.status, "blocked");
  assert.equal(result.error_code, "CODEX_SDK_INNER_COMMAND_RUNNER_FAILED");
  assert.equal(result.sdk_transport_status, "blocked");
  assert.equal(result.inner_codex_command_runner_status, "blocked");
  assert.equal(result.nexus_command_execution_status, "not_started");
  assert.equal(result.final_result_candidate_status, "blocked");
  assert.equal(result.thread_id, "thread-sandbox-failure");
  const envelope = JSON.parse(readFileSync(join(evidenceRoot, "sdk_transport_envelope.json"), "utf8"));
  assert.equal(envelope.status, "blocked");
  assert.equal(envelope.error_code, "CODEX_SDK_INNER_COMMAND_RUNNER_FAILED");
  assert.equal(envelope.sdk_transport_status, "blocked");
  assert.equal(envelope.inner_codex_command_runner_status, "blocked");
  assert.equal(envelope.nexus_command_execution_status, "not_started");
  assert.equal(envelope.final_result_candidate_status, "blocked");
});

test("transport preserves completed minimal turn when SDK throws post-turn diagnostic", async () => {
  const evidenceRoot = mkdtempSync(join(tmpdir(), "nexus-sdk-post-turn-diagnostic-"));
  const sdkModule = fakeSdkModuleWithPostTurnError([
    { type: "thread.started", thread_id: "thread-post-turn" },
    {
      type: "item.completed",
      item: {
        type: "agent_message",
        text: JSON.stringify({
          status: "completed_execution",
          not_business_completion: true,
          sdk_transport_probe: "minimal",
        }),
      },
    },
    { type: "turn.completed", usage: {} },
  ]);

  const result = await runCodexSdkTransport({
    request: request({ evidence_root: evidenceRoot, prompt_contract: "minimal_non_business_probe" }),
    sdkModule,
    emit: () => {},
  });

  assert.equal(result.status, "completed_execution");
  assert.equal(result.error_code, null);
  assert.equal(result.sdk_transport_status, "completed_execution");
  assert.equal(result.inner_codex_command_runner_status, "no_failure_observed");
  assert.equal(result.final_result_candidate_status, "completed_execution");
  const envelope = JSON.parse(readFileSync(join(evidenceRoot, "sdk_transport_envelope.json"), "utf8"));
  assert.equal(envelope.status, "completed_execution");
  assert.equal(envelope.error_code, null);
  assert.equal(envelope.event_count, 3);
});

test("transport sends minimal non-business probe prompt contract", async () => {
  const sdkModule = fakeSdkModule([{ type: "turn.completed", usage: {} }]);

  await runCodexSdkTransport({
    request: request({
      prompt_contract: "minimal_non_business_probe",
      required_commands: ["SDK bridge real transport minimal non-business probe"],
      evidence_requirements: ["runtime_compatibility_check.json before SDK transport starts"],
    }),
    sdkModule,
    emit: () => {},
  });

  assert.match(sdkModule.calls.prompt, /Do not use tools/);
  assert.match(sdkModule.calls.prompt, /Do not launch a nested sidecar/);
  assert.match(sdkModule.calls.prompt, /Return exactly one JSON object and no prose/);
  assert.doesNotMatch(sdkModule.calls.prompt, /Required commands:/);
  assert.doesNotMatch(sdkModule.calls.prompt, /Evidence requirements:/);
});

test("transport fails closed when SDK module cannot be loaded", async () => {
  const evidenceRoot = mkdtempSync(join(tmpdir(), "nexus-sdk-missing-"));
  const emitted = [];

  const result = await runCodexSdkTransport({
    request: request({ evidence_root: evidenceRoot }),
    loadSdkModule: async () => {
      throw new Error("synthetic module unavailable");
    },
    emit: (event) => emitted.push(event),
  });

  assert.equal(result.status, "blocked");
  assert.equal(result.error_code, "CODEX_SDK_MODULE_UNAVAILABLE");
  assert.equal(emitted.at(-1).error_code, "CODEX_SDK_MODULE_UNAVAILABLE");
  const envelope = JSON.parse(readFileSync(join(evidenceRoot, "sdk_transport_envelope.json"), "utf8"));
  assert.equal(envelope.error_code, "CODEX_SDK_MODULE_UNAVAILABLE");
});

function request(overrides = {}) {
  return {
    schema_version: "4.19.codex.sdk_bridge_request.v1",
    sidecar_protocol_version: "4.19.codex.sdk_sidecar.v1",
    run_id: "run-sdk-001",
    assignment_id: "assign-sdk-001",
    task_id: "task-sdk-001",
    runtime_instance_id: "codex-sdk-runtime-001",
    workspace_ref: "workspace://nexus",
    repo_ref: "repo://nexus",
    bounded_workdir: "D:/Projects/Nexus",
    allowed_write_surfaces: ["nexus/mq/codex_*.py"],
    allowed_tools: ["git", "pytest"],
    required_commands: ["python -m pytest nexus/mq/tests/test_codex_sdk_runner.py -q"],
    evidence_requirements: ["fake sdk test"],
    no_go_scope: ["no live SDK call"],
    not_business_completion: true,
    live_sdk_authorized: true,
    codex_path_override: REVIEWED_CODEX_PATH,
    reviewed_codex_cli_paths: [REVIEWED_CODEX_PATH],
    reviewed_codex_cli_versions: [REVIEWED_CODEX_VERSION],
    ...overrides,
  };
}

function fakeReviewedCodexPath() {
  const root = mkdtempSync(join(tmpdir(), "nexus-sdk-reviewed-codex-"));
  const codexPath = join(root, process.platform === "win32" ? "codex.cmd" : "codex");
  if (process.platform === "win32") {
    writeFileSync(codexPath, `@echo off\r\necho ${REVIEWED_CODEX_VERSION}\r\n`);
  } else {
    writeFileSync(codexPath, `#!/bin/sh\necho '${REVIEWED_CODEX_VERSION}'\n`, { mode: 0o755 });
  }
  return codexPath;
}

function fakeSdkModule(events) {
  const calls = { startThread: 0, resumeThread: 0, resumeId: null, prompt: null };
  class Codex {
    startThread() {
      calls.startThread += 1;
      return thread(events, calls);
    }
    resumeThread(id) {
      calls.resumeThread += 1;
      calls.resumeId = id;
      return thread(events, calls);
    }
  }
  return { Codex, calls };
}

function fakeSdkModuleWithPostTurnError(events) {
  const calls = { startThread: 0, resumeThread: 0, resumeId: null, prompt: null };
  class Codex {
    startThread() {
      calls.startThread += 1;
      return threadWithPostTurnError(events, calls);
    }
    resumeThread(id) {
      calls.resumeThread += 1;
      calls.resumeId = id;
      return threadWithPostTurnError(events, calls);
    }
  }
  return { Codex, calls };
}

function thread(events, calls) {
  return {
    async runStreamed(prompt) {
      calls.prompt = prompt;
      return { events: asyncGenerator(events) };
    },
  };
}

function threadWithPostTurnError(events, calls) {
  return {
    async runStreamed(prompt) {
      calls.prompt = prompt;
      return { events: asyncGeneratorWithPostTurnError(events) };
    },
  };
}

async function* asyncGenerator(events) {
  for (const event of events) {
    yield event;
  }
}

async function* asyncGeneratorWithPostTurnError(events) {
  for (const event of events) {
    yield event;
  }
  throw new Error("Failed to parse item: SUCCESS: The process with PID 1234 has been terminated.");
}
