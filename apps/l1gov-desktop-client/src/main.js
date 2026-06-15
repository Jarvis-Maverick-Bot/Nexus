let state;
let activePanelId = "main_cockpit";

const $ = (id) => document.getElementById(id);
const PANEL_REGISTRY = Object.freeze({
  main_cockpit: {
    title: "Operation Panel Host",
    body: "Select a shell menu item to open a child-panel placeholder. Main Cockpit and ContextEnvelope stay visible.",
    status: "No command is executed from shell navigation."
  },
  project_shell: {
    title: "Project Management",
    body: "CP-001 shell route only. Project child panels are planned for CP-002.",
    status: "Read-only navigation treatment; no command is executed from shell navigation."
  },
  agent_shell: {
    title: "Agent Management",
    body: "CP-001 shell route only. Agent child panels are planned for CP-003.",
    status: "Read-only navigation treatment; no live agent calls."
  },
  mq_shell: {
    title: "MQ Management",
    body: "CP-001 shell route only. MQ child panels are planned for CP-004.",
    status: "Read-only navigation treatment; no queue execution."
  },
  workspace_picker: {
    title: "Workspace Picker",
    body: "Workspace picker opens as an overlay and does not become canonical authority.",
    status: "Workspace rows are navigation/display only."
  },
  evidence_drawer: {
    title: "Evidence",
    body: "Evidence links remain display-only. Evidence does not become canonical authority.",
    status: "No command is executed from shell navigation."
  },
  status_toast: {
    title: "Status Toast",
    body: "Status toast is display-only and cannot submit commands.",
    status: "Display-only status surface."
  }
});
const INIT_FIELDS = [
  ["project_charter", "init-field-project-charter"],
  ["stakeholder_authority", "init-field-stakeholder-authority"],
  ["scope", "init-field-scope"],
  ["requirements", "init-field-requirements"],
  ["risks", "init-field-risks"],
  ["dependencies", "init-field-dependencies"],
  ["backlog_wbs", "init-field-backlog-wbs"],
  ["execution_plan", "init-field-execution-plan"]
];

function normalizeFreshness(value) {
  return ["stale", "rebuilding", "current", "blocked"].includes(value) ? value : "stale";
}

function invoke(command, args = {}) {
  const api = window.__TAURI__?.core?.invoke;
  if (!api) {
    throw new Error("Tauri command bridge is unavailable; launch the desktop app, not a browser preview.");
  }
  return api(command, args);
}

function pendingRealUatState() {
  return buildSurfaceState({
    source_mode: "real_test_project_pending",
    fixture_only: false,
    canonical_records_path: "",
    projection_path: "",
    projection: { source_checkpoint: "none", payload: {} },
    service_outcome: { status: "pending", error_code: null, message: "" },
    stale_refresh: { states: ["stale", "rebuilding", "current"] },
    future_integration_boundary: {
      daemon_controller_bridge: "disabled_future_boundary",
      can_execute_live_calls: false
    },
    display_state: {
      workspace_name: "No real TestProject yet",
      freshness_index: 0,
      project_summary: {
        accepted_slices: 12,
        active_slice: "L1GOV-SLICE-012-REAL-UAT",
        blocked_items: 0,
        canonical_records: 0
      },
      modules: {
        mission_control: {
          title: "Active Session Cockpit",
          summary: "Create TestProject to start real local UAT."
        },
        project_init: {
          title: "Project Init",
          summary: "Create TestProject first to load the workspace init checklist."
        },
        standardization: {
          title: "Standardization",
          summary: "Waiting for real TestProject projection."
        },
        monitor_hitl: {
          title: "Monitor/HITL",
          summary: "Direct UI approval remains blocked."
        },
        delivery_feedback: {
          title: "Delivery Feedback",
          summary: "No closeout claim is made."
        },
        notes_evidence: {
          title: "Notes Evidence",
          summary: "Real UAT evidence will be written under verification/4.21/real-uat."
        }
      },
      workspaces: [],
      init_status: "create_project_first",
      init_values: {},
      init_requirements: [],
      notes: [
        "Create TestProject from this desktop app to write local canonical records.",
        "The desktop surface remains non-authoritative.",
        "Runs local test bridge only."
      ],
      service_state: "real local test pending",
      sync_state: "no projection loaded"
    }
  });
}

function buildSurfaceState(source) {
  const displayState = source.display_state;
  const freshnessCycle = source.stale_refresh.states;
  const freshnessIndex = displayState.freshness_index;
  const freshness = normalizeFreshness(freshnessCycle[freshnessIndex] || "stale");

  return {
    source,
    sourceMode: source.source_mode,
    fixtureOnly: source.fixture_only,
    workspaceName: displayState.workspace_name,
    freshness,
    freshnessCycle,
    freshnessIndex,
    projectSummary: {
      acceptedSlices: displayState.project_summary.accepted_slices,
      activeSlice: displayState.project_summary.active_slice,
      blockedItems: displayState.project_summary.blocked_items,
      canonicalRecords: displayState.project_summary.canonical_records || 0
    },
    modules: displayState.modules,
    workspaces: displayState.workspaces,
    initStatus: displayState.init_status || "create_project_first",
    initValues: displayState.init_values || {},
    initRequirements: displayState.init_requirements || [],
    notes: displayState.notes,
    serviceState: displayState.service_state,
    syncState: displayState.sync_state,
    contextEnvelope: {
      project: displayState.workspace_name,
      session: displayState.session_name || "Session 2",
      agent: displayState.active_agent || "Agent2 observer",
      source: source.source_mode,
      freshness,
      liveInvocation: source.live_execution_invoked === true ? "true" : "false",
      authority: source.non_authoritative === false ? "service-mediated" : "non-authoritative"
    }
  };
}

async function loadRealProjectionState() {
  const payload = await invoke("read_test_project_projection");
  return buildSurfaceState(JSON.parse(payload));
}

async function createRealTestProject() {
  setServiceMessage("Creating TestProject through local Governance Service path...");
  const payload = await invoke("create_test_project");
  state = buildSurfaceState(JSON.parse(payload));
  render();
  $("workspace-overlay").close();
  setServiceMessage("ACCEPTED: TestProject canonical record and projection are current.");
}

async function cleanupRealTestProject() {
  await invoke("cleanup_test_project");
  state = pendingRealUatState();
  render();
  $("workspace-overlay").close();
  setServiceMessage("Cleanup completed for local TestProject data.");
}

async function saveProjectInitDraft() {
  setServiceMessage("Saving Project Init draft into local TestProject workspace...");
  const payloadJson = JSON.stringify(collectInitValues());
  const payload = await invoke("save_project_init_draft", { payloadJson });
  state = buildSurfaceState(JSON.parse(payload));
  render();
  setServiceMessage("ACCEPTED: Project Init draft saved locally; canonical authority remains Kernel/Service.");
}

async function loadFixtureState() {
  const response = await fetch("./fixtures/slice012_desktop_state.json");
  if (!response.ok) {
    throw new Error(`failed to load deterministic fixture: ${response.status}`);
  }
  const fixture = await response.json();
  return buildSurfaceState({ ...fixture, source_mode: "reference_fixture", fixture_only: true });
}

function render() {
  renderContextEnvelope();
  $("workspace-name").textContent = state.workspaceName;
  $("accepted-slices").textContent = state.projectSummary.acceptedSlices;
  $("active-slice").textContent = state.projectSummary.activeSlice;
  $("blocked-items").textContent = state.projectSummary.blockedItems;
  $("canonical-records").textContent = state.projectSummary.canonicalRecords;
  $("freshness-chip").textContent = state.freshness;
  $("freshness-chip").className = `chip ${state.freshness}`;
  $("freshness-state").textContent = state.freshness;
  $("service-state").textContent = state.serviceState;
  $("service-chip").textContent = `service ${state.serviceState}`;
  $("sync-state").textContent = state.syncState;
  $("inspector-projection").textContent = projectionLabel();
  $("real-uat-copy").textContent = realUatCopy();
  $("real-uat-path").textContent = state.source.projection_path || "No real projection loaded.";
  renderProjectInit();
  renderOperationPanel(activePanelId);
  $("notes-list").replaceChildren(
    ...state.notes.map((note) => {
      const item = document.createElement("li");
      item.textContent = note;
      return item;
    })
  );
  renderFutureIntegrationBoundary();
}

function renderContextEnvelope() {
  const context = state.contextEnvelope;
  $("context-project").textContent = context.project;
  $("context-session").textContent = context.session;
  $("context-agent").textContent = context.agent;
  $("context-source").textContent = context.source;
  $("context-freshness").textContent = context.freshness;
  $("context-freshness").className = `chip ${context.freshness}`;
  $("context-live-invocation").textContent = context.liveInvocation;
  $("context-authority").textContent = context.authority;
}

function failClosedPanelRoute(panelId) {
  activePanelId = "main_cockpit";
  $("operation-panel-title").textContent = "Panel route rejected";
  $("operation-panel-status").textContent = "ERR_INVALID_PANEL_ROUTE";
  $("operation-panel-body").textContent = `Unknown panel route ${panelId}; shell navigation failed closed. No command is executed from shell navigation.`;
  return false;
}

function renderOperationPanel(panelId = activePanelId) {
  const panel = PANEL_REGISTRY[panelId];
  if (!panel) {
    return failClosedPanelRoute(panelId);
  }
  $("operation-panel-title").textContent = panel.title;
  $("operation-panel-status").textContent = panel.status;
  $("operation-panel-body").textContent = panel.body;
  return true;
}

function selectOperationPanel(panelId) {
  activePanelId = panelId;
  renderOperationPanel(panelId);
}

function openWorkspacePicker() {
  const overlay = $("workspace-overlay");
  const list = $("workspace-list");
  const workspaces = state.workspaces.length
    ? state.workspaces
    : [{ id: "pending", label: "Create TestProject first", freshness: "blocked" }];
  list.replaceChildren(
    ...workspaces.map((workspace) => {
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
  if (moduleId === "project_init") {
    $("project-init").scrollIntoView({ block: "nearest" });
  }
}

function showCommandDraftPreview() {
  $("command-draft-preview").innerHTML = `
    <h3>Command Draft Preview</h3>
    <p>SubmitCommandDraft preview for Governance Service review path. No canonical mutation.</p>
    <code>target_ref=layer1-governance, affects_state=false, source_mode=${state.sourceMode}</code>
  `;
}

function showInitCommandDraft() {
  const draftedCount = state.initRequirements.filter((item) => item.status === "drafted").length;
  $("command-draft-preview").innerHTML = `
    <h3>Command Draft Preview</h3>
    <p>SubmitCommandDraft preview for Project Init. The draft references workspace files and does not make the UI authoritative.</p>
    <code>command_type=SubmitCommandDraft, target_ref=${state.workspaceName}, init_status=${state.initStatus}, drafted_fields=${draftedCount}, affects_state=false</code>
  `;
}

function showServiceRejection() {
  $("service-outcome-copy").textContent = "REJECTED ERR_INVALID_TRANSITION: malformed command draft remains rejected.";
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
  const boundary = state.source.future_integration_boundary.daemon_controller_bridge;
  $("future-boundary").textContent = `${boundary}; real local UAT bridge only`;
}

function renderProjectInit() {
  const workspaceRoot = state.source.projection?.payload?.workspace_root || "No workspace loaded.";
  $("init-workspace-root").textContent = workspaceRoot;
  $("init-status-copy").textContent =
    state.initStatus === "draft_required"
      ? "Required initialization info is seeded as workspace files. Draft through Governance Service before any canonical change."
      : "Create TestProject from Workspace Picker before entering initialization information.";
  for (const [key, elementId] of INIT_FIELDS) {
    const field = $(elementId);
    if (document.activeElement !== field) {
      field.value = state.initValues[key] || "";
    }
  }

  const requirements = state.initRequirements.length
    ? state.initRequirements
    : [{ field: "Create TestProject first", status: "blocked", path: "Workspace Picker > Create TestProject" }];

  $("init-required-list").replaceChildren(
    ...requirements.map((requirement) => {
      const item = document.createElement("li");
      const label = document.createElement("span");
      const path = document.createElement("code");
      const status = document.createElement("span");
      label.textContent = requirement.field;
      path.textContent = requirement.path;
      status.className = `chip ${normalizeFreshness(requirement.status === "needs_input" ? "stale" : requirement.status)}`;
      status.textContent = requirement.status;
      item.append(label, status, path);
      return item;
    })
  );
}

function collectInitValues() {
  return Object.fromEntries(INIT_FIELDS.map(([key, elementId]) => [key, $(elementId).value.trim()]));
}

function bindEvents() {
  $("workspace-picker").addEventListener("click", openWorkspacePicker);
  document.querySelectorAll("[data-panel-route]").forEach((button) => {
    button.addEventListener("click", () => selectOperationPanel(button.dataset.panelRoute));
  });
  $("create-testproject").addEventListener("click", () => {
    createRealTestProject().catch((error) => setServiceError(error));
  });
  $("cleanup-testproject").addEventListener("click", () => {
    cleanupRealTestProject().catch((error) => setServiceError(error));
  });
  $("refresh-projection").addEventListener("click", () => {
    loadRealProjectionState()
      .then((loaded) => {
        state = loaded;
        render();
        setServiceMessage("Projection refreshed from real local TestProject state.");
      })
      .catch(() => cycleStaleRefresh());
  });
  $("draft-command-button").addEventListener("click", showCommandDraftPreview);
  $("save-init-draft").addEventListener("click", () => {
    saveProjectInitDraft().catch((error) => setServiceError(error));
  });
  $("draft-init-command").addEventListener("click", showInitCommandDraft);
  $("show-rejection").addEventListener("click", showServiceRejection);
  $("no-go-block").addEventListener("click", showNoGoBlock);
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", () => selectModule(button.dataset.module));
  });
}

async function initialize() {
  bindEvents();
  try {
    state = await loadRealProjectionState();
  } catch {
    state = pendingRealUatState();
  }
  render();
}

function projectionLabel() {
  const projection = state.source.projection || {};
  return `${projection.projection_type || "none"}:${projection.source_checkpoint || "none"}`;
}

function realUatCopy() {
  if (state.sourceMode === "real_test_project") {
    return "Real TestProject canonical record and projection are loaded.";
  }
  return "Create TestProject to write local Kernel records and rebuild the projection.";
}

function setServiceMessage(message) {
  $("service-outcome-copy").textContent = message;
  $("service-rejection").classList.remove("blocked");
}

function setServiceError(error) {
  $("service-outcome-copy").textContent = `BLOCKED: ${error.message}`;
  $("service-rejection").classList.add("blocked");
}

initialize().catch((error) => setServiceError(error));

window.slice012DesktopSurface = {
  buildSurfaceState,
  PANEL_REGISTRY,
  loadFixtureState,
  loadRealProjectionState,
  createRealTestProject,
  cleanupRealTestProject,
  saveProjectInitDraft,
  openWorkspacePicker,
  renderProjectInit,
  collectInitValues,
  renderContextEnvelope,
  selectOperationPanel,
  renderOperationPanel,
  failClosedPanelRoute,
  selectModule,
  showCommandDraftPreview,
  showInitCommandDraft,
  showServiceRejection,
  showNoGoBlock,
  cycleStaleRefresh,
  renderFutureIntegrationBoundary
};
