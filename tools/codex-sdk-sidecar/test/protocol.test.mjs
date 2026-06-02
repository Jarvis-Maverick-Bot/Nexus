import test from "node:test";
import assert from "node:assert/strict";

import { buildSdkPrompt, validateBridgeRequest, mapSdkEventsToResult } from "../src/protocol.mjs";

test("validateBridgeRequest accepts bounded non-business request", () => {
  const request = {
    schema_version: "4.19.codex.sdk_bridge_request.v1",
    run_id: "run-sdk-001",
    assignment_id: "assign-sdk-001",
    task_id: "task-sdk-001",
    runtime_instance_id: "codex-sdk-runtime-001",
    workspace_ref: "workspace://nexus",
    repo_ref: "repo://nexus",
    allowed_write_surfaces: ["nexus/mq/codex_*.py"],
    allowed_tools: ["git", "pytest"],
    required_commands: ["python -m pytest nexus/mq/tests/test_codex_sdk_runner.py -q"],
    evidence_requirements: ["fake sdk test"],
    no_go_scope: ["no live SDK call"],
    not_business_completion: true,
  };

  assert.deepEqual(validateBridgeRequest(request), []);
  assert.match(buildSdkPrompt(request), /run-sdk-001/);
  assert.match(buildSdkPrompt(request), /not a Business Command/);
});

test("buildSdkPrompt constrains minimal non-business probe contract", () => {
  const prompt = buildSdkPrompt({
    run_id: "run-minimal-001",
    assignment_id: "assign-minimal-001",
    prompt_contract: "minimal_non_business_probe",
  });

  assert.match(prompt, /Do not use tools/);
  assert.match(prompt, /Do not read files/);
  assert.match(prompt, /Do not launch a nested sidecar/);
  assert.match(prompt, /Return exactly one JSON object and no prose/);
  assert.match(prompt, /"sdk_transport_probe":"minimal"/);
  assert.doesNotMatch(prompt, /Required commands:/);
  assert.doesNotMatch(prompt, /Evidence requirements:/);
});

test("validateBridgeRequest rejects business completion and secret-like values", () => {
  const errors = validateBridgeRequest({
    schema_version: "4.19.codex.sdk_bridge_request.v1",
    run_id: "run-sdk-001",
    assignment_id: "assign-sdk-001",
    task_id: "task-sdk-001",
    runtime_instance_id: "codex-sdk-runtime-001",
    workspace_ref: "workspace://nexus",
    repo_ref: "repo://nexus",
    allowed_write_surfaces: ["nexus/mq/codex_*.py"],
    allowed_tools: ["git", "pytest"],
    required_commands: ["echo " + "token" + "=" + "abc123"],
    evidence_requirements: ["fake sdk test"],
    no_go_scope: ["no live SDK call"],
    not_business_completion: false,
  });

  assert.ok(errors.includes("CODEX_SDK_REQUEST_CANNOT_BE_BUSINESS_COMPLETION"));
  assert.ok(errors.some((error) => error.startsWith("SECRET_MATERIAL_VALUE")));
});

test("mapSdkEventsToResult emits bounded result event", () => {
  const result = mapSdkEventsToResult([
    { type: "thread.started", thread_id: "thread-001" },
    { type: "turn.completed", turn_id: "turn-001" },
  ]);

  assert.equal(result.type, "result");
  assert.equal(result.status, "completed_execution");
  assert.equal(result.thread_id, "thread-001");
  assert.equal(result.turn_id, "turn-001");
  assert.deepEqual(result.evidence_refs, ["sdk-sidecar://event/thread.started", "sdk-sidecar://event/turn.completed"]);
});
