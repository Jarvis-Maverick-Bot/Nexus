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
    body: "Project menu open. Choose a Project Management child panel; shell state and ContextEnvelope stay visible.",
    status: "Frame 03 Project menu open; no command is executed from shell navigation.",
    actions: [
      { label: "Create Project", panelId: "project_create" },
      { label: "Init Project", panelId: "project_init_dirty" },
      { label: "Standardization", panelId: "project_standardization_preview" }
    ]
  },
  project_create: {
    title: "Create Project",
    status: "Command draft preview only; creates_authority=false.",
    render: renderProjectCreatePanel
  },
  project_init_dirty: {
    title: "Init Project Dirty State",
    status: "Dirty local draft fields; affects_state=false until service-mediated review.",
    render: renderProjectInitDirtyPanel
  },
  project_standardization_preview: {
    title: "Standardization Preview",
    status: "Preview-only planning packet candidate; no direct baseline approval.",
    render: renderProjectStandardizationPanel
  },
  agent_shell: {
    title: "Agent Management",
    body: "Agent menu open. Choose an Agent Management child panel; ContextEnvelope remains visible.",
    status: "Frame 07 Agent menu open; private_agent_invocation=false; runtime_control_activation=false.",
    actions: [
      { label: "Agent Directory", panelId: "agent_directory" },
      { label: "Assign Agent", panelId: "agent_assignment" },
      { label: "Runtime Status", panelId: "agent_runtime_status_blocked" },
      { label: "Configure Agent", panelId: "agent_configure" }
    ]
  },
  agent_directory: {
    title: "Agent Directory",
    status: "Read-only projected agent rows; private_agent_invocation=false.",
    render: renderAgentDirectoryPanel
  },
  agent_assignment: {
    title: "Assign Agent",
    status: "Display-only ContextEnvelope update preview; command draft preview only.",
    render: renderAgentAssignmentPanel
  },
  agent_runtime_status_blocked: {
    title: "Runtime Status Blocked",
    status: "Blocked runtime status display; runtime_control_activation=false.",
    render: renderAgentRuntimeStatusPanel
  },
  agent_configure: {
    title: "Configure Agent",
    status: "Configuration preview only; private_agent_invocation=false.",
    render: renderAgentConfigurePanel
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
const DEFAULT_PROJECT_MANAGEMENT = Object.freeze({
  creates_authority: false,
  command_draft_preview_only: true,
  create_project: {
    project_name: "TestProject",
    workspace_root: "verification/4.21/real-uat/testproject/workspace",
    source_refs: ["ContextEnvelope", "Workspace Picker"],
    expected_version: 1,
    idempotency_key: "cp002-create-project-preview"
  },
  init_project: {
    dirty_state: true,
    dirty_fields: ["project_charter", "stakeholder_authority", "scope", "requirements"],
    expected_version: 1,
    idempotency_key: "cp002-init-project-preview"
  },
  standardization_preview: {
    profile_ref: "DeliverableEvaluationProfile:standardization-preview",
    feedback_policy_ref: "FeedbackMetricPolicy:project-management-preview",
    evidence_plan: "README_EVIDENCE.md + screenshot evidence",
    expected_version: 1,
    idempotency_key: "cp002-standardization-preview"
  }
});
const DEFAULT_AGENT_MANAGEMENT = Object.freeze({
  private_agent_invocation: false,
  runtime_control_activation: false,
  command_draft_preview_only: true,
  directory: {
    agents: [
      { id: "agent:observer", label: "Agent2 observer", status: "current", role: "Observer" },
      { id: "agent:planner", label: "Agent3 planning candidate", status: "preview", role: "Planner" }
    ]
  },
  assignment: {
    target_agent: "Agent3 planning candidate",
    target_session: "Session 2",
    context_update: "display-only",
    expected_version: 1,
    idempotency_key: "cp003-agent-assignment-preview"
  },
  runtime_status: {
    status: "blocked",
    error_code: "ERR_NO_GO_BOUNDARY",
    reason: "private_agent_invocation=false; runtime_control_activation=false"
  },
  configure_agent: {
    role: "Planner",
    allowed_actions: ["draft planning notes", "prepare evidence checklist"],
    forbidden_actions: ["private_agent_invocation", "runtime_control_activation"],
    expected_version: 1,
    idempotency_key: "cp003-agent-configure-preview"
  }
});

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
    projectManagement: displayState.project_management || DEFAULT_PROJECT_MANAGEMENT,
    agentManagement: displayState.agent_management || DEFAULT_AGENT_MANAGEMENT,
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
  const body = $("operation-panel-body");
  body.replaceChildren();
  if (panel.render) {
    panel.render(body);
    return true;
  }
  appendPanelParagraph(body, panel.body);
  renderPanelActions(body, panel.actions || []);
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

function projectManagementState() {
  return state?.projectManagement || DEFAULT_PROJECT_MANAGEMENT;
}

function appendPanelParagraph(container, text) {
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  container.append(paragraph);
}

function appendPanelCode(container, text) {
  const code = document.createElement("code");
  code.textContent = text;
  container.append(code);
}

function appendPanelList(container, items) {
  const list = document.createElement("ul");
  list.className = "panel-detail-list";
  for (const item of items) {
    const row = document.createElement("li");
    row.textContent = item;
    list.append(row);
  }
  container.append(list);
}

function renderPanelActions(container, actions) {
  if (!actions.length) {
    return;
  }
  const row = document.createElement("div");
  row.className = "operation-panel-actions";
  for (const action of actions) {
    const button = document.createElement("button");
    button.className = action.danger ? "button danger" : "button";
    button.type = "button";
    button.textContent = action.label;
    button.addEventListener("click", () => {
      if (action.panelId) {
        selectOperationPanel(action.panelId);
      }
      if (action.command === "create_project_preview") {
        showProjectCreateDraftPreview();
      }
      if (action.command === "init_project_preview") {
        showProjectInitDraftPreview();
      }
      if (action.command === "standardization_preview") {
        showProjectStandardizationDraftPreview();
      }
      if (action.command === "project_no_go") {
        showProjectNoGoBoundary();
      }
      if (action.command === "agent_assignment_preview") {
        showAgentAssignmentDraftPreview();
      }
      if (action.command === "agent_configure_preview") {
        showAgentConfigureDraftPreview();
      }
      if (action.command === "agent_runtime_block") {
        showAgentRuntimeBlocked();
      }
    });
    row.append(button);
  }
  container.append(row);
}

function renderProjectCreatePanel(container) {
  const createProject = projectManagementState().create_project;
  appendPanelParagraph(container, "Draft a new project candidate from workspace root and source refs. This panel creates a command draft preview only.");
  appendPanelCode(container, `project_name=${createProject.project_name}; workspace_root=${createProject.workspace_root}`);
  appendPanelList(container, [
    `source_refs=${createProject.source_refs.join(", ")}`,
    `expected_version=${createProject.expected_version}`,
    `idempotency_key=${createProject.idempotency_key}`,
    "affects_state=false",
    "creates_authority=false"
  ]);
  renderPanelActions(container, [
    { label: "Preview Create Project Draft", command: "create_project_preview" },
    { label: "Show Project Boundary Block", command: "project_no_go", danger: true }
  ]);
}

function renderProjectInitDirtyPanel(container) {
  const initProject = projectManagementState().init_project;
  appendPanelParagraph(container, "Init Project Dirty State keeps local draft fields visible until a Governance Service command draft is reviewed.");
  appendPanelList(container, [
    `dirty_state=${initProject.dirty_state}`,
    `dirty_fields=${initProject.dirty_fields.join(", ")}`,
    `expected_version=${initProject.expected_version}`,
    `idempotency_key=${initProject.idempotency_key}`,
    "affects_state=false",
    "creates_authority=false"
  ]);
  renderPanelActions(container, [
    { label: "Preview Init Project Draft", command: "init_project_preview" },
    { label: "Show Project Boundary Block", command: "project_no_go", danger: true }
  ]);
}

function renderProjectStandardizationPanel(container) {
  const preview = projectManagementState().standardization_preview;
  appendPanelParagraph(container, "Standardization Preview displays a planning packet candidate for review. It cannot approve a baseline or write canonical records.");
  appendPanelList(container, [
    `profile_ref=${preview.profile_ref}`,
    `feedback_policy_ref=${preview.feedback_policy_ref}`,
    `evidence_plan=${preview.evidence_plan}`,
    `expected_version=${preview.expected_version}`,
    `idempotency_key=${preview.idempotency_key}`,
    "affects_state=false",
    "creates_authority=false"
  ]);
  renderPanelActions(container, [
    { label: "Preview Standardization Draft", command: "standardization_preview" },
    { label: "Show Project Boundary Block", command: "project_no_go", danger: true }
  ]);
}

function renderProjectDraftPreview(title, description, details) {
  $("command-draft-preview").innerHTML = `
    <h3>${title}</h3>
    <p>${description}</p>
    <code>${details.join("; ")}</code>
  `;
}

function showProjectCreateDraftPreview() {
  const createProject = projectManagementState().create_project;
  renderProjectDraftPreview("Command Draft Preview", "Create Project route is preview-only and must be mediated by Governance Service.", [
    "command_type=SubmitCommandDraft",
    "subtype=ProjectCreatePanel",
    `project_name=${createProject.project_name}`,
    `source_refs=${createProject.source_refs.join("|")}`,
    `expected_version=${createProject.expected_version}`,
    `idempotency_key=${createProject.idempotency_key}`,
    "affects_state=false",
    "creates_authority=false"
  ]);
}

function showProjectInitDraftPreview() {
  const initProject = projectManagementState().init_project;
  renderProjectDraftPreview("Command Draft Preview", "Init Project dirty fields are prepared as draft metadata only.", [
    "command_type=SubmitCommandDraft",
    "subtype=ProjectInitPanel",
    `dirty_fields=${initProject.dirty_fields.join("|")}`,
    `expected_version=${initProject.expected_version}`,
    `idempotency_key=${initProject.idempotency_key}`,
    "affects_state=false",
    "creates_authority=false"
  ]);
}

function showProjectStandardizationDraftPreview() {
  const preview = projectManagementState().standardization_preview;
  renderProjectDraftPreview("Command Draft Preview", "Standardization candidate remains preview-only until a later approved service path.", [
    "command_type=SubmitCommandDraft",
    "subtype=ProjectStandardizationPanel",
    `source_refs=${preview.profile_ref}|${preview.feedback_policy_ref}`,
    `expected_version=${preview.expected_version}`,
    `idempotency_key=${preview.idempotency_key}`,
    "affects_state=false",
    "creates_authority=false"
  ]);
}

function showProjectNoGoBoundary() {
  $("service-outcome-copy").textContent = "BLOCKED ERR_NO_GO_BOUNDARY: direct baseline approval and direct canonical mutation are blocked; use Governance Service command draft preview.";
  $("service-rejection").classList.add("blocked");
}

function agentManagementState() {
  return state?.agentManagement || DEFAULT_AGENT_MANAGEMENT;
}

function renderAgentDirectoryPanel(container) {
  const directory = agentManagementState().directory;
  appendPanelParagraph(container, "Agent Directory displays projected agent rows for review only. private_agent_invocation=false.");
  appendPanelList(container, directory.agents.map((agent) => `${agent.label}; role=${agent.role}; status=${agent.status}`));
  renderPanelActions(container, [
    { label: "Assign Agent", panelId: "agent_assignment" },
    { label: "Configure Agent", panelId: "agent_configure" },
    { label: "Runtime Status", panelId: "agent_runtime_status_blocked" }
  ]);
}

function renderAgentAssignmentPanel(container) {
  const assignment = agentManagementState().assignment;
  appendPanelParagraph(container, "Assign Agent prepares a display-only ContextEnvelope update and a Governance Service command draft preview.");
  appendPanelList(container, [
    `target_agent=${assignment.target_agent}`,
    `target_session=${assignment.target_session}`,
    `context_update=${assignment.context_update}`,
    `expected_version=${assignment.expected_version}`,
    `idempotency_key=${assignment.idempotency_key}`,
    "private_agent_invocation=false",
    "runtime_control_activation=false"
  ]);
  renderPanelActions(container, [
    { label: "Preview Agent Assignment Draft", command: "agent_assignment_preview" },
    { label: "Show Runtime Boundary Block", command: "agent_runtime_block", danger: true }
  ]);
}

function renderAgentRuntimeStatusPanel(container) {
  const runtimeStatus = agentManagementState().runtime_status;
  appendPanelParagraph(container, "Runtime Status Blocked shows diagnostic state only. Runtime control activation stays disabled.");
  appendPanelList(container, [
    `status=${runtimeStatus.status}`,
    `error_code=${runtimeStatus.error_code}`,
    runtimeStatus.reason
  ]);
  renderPanelActions(container, [
    { label: "Show Runtime Boundary Block", command: "agent_runtime_block", danger: true }
  ]);
}

function renderAgentConfigurePanel(container) {
  const config = agentManagementState().configure_agent;
  appendPanelParagraph(container, "Configure Agent previews role and evidence expectations with private_agent_invocation=false.");
  appendPanelList(container, [
    `role=${config.role}`,
    `allowed_actions=${config.allowed_actions.join(", ")}`,
    `forbidden_actions=${config.forbidden_actions.join(", ")}`,
    `expected_version=${config.expected_version}`,
    `idempotency_key=${config.idempotency_key}`,
    "private_agent_invocation=false",
    "runtime_control_activation=false"
  ]);
  renderPanelActions(container, [
    { label: "Preview Configure Agent Draft", command: "agent_configure_preview" },
    { label: "Show Runtime Boundary Block", command: "agent_runtime_block", danger: true }
  ]);
}

function showAgentAssignmentDraftPreview() {
  const assignment = agentManagementState().assignment;
  state.contextEnvelope.agent = assignment.target_agent;
  renderContextEnvelope();
  renderProjectDraftPreview("Command Draft Preview", "Agent assignment is a display-only context update plus command draft preview.", [
    "command_type=SubmitCommandDraft",
    "subtype=AgentAssignmentPanel",
    `target_agent=${assignment.target_agent}`,
    `target_session=${assignment.target_session}`,
    `context_update=${assignment.context_update}`,
    `expected_version=${assignment.expected_version}`,
    `idempotency_key=${assignment.idempotency_key}`,
    "private_agent_invocation=false",
    "runtime_control_activation=false"
  ]);
}

function showAgentConfigureDraftPreview() {
  const config = agentManagementState().configure_agent;
  renderProjectDraftPreview("Command Draft Preview", "Configure Agent prepares draft-only role and evidence expectations.", [
    "command_type=SubmitCommandDraft",
    "subtype=AgentConfigurePanel",
    `role=${config.role}`,
    `expected_version=${config.expected_version}`,
    `idempotency_key=${config.idempotency_key}`,
    "private_agent_invocation=false",
    "runtime_control_activation=false"
  ]);
}

function showAgentRuntimeBlocked() {
  const runtimeStatus = agentManagementState().runtime_status;
  $("service-outcome-copy").textContent = `BLOCKED ${runtimeStatus.error_code}: private_agent_invocation=false; runtime_control_activation=false.`;
  $("service-rejection").classList.add("blocked");
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
  renderProjectCreatePanel,
  renderProjectInitDirtyPanel,
  renderProjectStandardizationPanel,
  showProjectCreateDraftPreview,
  showProjectInitDraftPreview,
  showProjectStandardizationDraftPreview,
  showProjectNoGoBoundary,
  renderAgentDirectoryPanel,
  renderAgentAssignmentPanel,
  renderAgentRuntimeStatusPanel,
  renderAgentConfigurePanel,
  showAgentAssignmentDraftPreview,
  showAgentConfigureDraftPreview,
  showAgentRuntimeBlocked,
  selectModule,
  showCommandDraftPreview,
  showInitCommandDraft,
  showServiceRejection,
  showNoGoBlock,
  cycleStaleRefresh,
  renderFutureIntegrationBoundary
};
