const state = {
  workspaceName: "4.21 Layer 1 Governance",
  freshness: "current",
  freshnessCycle: ["stale", "rebuilding", "current"],
  freshnessIndex: 2,
  projectSummary: {
    acceptedSlices: 11,
    activeSlice: "L1GOV-SLICE-012",
    blockedItems: 0
  },
  modules: {
    mission_control: {
      title: "Mission Control",
      summary: "Projection freshness."
    },
    standardization: {
      title: "Standardization",
      summary: "Profiles and policy references shown for UX inspection."
    },
    monitor_hitl: {
      title: "Monitor/HITL",
      summary: "Review task and decision state shown without local approval authority."
    },
    delivery_feedback: {
      title: "Delivery Feedback",
      summary: "Feedback metric and triage candidates visible for review."
    },
    notes_evidence: {
      title: "Notes Evidence",
      summary: "UX direction and render evidence references shown as evidence only."
    }
  },
  workspaces: [
    { id: "workspace:4.21", label: "4.21 Layer 1 Governance", freshness: "current" },
    { id: "workspace:4.21-review", label: "4.21 Review Evidence", freshness: "stale" },
    { id: "workspace:4.21-parked", label: "Parked desktop review candidate", freshness: "blocked" }
  ],
  notes: [
    "PR #20 is draft/reference only.",
    "Slice 010 contracts define view-model boundaries.",
    "Slice 011 fixtures prove cross-component composition.",
    "Desktop app is non-authoritative."
  ]
};

const $ = (id) => document.getElementById(id);

function render() {
  $("workspace-name").textContent = state.workspaceName;
  $("accepted-slices").textContent = state.projectSummary.acceptedSlices;
  $("active-slice").textContent = state.projectSummary.activeSlice;
  $("blocked-items").textContent = state.projectSummary.blockedItems;
  $("freshness-chip").textContent = state.freshness;
  $("freshness-chip").className = `chip ${state.freshness}`;
  $("freshness-state").textContent = state.freshness;
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
        state.freshness = workspace.freshness;
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
  state.freshness = state.freshnessCycle[state.freshnessIndex];
  $("stale-copy").textContent = `Projection display state is ${state.freshness}. No canonical mutation.`;
  render();
}

function renderFutureIntegrationBoundary() {
  $("future-boundary").textContent = "disabled future boundary; deterministic fixture display only";
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

bindEvents();
render();

window.slice012DesktopSurface = {
  openWorkspacePicker,
  selectModule,
  showCommandDraftPreview,
  showServiceRejection,
  showNoGoBlock,
  cycleStaleRefresh,
  renderFutureIntegrationBoundary
};
