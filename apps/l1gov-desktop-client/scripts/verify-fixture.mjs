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

if (fixture.display_state?.project_management?.creates_authority !== false) {
  throw new Error("Project Management fixture must remain non-authoritative");
}

if (fixture.display_state?.project_management?.command_draft_preview_only !== true) {
  throw new Error("Project Management fixture must be command draft preview only");
}

if (fixture.display_state?.agent_management?.private_agent_invocation !== false) {
  throw new Error("Agent Management fixture must not allow private_agent_invocation");
}

if (fixture.display_state?.agent_management?.runtime_control_activation !== false) {
  throw new Error("Agent Management fixture must not allow runtime_control_activation");
}

if (fixture.display_state?.agent_management?.command_draft_preview_only !== true) {
  throw new Error("Agent Management fixture must be command draft preview only");
}

if (fixture.display_state?.mq_management?.queue_execution !== false) {
  throw new Error("MQ Management fixture must not allow queue_execution");
}

if (fixture.display_state?.mq_management?.dispatch_execution !== false) {
  throw new Error("MQ Management fixture must not allow dispatch_execution");
}

if (fixture.display_state?.mq_management?.controller_call !== false) {
  throw new Error("MQ Management fixture must not allow controller_call");
}

if (fixture.display_state?.mq_management?.route_activation !== false) {
  throw new Error("MQ Management fixture must not allow route_activation");
}

if (fixture.display_state?.mq_management?.adapter_transport_activation !== false) {
  throw new Error("MQ Management fixture must not allow adapter_transport_activation");
}

if (fixture.display_state?.mq_management?.replay_execution !== false) {
  throw new Error("MQ Management fixture must not allow replay_execution");
}

if (fixture.display_state?.mq_management?.command_draft_preview_only !== true) {
  throw new Error("MQ Management fixture must be command draft preview only");
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

for (const expected of [
  "project_create",
  "project_init_dirty",
  "project_standardization_preview",
  "renderProjectCreatePanel",
  "renderProjectInitDirtyPanel",
  "renderProjectStandardizationPanel",
  "showProjectCreateDraftPreview",
  "showProjectInitDraftPreview",
  "showProjectStandardizationDraftPreview",
  "creates_authority=false"
]) {
  if (!mainJs.includes(expected)) {
    throw new Error(`CP-002 Project Management panel is missing ${expected}`);
  }
}

for (const expected of [
  "agent_directory",
  "agent_assignment",
  "agent_runtime_status_blocked",
  "agent_configure",
  "renderAgentDirectoryPanel",
  "renderAgentAssignmentPanel",
  "renderAgentRuntimeStatusPanel",
  "renderAgentConfigurePanel",
  "showAgentAssignmentDraftPreview",
  "showAgentConfigureDraftPreview",
  "showAgentRuntimeBlocked",
  "private_agent_invocation=false",
  "runtime_control_activation=false"
]) {
  if (!mainJs.includes(expected)) {
    throw new Error(`CP-003 Agent Management panel is missing ${expected}`);
  }
}

for (const expected of [
  "mq_queue_overview",
  "mq_message_detail",
  "mq_no_go_diagnostics",
  "mq_replay_evidence",
  "renderMqQueueOverviewPanel",
  "renderMqMessageDetailPanel",
  "renderMqNoGoDiagnosticsPanel",
  "renderMqReplayEvidencePanel",
  "showMqMessageDraftPreview",
  "showMqDispatchNoGo",
  "showMqReplayEvidencePreview",
  "queue_execution=false",
  "dispatch_execution=false",
  "replay_execution=false"
]) {
  if (!mainJs.includes(expected)) {
    throw new Error(`CP-004 MQ Management panel is missing ${expected}`);
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
