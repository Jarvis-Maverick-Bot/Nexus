import { readFileSync } from "node:fs";

const fixture = JSON.parse(readFileSync(new URL("../src/fixtures/slice012_desktop_state.json", import.meta.url), "utf8"));

if (fixture.slice_id !== "L1GOV-SLICE-012") {
  throw new Error("unexpected slice id");
}

if (fixture.non_authoritative !== true || fixture.live_execution_invoked !== false) {
  throw new Error("fixture boundary is invalid");
}

if (fixture.display_state?.service_state !== "fixture only") {
  throw new Error("fixture service state must be fixture only");
}

if (fixture.display_state?.workspace_name !== "4.21 Layer 1 Governance") {
  throw new Error("fixture workspace name is invalid");
}

console.log("slice012 desktop fixture verified");
