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

function byId(records, key = "id") {
  return Object.fromEntries(records.map((record) => [record[key], record]));
}

function labelize(value) {
  return String(value ?? "").replaceAll("_", " ");
}

function createTextList(items) {
  return (items?.length ? items : ["None recorded"]).map((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    return item;
  });
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

  const workItems = fixture.work_items ?? [];
  const workItemsById = byId(workItems, "internal_id");
  const selectedWorkItemId = workItemsById[fixture.selected_work_item_id]
    ? fixture.selected_work_item_id
    : workItems[0]?.internal_id;

  return {
    fixture,
    activeViewId: REQUIRED_VIEW_IDS[0],
    selectedWorkItemId,
    views,
    viewsById: byId(views),
    workItems,
    workItemsById
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
      const id = document.createElement("span");
      const github = document.createElement("strong");
      const role = document.createElement("em");
      id.textContent = mapping.internal_id;
      github.textContent = mapping.github_pr_label || "TBD";
      role.textContent = mapping.baseline_role;
      item.append(id, github, role);
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
      const label = document.createElement("strong");
      const detail = document.createElement("span");
      label.textContent = boundary.label;
      detail.textContent = boundary.detail;
      item.append(label, detail);
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

function renderWorkItemsBoard() {
  const lanes = [
    ["draft_pr_open", "Draft PR open"],
    ["in_progress", "In progress"],
    ["planned", "Planned"]
  ];

  const laneNodes = lanes.map(([laneId, label]) => {
    const lane = document.createElement("section");
    lane.className = "work-lane";
    const heading = document.createElement("h3");
    heading.textContent = label;
    const list = document.createElement("div");
    list.className = "work-card-list";

    const items = state.workItems.filter((item) => item.lane === laneId);
    for (const workItem of items) {
      const button = document.createElement("button");
      const isSelected = workItem.internal_id === state.selectedWorkItemId;
      const topRow = document.createElement("span");
      const internalId = document.createElement("strong");
      const githubLabel = document.createElement("em");
      const title = document.createElement("span");
      const stateMeta = document.createElement("span");
      const branchMeta = document.createElement("span");

      button.type = "button";
      button.className = `work-card ${isSelected ? "selected" : ""}`;
      button.setAttribute("data-work-item-id", workItem.internal_id);
      button.setAttribute("aria-pressed", isSelected ? "true" : "false");

      topRow.className = "work-card-top";
      internalId.textContent = workItem.internal_id;
      githubLabel.textContent = workItem.github_pr_label;
      topRow.append(internalId, githubLabel);

      title.className = "work-card-title";
      title.textContent = workItem.title;

      stateMeta.className = "work-card-meta";
      stateMeta.textContent = `${labelize(workItem.status)} / ${labelize(workItem.readiness_state)} / ${labelize(workItem.evidence_state)}`;

      branchMeta.className = "work-card-meta";
      branchMeta.textContent = workItem.branch;

      button.append(topRow, title, stateMeta, branchMeta);
      button.addEventListener("click", () => selectWorkItem(workItem.internal_id));
      list.append(button);
    }

    lane.append(heading, list);
    return lane;
  });

  $("work-item-board").replaceChildren(...laneNodes);
}
function renderWorkItemDetail() {
  const item = state.workItemsById[state.selectedWorkItemId] ?? state.workItems[0];
  if (!item) return;

  $("detail-internal-id").textContent = item.internal_id;
  $("detail-title").textContent = item.title;
  $("detail-summary").textContent = `${labelize(item.status)} / ${labelize(item.readiness_state)} / owner UAT ${labelize(item.owner_uat_state)}`;
  $("detail-pr-mapping").textContent = `${item.internal_id} -> ${item.github_pr_label || "TBD"}`;
  $("detail-goal").textContent = item.task_card.goal;
  $("detail-scope").textContent = item.task_card.scope_summary;
  $("detail-non-goals").textContent = item.task_card.non_goals;
  $("detail-branch").textContent = `Branch: ${item.branch}`;
  $("detail-worktree").textContent = `Worktree: ${item.worktree}`;
  $("detail-evidence").textContent = `Evidence: ${labelize(item.evidence_state)}; runtime authorization: ${labelize(item.runtime_authorization_state)}.`;
  $("detail-uat").textContent = `Owner UAT: ${labelize(item.owner_uat_state)}; no owner acceptance recorded.`;
  $("detail-writeback").textContent = item.task_card.write_back_location;
  $("detail-boundaries").replaceChildren(...createTextList(item.task_card.editable_boundary));
  $("detail-validation").replaceChildren(...createTextList(item.task_card.validation_commands));
  $("detail-risk-list").replaceChildren(...createTextList(item.residual_risks));
  $("detail-blocker-list").replaceChildren(...createTextList(item.blockers));
}

function showRegion(regionName) {
  $("work-items-region").hidden = regionName !== "work_items";
  $("work-item-detail-region").hidden = regionName !== "work_item_detail";
  $("placeholder-region").hidden = regionName !== "placeholder";
}

function renderActiveView() {
  const view = state.viewsById[state.activeViewId];
  $("view-kicker").textContent = view.implementation_pr;
  $("view-title").textContent = view.title;
  $("view-purpose").textContent = view.purpose;
  $("view-readiness").textContent = labelize(view.readiness_state);

  if (["work_items", "work_item_detail"].includes(state.activeViewId)) {
    showRegion(state.activeViewId);
    renderWorkItemsBoard();
    renderWorkItemDetail();
    return;
  }

  showRegion("placeholder");
  $("view-owner").textContent = view.implementation_pr;
  $("view-safety").textContent = labelize(view.safety_state);
  $("view-boundary").textContent = `${view.title} remains ${labelize(view.readiness_state)} in EDC-PR-008. Full workflow content belongs to ${view.implementation_pr}.`;
}

function selectWorkItem(workItemId) {
  if (!state.workItemsById[workItemId]) return;
  state.selectedWorkItemId = workItemId;
  renderWorkItemsBoard();
  renderWorkItemDetail();
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
  renderWorkItemDetail,
  renderWorkItemsBoard,
  selectView,
  selectWorkItem
};
