let state;

const $ = (id) => document.getElementById(id);

function normalizeFreshness(value) {
  return ["stale", "rebuilding", "current", "blocked"].includes(value) ? value : "stale";
}

function buildSurfaceState(fixture) {
  const displayState = fixture.display_state;
  const freshnessCycle = fixture.stale_refresh.states;
  const freshnessIndex = displayState.freshness_index;
  const freshness = normalizeFreshness(freshnessCycle[freshnessIndex] || "stale");

  return {
    fixture,
    workspaceName: displayState.workspace_name,
    freshness,
    freshnessCycle,
    freshnessIndex,
    projectSummary: {
      acceptedSlices: displayState.project_summary.accepted_slices,
      activeSlice: displayState.project_summary.active_slice,
      blockedItems: displayState.project_summary.blocked_items
    },
    modules: displayState.modules,
    workspaces: displayState.workspaces,
    notes: displayState.notes,
    serviceState: displayState.service_state,
    syncState: displayState.sync_state
  };
}

async function loadFixtureState() {
  const response = await fetch("./fixtures/slice012_desktop_state.json");
  if (!response.ok) {
    throw new Error(`failed to load deterministic fixture: ${response.status}`);
  }
  const fixture = await response.json();
  if (fixture.slice_id !== "L1GOV-SLICE-012" || fixture.live_execution_invoked !== false) {
    throw new Error("invalid Slice 012 fixture boundary");
  }
  return buildSurfaceState(fixture);
}

function render() {
  $("workspace-name").textContent = state.workspaceName;
  $("accepted-slices").textContent = state.projectSummary.acceptedSlices;
  $("active-slice").textContent = state.projectSummary.activeSlice;
  $("blocked-items").textContent = state.projectSummary.blockedItems;
  $("freshness-chip").textContent = state.freshness;
  $("freshness-chip").className = `chip ${state.freshness}`;
  $("freshness-state").textContent = state.freshness;
  $("service-state").textContent = state.serviceState;
  $("service-chip").textContent = `service ${state.serviceState}`;
  $("sync-state").textContent = state.syncState;
  $("notes-list").replaceChildren(
    ...state.notes.map((note) => {
      const item = document.createElement("li");
      item.textContent = note;
      return item;
    })
  );
  renderFutureIntegrationBoundary();
}

function openWorkspacePicker() {
  const overlay = $("workspace-overlay");
  const list = $("workspace-list");
  list.replaceChildren(
    ...state.workspaces.map((workspace) => {
      const button = document.createElement("button");
      button.className = "workspace-option";
      button.type = "button";
      button.innerHTML = `<span>${workspace.label}</span><span class="chip ${workspace.freshness}">${workspace.freshness}</span>`;
      button.addEventListener("click", () => {
        state.workspaceName = workspace.label;
        state.freshness = normalizeFreshness(workspace.freshness);
        overlay.close();
        render();
      });
      return button;
    })
  );
  overlay.showModal();
}

function selectModule(moduleId) {
  const module = state.modules[moduleId] || state.modules.mission_control;
  $("active-module-title").textContent = module.title;
  $("active-module-summary").textContent = module.summary;
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.module === moduleId);
  });
}

function showCommandDraftPreview() {
  $("command-draft-preview").innerHTML = `
    <h3>Command Draft Preview</h3>
    <p>SubmitCommandDraft preview for Governance Service review path. No canonical mutation.</p>
    <code>target_ref=layer1-governance, affects_state=false</code>
  `;
}

function showServiceRejection() {
  $("service-outcome-copy").textContent = "REJECTED ERR_INVALID_TRANSITION: service route preview is fixture-backed only.";
  $("service-rejection").classList.remove("blocked");
}

function showNoGoBlock() {
  $("service-outcome-copy").textContent = "BLOCKED ERR_NO_GO_BOUNDARY: direct UI approval is blocked and must route through Monitor/HITL.";
  $("service-rejection").classList.add("blocked");
}

function cycleStaleRefresh() {
  state.freshnessIndex = (state.freshnessIndex + 1) % state.freshnessCycle.length;
  state.freshness = normalizeFreshness(state.freshnessCycle[state.freshnessIndex]);
  $("stale-copy").textContent = `Projection display state is ${state.freshness}. No canonical mutation.`;
  render();
}

function renderFutureIntegrationBoundary() {
  const boundary = state.fixture.future_integration_boundary.daemon_controller_bridge;
  $("future-boundary").textContent = `${boundary}; deterministic fixture display only`;
}

function bindEvents() {
  $("workspace-picker").addEventListener("click", openWorkspacePicker);
  $("refresh-projection").addEventListener("click", cycleStaleRefresh);
  $("draft-command-button").addEventListener("click", showCommandDraftPreview);
  $("show-rejection").addEventListener("click", showServiceRejection);
  $("no-go-block").addEventListener("click", showNoGoBlock);
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", () => selectModule(button.dataset.module));
  });
}

async function initialize() {
  state = await loadFixtureState();
  bindEvents();
  render();
}

initialize().catch((error) => {
  $("service-outcome-copy").textContent = `Fixture load failed: ${error.message}`;
  $("service-rejection").classList.add("blocked");
});

window.slice012DesktopSurface = {
  buildSurfaceState,
  loadFixtureState,
  openWorkspacePicker,
  selectModule,
  showCommandDraftPreview,
  showServiceRejection,
  showNoGoBlock,
  cycleStaleRefresh,
  renderFutureIntegrationBoundary
};
