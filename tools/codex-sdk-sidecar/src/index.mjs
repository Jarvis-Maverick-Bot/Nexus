#!/usr/bin/env node
import process from "node:process";

import { buildSdkPrompt, mapSdkEventsToResult, validateBridgeRequest } from "./protocol.mjs";
import { runCodexSdkTransport } from "./sdk-transport.mjs";

async function main() {
  const input = await readStdin();
  let request;
  try {
    request = JSON.parse(input || "{}");
  } catch {
    emit({ type: "error", error_code: "CODEX_SDK_REQUEST_INVALID_JSON" });
    process.exitCode = 2;
    return;
  }
  const errors = validateBridgeRequest(request);
  if (errors.length) {
    emit({ type: "error", error_code: errors[0], errors });
    process.exitCode = 2;
    return;
  }
  if (process.env.NEXUS_CODEX_SDK_FAKE_MODE === "1") {
    const events = [
      { type: "thread.started", thread_id: `thread-${request.assignment_id}` },
      { type: "turn.completed", turn_id: `turn-${request.assignment_id}` },
    ];
    for (const event of events) {
      emit(event);
    }
    emit(mapSdkEventsToResult(events));
    return;
  }
  buildSdkPrompt(request);
  const result = await runCodexSdkTransport({ request, emit });
  if (result.status !== "completed_execution") {
    process.exitCode = 3;
  }
}

function emit(event) {
  process.stdout.write(`${JSON.stringify(event)}\n`);
}

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

await main();
