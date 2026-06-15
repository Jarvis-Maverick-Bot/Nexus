import { readFileSync } from "node:fs";

const fixture = JSON.parse(readFileSync(new URL("../src/fixtures/slice012_desktop_state.json", import.meta.url), "utf8"));
const html = readFileSync(new URL("../src/index.html", import.meta.url), "utf8");
const mainJs = readFileSync(new URL("../src/main.js", import.meta.url), "utf8");
const mainRs = readFileSync(new URL("../src-tauri/src/main.rs", import.meta.url), "utf8");
const tauriConfig = readFileSync(new URL("../src-tauri/tauri.conf.json", import.meta.url), "utf8");

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

if (!html.includes('id="create-testproject"') || !html.includes("Create TestProject")) {
  throw new Error("real TestProject creation surface is missing");
}

for (const expected of [
  'data-module="project_init">Project Init',
  'id="project-init"',
  'id="init-required-list"',
  'id="init-field-project-charter"',
  'id="init-field-execution-plan"',
  'id="save-init-draft"',
  'id="draft-init-command"'
]) {
  if (!html.includes(expected)) {
    throw new Error(`Project Init surface is missing ${expected}`);
  }
}

const topActions = html.split('<section class="workspace-strip"', 1)[0];
if (!html.includes('id="workspace-overlay"')) {
  throw new Error("workspace picker overlay is missing");
}
if (html.indexOf('id="workspace-overlay"') > html.indexOf('id="create-testproject"')) {
  throw new Error("real TestProject creation must live inside the workspace picker");
}
if (topActions.includes('id="create-testproject"') || topActions.includes('id="cleanup-testproject"')) {
  throw new Error("project lifecycle actions must not live in the main toolbar");
}

if (!html.includes('id="service-state">real local test pending')) {
  throw new Error("desktop service state must start as real local test pending");
}

for (const expected of [
  'invoke("create_test_project"',
  'invoke("read_test_project_projection"',
  'invoke("cleanup_test_project"',
  'invoke("save_project_init_draft"',
  "renderProjectInit",
  "saveProjectInitDraft",
  "showInitCommandDraft"
]) {
  if (!mainJs.includes(expected)) {
    throw new Error(`desktop bridge is missing ${expected}`);
  }
}

for (const expected of ["create_test_project", "read_test_project_projection", "cleanup_test_project"]) {
  if (!mainRs.includes(expected)) {
    throw new Error(`Tauri command is missing ${expected}`);
  }
}

if (!tauriConfig.includes('"withGlobalTauri": true')) {
  throw new Error("Tauri global command bridge is disabled");
}

console.log("slice012 desktop real UAT surface verified");
