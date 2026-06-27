let state;

const REQUIRED_VIEW_IDS = [
  "work_items",
  "work_item_detail",
  "agents",
  "runtime_worktrees",
  "evidence_runs",
  "pr_uat_closeout",
  "inbox_attention",
  "settings_boundaries"
];

const REQUIRED_SAFETY_IDS = [
  "runtime_hold",
  "dependency_install_not_authorized",
  "broker_nats_mutation_blocked",
  "live_dispatch_blocked",
  "owner_uat_after_edc_pr_010"
];

const $ = (id) => document.getElementById(id);

function normalizeViewId(viewId) {
  return REQUIRED_VIEW_IDS.includes(viewId) ? viewId : REQUIRED_VIEW_IDS[0];
}

function byId(records) {
  return Object.fromEntries(records.map((record) => [record.id, record]));
}

function buildShellState(fixture) {
  const views = fixture.views ?? [];
  const viewIds = views.map((view) => view.id);
  for (const required of REQUIRED_VIEW_IDS) {
    if (!viewIds.includes(required)) {
      throw new Error(`missing workbench view: ${required}`);
    }
  }

  for (const required of REQUIRED_SAFETY_IDS) {
    if (!(fixture.safety_boundaries ?? []).some((item) => item.id === required)) {
      throw new Error(`missing safety boundary: ${required}`);
    }
  }

  return {
    fixture,
    activeViewId: REQUIRED_VIEW_IDS[0],
    views,
    viewsById: byId(views)
  };
}

async function loadFixtureState() {
  const response = await fetch("./fixtures/edc_workbench_shell_state.json");
  if (!response.ok) {
    throw new Error(`failed to load deterministic fixture: ${response.status}`);
  }
  const fixture = await response.json();
  if (fixture.surface !== "Nexus Agent Coding Team Workbench" || fixture.live_execution_invoked !== false) {
    throw new Error("invalid Workbench shell fixture boundary");
  }
  return buildShellState(fixture);
}

function renderAuthorityChips() {
  const chipRoot = $("authority-chips");
  chipRoot.replaceChildren(
    ...state.fixture.authority_chips.map((chip) => {
      const item = document.createElement("span");
      item.className = `chip ${chip.state}`;
      item.textContent = chip.label;
      return item;
    })
  );
}

function renderGlobalContext() {
  const project = state.fixture.project;
  $("project-name").textContent = project.name;
  $("project-path").textContent = project.repo_path;
  $("branch-context").textContent = project.active_branch;
  $("worktree-context").textContent = project.active_worktree;
  $("internal-sequence").textContent = project.current_internal_sequence;
  $("fixture-state").textContent = state.fixture.fixture_only ? "fixture-only" : "invalid";
  $("authority-state").textContent = state.fixture.non_authoritative ? "non-authoritative" : "invalid";
  $("runtime-state").textContent = state.fixture.runtime_startup_allowed ? "invalid" : "runtime hold";
  $("uat-state").textContent = `after ${state.fixture.owner_uat_after}`;
}

function renderPrMappings() {
  $("pr-mapping-list").replaceChildren(
    ...state.fixture.pr_mappings.map((mapping) => {
      const item = document.createElement("li");
      const githubLabel = mapping.github_pr_label || "TBD";
      item.innerHTML = `<span>${mapping.internal_id}</span><strong>${githubLabel}</strong><em>${mapping.baseline_role}</em>`;
      if (mapping.baseline_role === "superseded_prototype") {
        item.classList.add("superseded");
      }
      return item;
    })
  );
}

function renderSafetyBoundaries() {
  $("safety-list").replaceChildren(
    ...state.fixture.safety_boundaries.map((boundary) => {
      const item = document.createElement("li");
      item.innerHTML = `<strong>${boundary.label}</strong><span>${boundary.detail}</span>`;
      return item;
    })
  );
}

function renderBaseDecision() {
  const decision = state.fixture.base_decision;
  $("base-decision").textContent = `Continue from ${decision.continue_from}; foundation lineage ${decision.foundation_lineage.join(" -> ")}.`;
  $("superseded-note").textContent = `${decision.bypass.join(" and ")} are reference-only superseded prototypes.`;
}

function renderNavigation() {
  document.querySelectorAll(".nav-button").forEach((button) => {
    const isActive = button.dataset.viewId === state.activeViewId;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-current", isActive ? "page" : "false");
  });
}

function renderActiveView() {
  const view = state.viewsById[state.activeViewId];
  $("view-kicker").textContent = view.implementation_pr;
  $("view-title").textContent = view.title;
  $("view-purpose").textContent = view.purpose;
  $("view-owner").textContent = view.implementation_pr;
  $("view-safety").textContent = view.safety_state.replaceAll("_", " ");
  $("view-readiness").textContent = view.readiness_state.replaceAll("_", " ");
  $("view-boundary").textContent = `${view.title} is ${view.readiness_state.replaceAll("_", " ")} in EDC-PR-007. Full workflow content belongs to ${view.implementation_pr}.`;
}

function selectView(viewId) {
  state.activeViewId = normalizeViewId(viewId);
  renderNavigation();
  renderActiveView();
}

function bindEvents() {
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", () => selectView(button.dataset.viewId));
  });
}

function render() {
  renderAuthorityChips();
  renderGlobalContext();
  renderPrMappings();
  renderSafetyBoundaries();
  renderBaseDecision();
  renderNavigation();
  renderActiveView();
}

async function initialize() {
  state = await loadFixtureState();
  bindEvents();
  render();
}

initialize().catch((error) => {
  $("view-title").textContent = "Workbench fixture load failed";
  $("view-purpose").textContent = error.message;
  $("view-readiness").textContent = "blocked";
});

window.edcWorkbenchShellSurface = {
  buildShellState,
  loadFixtureState,
  normalizeViewId,
  renderActiveView,
  renderNavigation,
  selectView
};
