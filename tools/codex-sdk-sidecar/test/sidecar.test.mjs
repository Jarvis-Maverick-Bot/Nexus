import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const sidecar = resolve(here, "../src/index.mjs");

test("sidecar fake mode emits thread turn and result events", () => {
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

  const completed = spawnSync(process.execPath, [sidecar, "--stdio"], {
    input: JSON.stringify(request),
    encoding: "utf8",
    env: { ...process.env, NEXUS_CODEX_SDK_FAKE_MODE: "1" },
  });

  assert.equal(completed.status, 0);
  const events = completed.stdout.trim().split(/\r?\n/).map((line) => JSON.parse(line));
  assert.deepEqual(events.map((event) => event.type), ["thread.started", "turn.completed", "result"]);
  assert.equal(events[2].status, "completed_execution");
});

test("sidecar rejects live mode without authorization", () => {
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

  const completed = spawnSync(process.execPath, [sidecar, "--stdio"], {
    input: JSON.stringify(request),
    encoding: "utf8",
  });

  assert.equal(completed.status, 3);
  const event = JSON.parse(completed.stdout.trim());
  assert.equal(event.error_code, "CODEX_SDK_LIVE_CALL_NOT_AUTHORIZED");
});
