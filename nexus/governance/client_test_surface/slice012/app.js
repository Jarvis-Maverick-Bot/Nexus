const state = {
  data: null,
  activeModule: "mission_control",
  refreshIndex: 2
};

const $ = (id) => document.getElementById(id);

async function loadFixture() {
  const response = await fetch("fixtures/slice012_state.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`fixture load failed: ${response.status}`);
  }
  state.data = await response.json();
  render();
  applyScenarioFromUrl();
}

function render() {
  renderWorkspaceList();
  renderModuleNav();
  renderMissionControl();
  renderNotes();
  bindActions();
}

function bindActions() {
  $("workspace-picker-button").onclick = openWorkspacePicker;
  $("workspace-close-button").onclick = closeWorkspacePicker;
  $("command-draft-button").onclick = showCommandDraftPreview;
  $("service-rejection-button").onclick = showServiceRejection;
  $("no-go-button").onclick = showNoGoBlock;
  $("stale-refresh-button").onclick = cycleStaleRefresh;
}

function openWorkspacePicker() {
  $("workspace-picker-overlay").classList.remove("hidden");
}

function closeWorkspacePicker() {
  $("workspace-picker-overlay").classList.add("hidden");
}

function selectWorkspace(workspaceRef) {
  const workspace = state.data.workspace_picker.workspaces.find((item) => item.ref === workspaceRef);
  if (!workspace) {
    return;
  }
  $("workspace-name").textContent = workspace.name;
  setFreshness(workspace.freshness);
  $("inspector-source-refs").textContent = workspace.ref;
  closeWorkspacePicker();
}

function selectModule(moduleId) {
  state.activeModule = moduleId;
  renderModuleNav();
  renderMissionControl();
}

function showCommandDraftPreview() {
  const draft = state.data.service_outcomes.draft_preview;
  $("command-draft-text").textContent =
    `${draft.command_type} preview for ${draft.target_ref}. ${draft.authority_effect}.`;
}

function showServiceRejection() {
  const rejection = state.data.service_outcomes.rejection;
  const panel = $("service-outcome-panel");
  panel.classList.add("blocked");
  $("service-outcome-text").textContent =
    `${rejection.status.toUpperCase()} ${rejection.error_code}: ${rejection.blocked_reason}`;
}

function showNoGoBlock() {
  const blocked = state.data.service_outcomes.no_go_block;
  const panel = $("service-outcome-panel");
  panel.classList.add("blocked");
  $("service-outcome-text").textContent =
    `${blocked.status.toUpperCase()} ${blocked.error_code}: ${blocked.blocked_reason}`;
}

function cycleStaleRefresh() {
  const states = state.data.stale_refresh.states;
  state.refreshIndex = (state.refreshIndex + 1) % states.length;
  const next = states[state.refreshIndex];
  setFreshness(next);
  const panel = $("stale-refresh-panel");
  panel.classList.toggle("rebuilt", next === "current");
  $("stale-refresh-text").textContent = `${next}: ${state.data.stale_refresh.note}.`;
}

function applyScenarioFromUrl() {
  const scenario = new URLSearchParams(window.location.search).get("scenario");
  if (scenario === "no-go") {
    showNoGoBlock();
  }
  if (scenario === "stale") {
    state.refreshIndex = 0;
    setFreshness("stale");
    $("stale-refresh-text").textContent = `stale: ${state.data.stale_refresh.note}.`;
  }
}

function renderWorkspaceList() {
  const list = $("workspace-list");
  list.replaceChildren();
  state.data.workspace_picker.workspaces.forEach((workspace) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "workspace-option";
    button.dataset.workspaceRef = workspace.ref;
    button.onclick = () => selectWorkspace(workspace.ref);
    button.innerHTML = `<strong>${workspace.name}</strong><span class="chip ${workspace.freshness}">${workspace.freshness}</span>`;
    list.appendChild(button);
  });
}

function renderModuleNav() {
  const nav = $("module-nav");
  nav.replaceChildren();
  state.data.modules.forEach((module) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `nav-button${module.id === state.activeModule ? " active" : ""}`;
    button.textContent = module.label;
    button.onclick = () => selectModule(module.id);
    nav.appendChild(button);
  });
}

function renderMissionControl() {
  const module = state.data.modules.find((item) => item.id === state.activeModule);
  $("active-module-title").textContent = module.label;
  $("active-module-summary").textContent = module.summary;
  $("active-slice").textContent = state.data.mission_control.project_summary.active_slice;
  $("accepted-slices").textContent = state.data.mission_control.project_summary.accepted_slices;
  $("blocked-items").textContent = state.data.mission_control.project_summary.blocked_items;
  $("inspector-projection").textContent = state.data.mission_control.projection_surface.projection_ref;
  $("inspector-source-refs").textContent = module.source_refs.join(", ");
}

function renderNotes() {
  const list = $("notes-list");
  list.replaceChildren();
  state.data.notes_evidence.items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  });
}

function setFreshness(value) {
  $("freshness-chip").textContent = value;
  $("freshness-chip").className = `chip ${value}`;
  $("status-freshness").textContent = value;
}

window.slice012Surface = {
  openWorkspacePicker,
  selectWorkspace,
  selectModule,
  showCommandDraftPreview,
  showServiceRejection,
  showNoGoBlock,
  cycleStaleRefresh,
  applyScenarioFromUrl
};

loadFixture().catch((error) => {
  $("service-state").textContent = "degraded";
  $("service-outcome-text").textContent = error.message;
});
