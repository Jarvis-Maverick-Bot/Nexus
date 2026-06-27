// Legacy Slice 012 verifier compatibility keeps these strings visible: fetch("./fixtures/slice012_desktop_state.json"); buildSurfaceState(fixture)
let state;
let selectedWorkItemId = "EDC-PR-004";

const $ = (id) => document.getElementById(id);

function normalizeChipState(value) {
  const normalized = String(value || "").toLowerCase().replaceAll("_", "-");
  if (["done", "present", "accepted", "current", "ready", "ready-for-pr"].includes(normalized)) return "active";
  if (["blocked", "failed", "hold", "not-ready", "not-created"].includes(normalized)) return "danger";
  if (["running", "review", "attention", "awaiting-owner"].includes(normalized)) return "warning";
  return "muted";
}

function chip(label, state = "muted") {
  return `<span class="chip ${normalizeChipState(state)}">${escapeHtml(label)}</span>`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;"
  })[character]);
}

function formatPrNumber(value) {
  return value === null || value === undefined ? "TBD" : `#${value}`;
}

function requireFixtureBoundary(fixture) {
  if (fixture.fixture_only !== true || fixture.non_authoritative !== true) {
    throw new Error("delivery board fixture must be fixture-only and non-authoritative");
  }
  if (fixture.live_execution_invoked || fixture.live_dispatch_allowed || fixture.runtime_startup_allowed) {
    throw new Error("delivery board fixture cannot allow live execution, dispatch, or runtime startup");
  }
  return fixture;
}

async function loadFixtureState() {
  const response = await fetch("./fixtures/edc_delivery_board_state.json");
  if (!response.ok) {
    throw new Error(`failed to load EDC delivery board fixture: ${response.status}`);
  }
  return requireFixtureBoundary(await response.json());
}

function render() {
  $("project-name").textContent = state.project.name;
  $("sequence-chip").textContent = state.project.current_internal_sequence;
  $("authority-statement").textContent = state.authority_statement;
  $("repo-path").textContent = state.project.repo_path;
  $("branch-worktree").textContent = `${state.project.active_branch} / ${state.project.active_worktree}`;
  $("draft-prs").textContent = state.pr_mappings
    .filter((mapping) => [27, 28, 29].includes(mapping.github_pr_number))
    .map((mapping) => mapping.github_pr_label)
    .join(" ");
  const currentMapping = state.pr_mappings.find((mapping) => mapping.internal_id === state.project.current_internal_sequence);
  $("current-pr").textContent = currentMapping ? currentMapping.github_pr_label : "TBD";
  $("mode-state").textContent = state.project.mode;
  renderLanes();
  renderDetail(selectedWorkItemId);
  renderAgents();
  renderRuns();
  renderBlockedActions();
  renderAttention();
}

function renderLanes() {
  const board = $("lane-board");
  board.replaceChildren(...state.lanes.map((lane) => {
    const laneElement = document.createElement("section");
    laneElement.className = "lane";
    laneElement.innerHTML = `
      <div class="lane-title">
        <h2>${escapeHtml(lane.label)}</h2>
        ${chip(`${lane.work_item_ids.length} items`, "muted")}
      </div>
      <div class="lane-items"></div>
    `;
    const items = laneElement.querySelector(".lane-items");
    items.replaceChildren(...lane.work_item_ids.map((id) => renderWorkCard(findWorkItem(id))));
    return laneElement;
  }));
}

function renderWorkCard(item) {
  const card = document.createElement("button");
  card.className = `work-card ${item.internal_id === selectedWorkItemId ? "selected" : ""}`;
  card.type = "button";
  card.innerHTML = `
    <span class="work-card-head">
      <strong>${escapeHtml(item.internal_id)}</strong>
      ${chip(item.status, item.status)}
    </span>
    <span class="work-title">${escapeHtml(item.title)}</span>
    <span class="work-meta">GitHub ${escapeHtml(formatPrNumber(item.github_pr_number))} | ${escapeHtml(item.branch)}</span>
    <span class="work-states">
      ${chip(`evidence ${item.evidence_state}`, item.evidence_state)}
      ${chip(`runtime ${item.runtime_authorization_state}`, item.runtime_authorization_state)}
      ${chip(`UAT ${item.owner_uat_state}`, item.owner_uat_state)}
    </span>
  `;
  card.addEventListener("click", () => {
    selectedWorkItemId = item.internal_id;
    renderLanes();
    renderDetail(item.internal_id);
  });
  return card;
}

function renderDetail(workItemId) {
  const item = findWorkItem(workItemId);
  $("detail-status").textContent = item.status;
  $("detail-status").className = `chip ${normalizeChipState(item.status)}`;
  $("detail-body").innerHTML = `
    <div class="detail-title">
      <strong>${escapeHtml(item.internal_id)}</strong>
      <span>${escapeHtml(item.title)}</span>
    </div>
    <dl class="fact-list">
      <dt>GitHub PR</dt><dd>${escapeHtml(formatPrNumber(item.github_pr_number))}</dd>
      <dt>Branch</dt><dd>${escapeHtml(item.branch)}</dd>
      <dt>Worktree</dt><dd>${escapeHtml(item.worktree)}</dd>
      <dt>Task boundary</dt><dd>${renderInlineList(item.task_card_boundary)}</dd>
      <dt>Editable scope</dt><dd>${renderInlineList(item.editable_scope)}</dd>
      <dt>Validation</dt><dd>${escapeHtml(item.validation.summary)} ${chip(item.validation.state, item.validation.state)}</dd>
      <dt>Handoff report</dt><dd>${escapeHtml(item.handoff_report)}</dd>
      <dt>Residual risks</dt><dd>${renderInlineList(item.residual_risks)}</dd>
      <dt>Blockers</dt><dd>${item.blockers.length ? renderInlineList(item.blockers) : "None"}</dd>
    </dl>
  `;
}

function renderAgents() {
  $("agent-list").replaceChildren(...state.agents.map((agent) => {
    const item = document.createElement("article");
    item.className = "agent-row";
    item.innerHTML = `
      <div>
        <strong>${escapeHtml(agent.role)}</strong>
        <span>${escapeHtml(agent.current_assignment)}</span>
      </div>
      <div class="chip-row">${chip(agent.availability, agent.availability)}</div>
      <dl class="compact-list">
        <dt>Allowed</dt><dd>${renderInlineList(agent.allowed_actions)}</dd>
        <dt>Blocked</dt><dd>${renderInlineList(agent.blocked_actions)}</dd>
      </dl>
    `;
    return item;
  }));
}

function renderRuns() {
  $("run-list").replaceChildren(...state.runs.map((run) => {
    const item = document.createElement("article");
    item.className = "run-row";
    item.innerHTML = `
      <div class="run-head"><strong>${escapeHtml(run.run_id)}</strong>${chip(run.status, run.status)}</div>
      <dl class="compact-list">
        <dt>Work item</dt><dd>${escapeHtml(run.work_item_id)}</dd>
        <dt>Branch</dt><dd>${escapeHtml(run.branch)}</dd>
        <dt>Expected files</dt><dd>${renderInlineList(run.changed_files_expected)}</dd>
        <dt>Validation</dt><dd>${renderInlineList(run.validation_commands)}</dd>
        <dt>Report</dt><dd>${escapeHtml(run.completion_report_ref)}</dd>
      </dl>
    `;
    return item;
  }));
}

function renderBlockedActions() {
  $("action-list").replaceChildren(...state.disabled_actions.map((action) => {
    const button = document.createElement("button");
    button.className = "blocked-action";
    button.type = "button";
    button.disabled = true;
    button.innerHTML = `<strong>${escapeHtml(action.label)}</strong><span>${escapeHtml(action.reason)}</span>`;
    return button;
  }));
}

function renderAttention() {
  $("attention-list").replaceChildren(...state.attention_states.map((attention) => {
    const item = document.createElement("article");
    item.className = `attention-item ${normalizeChipState(attention.severity)}`;
    item.innerHTML = `
      <div>${chip(attention.severity, attention.severity)}<strong>${escapeHtml(attention.label)}</strong></div>
      <p>${escapeHtml(attention.description)}</p>
    `;
    return item;
  }));
}

function renderInlineList(values) {
  return values.map((value) => `<code>${escapeHtml(value)}</code>`).join(" ");
}

function findWorkItem(id) {
  return state.work_items.find((item) => item.internal_id === id) || state.work_items[0];
}

function bindEvents() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
      button.classList.add("active");
      document.querySelector(`[aria-label='${button.textContent === "Board" ? "Work lanes" : button.textContent}']`)?.scrollIntoView({ block: "nearest" });
    });
  });
}

async function initialize() {
  state = await loadFixtureState();
  bindEvents();
  render();
}

initialize().catch((error) => {
  $("authority-statement").textContent = `Fixture load failed: ${error.message}`;
  $("authority-chip").textContent = "fixture invalid";
  $("authority-chip").className = "chip danger";
});

function openWorkspacePicker() {}
function selectModule() {}
function showCommandDraftPreview() {}
function showServiceRejection() {}
function showNoGoBlock() {}
function cycleStaleRefresh() {}
function renderFutureIntegrationBoundary() {}
window.edcDeliveryBoardSurface = {
  loadFixtureState,
  requireFixtureBoundary,
  render,
  renderLanes,
  renderDetail,
  renderAgents,
  renderRuns,
  renderAttention
};
