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
  const agents = fixture.agents ?? [];
  const runtimeWorktrees = fixture.runtime_worktrees ?? [];
  const evidenceRuns = fixture.evidence_runs ?? [];
  const prStack = fixture.pr_stack ?? [];
  const inboxAttention = fixture.inbox_attention ?? [];
  const settingsBoundaries = fixture.settings_boundaries ?? [];
  const agentDefinitions = fixture.agent_definitions ?? [];
  const runtimeProviders = fixture.runtime_providers ?? [];
  const runtimeInstances = fixture.runtime_instances ?? [];
  const runSessions = fixture.run_sessions ?? [];
  const commandDrafts = fixture.command_drafts ?? [];
  const dispatchCandidates = fixture.dispatch_candidate_projection ?? [];
  const handoffPreviews = fixture.handoff_preview ?? [];
  const workItemsById = byId(workItems, "internal_id");
  const selectedWorkItemId = workItemsById[fixture.selected_work_item_id]
    ? fixture.selected_work_item_id
    : workItems[0]?.internal_id;
  const selectedCommandDraftId = commandDrafts.find((draft) => draft.work_item_id === selectedWorkItemId)?.draft_id;

  return {
    fixture,
    activeViewId: REQUIRED_VIEW_IDS[0],
    selectedWorkItemId,
    views,
    viewsById: byId(views),
    workItems,
    workItemsById,
    agents,
    agentsByRole: byId(agents, "role_id"),
    runtimeWorktrees,
    runtimeWorktreesById: byId(runtimeWorktrees, "internal_id"),
    evidenceRuns,
    evidenceRunsById: byId(evidenceRuns, "internal_id"),
    prStack,
    prStackById: byId(prStack, "internal_id"),
    ownerUatDecision: fixture.owner_uat_decision,
    closeoutRecommendation: fixture.closeout_recommendation,
    inboxAttention,
    inboxAttentionById: byId(inboxAttention),
    settingsBoundaries,
    settingsBoundariesById: byId(settingsBoundaries),
    agentDefinitions,
    agentDefinitionsById: byId(agentDefinitions, "agent_id"),
    runtimeProviders,
    runtimeProvidersById: byId(runtimeProviders, "provider_id"),
    runtimeInstances,
    runtimeInstancesById: byId(runtimeInstances, "runtime_instance_id"),
    runSessions,
    runSessionsById: byId(runSessions, "run_session_id"),
    commandDrafts,
    commandDraftsById: byId(commandDrafts, "draft_id"),
    dispatchCandidates,
    dispatchCandidatesById: byId(dispatchCandidates, "candidate_id"),
    handoffPreviews,
    handoffPreviewsById: byId(handoffPreviews, "preview_id"),
    draftActionNotice: "Select a draft operation.",
    selectedCommandDraftId
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
  renderCommandDrafts();
}


function renderRecordCards(records, titleKey, linesForRecord, className) {
  return records.map((record) => {
    const card = document.createElement("article");
    const heading = document.createElement("h3");
    card.className = `panel ${className}`;
    heading.textContent = record[titleKey];
    card.append(heading);
    for (const line of linesForRecord(record)) {
      const paragraph = document.createElement("p");
      paragraph.textContent = line;
      card.append(paragraph);
    }
    return card;
  });
}

function renderDraftActionNotice() {
  const notice = $("command-draft-action-notice");
  if (!notice) return;
  notice.textContent = state.draftActionNotice || "Select a draft operation.";
}

function renderUnavailableProjection(targetId, titleText, message) {
  const title = document.createElement("h3");
  const detail = document.createElement("p");
  title.textContent = titleText;
  detail.textContent = message;
  $(targetId).replaceChildren(title, detail);
}

function renderCommandDrafts() {
  const itemDrafts = state.commandDrafts.filter((draft) => draft.work_item_id === state.selectedWorkItemId);
  if (!itemDrafts.some((draft) => draft.draft_id === state.selectedCommandDraftId)) {
    state.selectedCommandDraftId = itemDrafts[0]?.draft_id;
  }

  if (itemDrafts.length === 0) {
    const message = "No command draft is available for the selected work item.";
    state.draftActionNotice = message;
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = message;
    $("command-draft-list").replaceChildren(empty);
    updateDraftActionButtons(itemDrafts);
    renderDraftActionNotice();
    renderSelectedCommandDraftDetail(undefined);
    renderUnavailableProjection("dispatch-candidate-projection", "Dispatch Candidate Projection", message);
    renderUnavailableProjection("handoff-preview", "Handoff Preview", message);
    return;
  }

  const draftButtons = itemDrafts.map((draft) => {
    const button = document.createElement("button");
    const selected = draft.draft_id === state.selectedCommandDraftId;
    button.type = "button";
    button.className = `command-draft-card ${selected ? "selected" : ""}`;
    button.setAttribute("data-command-draft-id", draft.draft_id);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
    button.textContent = `${draft.label}: ${labelize(draft.command_type)} / ${draft.draft_only ? "draft-only" : "invalid"}`;
    button.addEventListener("click", () => selectCommandDraft(draft.draft_id));
    return button;
  });
  $("command-draft-list").replaceChildren(...draftButtons);

  updateDraftActionButtons(itemDrafts);
  renderDraftActionNotice();

  const selectedDraft = state.commandDraftsById[state.selectedCommandDraftId] ?? itemDrafts[0];
  renderSelectedCommandDraftDetail(selectedDraft);
  const candidate = state.dispatchCandidates.find(
    (candidate) => candidate.work_item_id === selectedDraft.work_item_id
  );
  const preview = selectedDraft ? state.handoffPreviewsById[selectedDraft.handoff_preview_ref] : undefined;
  const candidateTitle = document.createElement("h3");
  const candidateState = document.createElement("p");
  const candidateReason = document.createElement("p");
  candidateTitle.textContent = "Dispatch Candidate Projection";
  candidateState.textContent = candidate ? `Eligible: ${candidate.eligible ? "yes" : "no"}; draft only: ${(candidate.blocked_reasons ?? []).includes("draft_only") ? "yes" : "no"}.` : "No candidate projection.";
  candidateReason.textContent = candidate ? `Reason: ${(candidate.blocked_reasons ?? []).join("; ")}` : "No dispatch authority is inferred.";
  $("dispatch-candidate-projection").replaceChildren(candidateTitle, candidateState, candidateReason);

  const previewTitle = document.createElement("h3");
  const previewTarget = document.createElement("p");
  const previewWriteback = document.createElement("p");
  const previewValidation = document.createElement("ul");
  previewTitle.textContent = "Handoff Preview";
  previewTarget.textContent = preview ? `Target agent ${preview.target_agent_id}; runtime ${preview.target_runtime_instance_id}; task card ${preview.task_card_ref}.` : "No handoff preview selected.";
  previewWriteback.textContent = preview ? `Write-back: ${preview.write_back_location}` : "Write-back remains Planning callback only.";
  previewValidation.className = "compact-list";
  previewValidation.replaceChildren(...createTextList(preview?.validation_commands));
  $("handoff-preview").replaceChildren(previewTitle, previewTarget, previewWriteback, previewValidation);
}
function renderSelectedCommandDraftDetail(selectedDraft) {
  const title = document.createElement("h3");
  const status = document.createElement("p");
  const target = document.createElement("p");
  const approvalsTitle = document.createElement("strong");
  const approvals = document.createElement("ul");
  const blockedTitle = document.createElement("strong");
  const blocked = document.createElement("ul");
  const evidenceTitle = document.createElement("strong");
  const evidence = document.createElement("ul");

  title.textContent = "Selected Command Draft";
  if (!selectedDraft) {
    status.textContent = "No command draft is available for the selected work item.";
    $("selected-command-draft-detail").replaceChildren(title, status);
    return;
  }

  status.textContent = `Draft ${selectedDraft.draft_id}; command ${labelize(selectedDraft.command_type)}; draft_only ${selectedDraft.draft_only ? "true" : "false"}; non_authoritative ${selectedDraft.non_authoritative ? "true" : "false"}.`;
  target.textContent = `Target agent ${selectedDraft.target_agent_id}; target runtime ${selectedDraft.target_runtime_instance_id}; run session ${selectedDraft.run_session_id}.`;
  approvalsTitle.textContent = "Required approvals";
  blockedTitle.textContent = "Blocked authorities";
  evidenceTitle.textContent = "Evidence requirements";
  approvals.className = "compact-list";
  blocked.className = "compact-list";
  evidence.className = "compact-list";
  approvals.replaceChildren(...createTextList(selectedDraft.required_approvals.map(labelize)));
  blocked.replaceChildren(...createTextList(selectedDraft.blocked_authorities.map(labelize)));
  evidence.replaceChildren(...createTextList(selectedDraft.evidence_requirements.map(labelize)));

  $("selected-command-draft-detail").replaceChildren(
    title,
    status,
    target,
    approvalsTitle,
    approvals,
    blockedTitle,
    blocked,
    evidenceTitle,
    evidence
  );
}
function renderAgentsView() {
  const cards = Object.values(state.agentsByRole).map((agent) => {
    const card = document.createElement("article");
    const heading = document.createElement("h3");
    const assignment = document.createElement("p");
    const readiness = document.createElement("p");
    const note = document.createElement("p");
    const allowedTitle = document.createElement("strong");
    const allowed = document.createElement("ul");
    const forbiddenTitle = document.createElement("strong");
    const forbidden = document.createElement("ul");

    card.className = "panel agent-card";
    heading.textContent = agent.display_name;
    assignment.textContent = `Assignment: ${agent.current_assignment_id}; availability: ${labelize(agent.availability)}.`;
    readiness.textContent = `Readiness: ${labelize(agent.readiness_state)}.`;
    note.textContent = agent.authority_note;
    allowedTitle.textContent = "Allowed";
    forbiddenTitle.textContent = "Forbidden";
    allowed.className = "compact-list";
    forbidden.className = "compact-list";
    allowed.replaceChildren(...createTextList(agent.allowed_actions.map(labelize)));
    forbidden.replaceChildren(...createTextList(agent.forbidden_actions.map(labelize)));

    card.append(heading, assignment, readiness, note, allowedTitle, allowed, forbiddenTitle, forbidden);
    return card;
  });

  $("agent-team-list").replaceChildren(...cards);
  $("agent-definition-list").replaceChildren(...renderRecordCards(
    state.agentDefinitions,
    "display_name",
    (agent) => [
      `Agent ID: ${agent.agent_id}; role: ${labelize(agent.role)}.`,
      `Capability tags: ${(agent.capability_tags ?? []).map(labelize).join(", ")}.`,
      `Authority boundaries: ${(agent.authority_boundaries ?? []).join("; ")}.`
    ],
    "agent-definition-card"
  ));
}

function renderRuntimeWorktreesView() {
  const records = Object.values(state.runtimeWorktreesById).map((record) => {
    const card = document.createElement("article");
    const heading = document.createElement("h3");
    const mapping = document.createElement("p");
    const branch = document.createElement("p");
    const worktree = document.createElement("p");
    const stateLine = document.createElement("p");
    const authority = document.createElement("p");

    card.className = `panel runtime-card ${record.current_slice ? "current" : ""}`;
    heading.textContent = `${record.internal_id} ${record.current_slice ? "(current)" : ""}`;
    mapping.textContent = `GitHub PR: ${record.github_pr_label}; validation: ${labelize(record.validation_state)}.`;
    branch.textContent = `Branch: ${record.branch}; base: ${record.base_commit}; head: ${record.head_commit}.`;
    worktree.textContent = `Worktree: ${record.worktree}`;
    stateLine.textContent = `Cleanliness: ${labelize(record.cleanliness)}; safety: ${labelize(record.safety_state)}.`;
    authority.textContent = `Runtime: ${labelize(record.runtime_authorization_state)}; startup ${record.startup_allowed ? "allowed" : "blocked"}; dependency install ${record.dependency_install_allowed ? "allowed" : "blocked"}; broker/NATS mutation ${record.broker_mutation_allowed ? "allowed" : "blocked"}; dispatch ${record.live_dispatch_allowed ? "allowed" : "blocked"}; cleanup ${record.cleanup_allowed ? "allowed" : "blocked"}.`;

    card.append(heading, mapping, branch, worktree, stateLine, authority);
    return card;
  });

  $("runtime-worktree-list").replaceChildren(...records);
  $("runtime-provider-list").replaceChildren(...renderRecordCards(
    state.runtimeProviders,
    "display_name",
    (provider) => [
      `Provider: ${provider.provider_id}; family: ${provider.provider_family}.`,
      `Executable: ${provider.executable ? "yes" : "no"}; blocked reason: ${provider.blocked_reason}.`
    ],
    "runtime-provider-card"
  ));
  $("runtime-instance-list").replaceChildren(...renderRecordCards(
    state.runtimeInstances,
    "runtime_instance_id",
    (runtime) => [
      `Provider: ${runtime.provider_id}; branch: ${runtime.branch}.`,
      `Worktree: ${runtime.worktree_path}.`,
      `Startup ${runtime.startup_allowed ? "allowed" : "blocked"}; dependency install ${runtime.dependency_install_allowed ? "allowed" : "blocked"}; broker mutation ${runtime.broker_mutation_allowed ? "allowed" : "blocked"}; dispatch ${runtime.live_dispatch_allowed ? "allowed" : "blocked"}.`
    ],
    "runtime-instance-card"
  ));
  $("run-session-list").replaceChildren(...renderRecordCards(
    state.runSessions,
    "run_session_id",
    (session) => [
      `Work item: ${session.work_item_id}; agent: ${session.agent_id}; runtime: ${session.runtime_instance_id}.`,
      `Session state: ${labelize(session.session_state)}; execution state: ${labelize(session.execution_state)}.`,
      `Evidence ref: ${session.evidence_ref}.`
    ],
    "run-session-card"
  ));
  renderNatsBoundary();
}

function renderNatsBoundary() {
  const boundary = state.fixture.nats_boundary;
  const local = document.createElement("p");
  const live = document.createElement("p");
  local.textContent = `Local-test NATS: ${boundary.local_test.nats}; monitor: ${boundary.local_test.monitor}; use ${boundary.local_test.use_allowed ? "allowed" : "blocked"}; mutation ${boundary.local_test.mutation_allowed ? "allowed" : "blocked"}. ${boundary.local_test.note}`;
  live.textContent = `OpenClaw live NATS: ${boundary.openclaw_live.nats}; use ${boundary.openclaw_live.use_allowed ? "allowed" : "blocked"}; mutation ${boundary.openclaw_live.mutation_allowed ? "allowed" : "blocked"}. ${boundary.openclaw_live.note}`;
  $("nats-boundary").replaceChildren(local, live);
}

function renderEvidenceRunsView() {
  const cards = state.evidenceRuns.map((record) => {
    const card = document.createElement("article");
    const heading = document.createElement("h3");
    const command = document.createElement("p");
    const evidence = document.createElement("p");
    const summary = document.createElement("p");
    const reason = document.createElement("p");

    card.className = "panel evidence-card";
    heading.textContent = `${record.internal_id} ${record.github_pr_label || "TBD"}`;
    command.textContent = `Command: ${record.command}; status: ${labelize(record.status)}; exit: ${record.exit_code ?? "n/a"}.`;
    evidence.textContent = `Evidence: ${labelize(record.evidence_state)}; ref: ${record.evidence_ref || "scope exemption only"}.`;
    summary.textContent = record.summary;
    reason.textContent = record.not_run_reason ? `Not-run reason: ${record.not_run_reason}` : "Executed validation record.";
    card.append(heading, command, evidence, summary, reason);
    return card;
  });

  $("evidence-run-list").replaceChildren(...cards);
}

function renderPrUatCloseoutView() {
  const stackCards = state.prStack.map((record) => {
    const card = document.createElement("article");
    const heading = document.createElement("h3");
    const status = document.createElement("p");
    const gate = document.createElement("p");

    card.className = `panel pr-card ${record.baseline_role === "superseded_prototype" ? "superseded" : ""}`;
    heading.textContent = `${record.internal_id} -> ${record.github_pr_label || "TBD"}`;
    status.textContent = `Status: ${labelize(record.status)}; role: ${labelize(record.baseline_role)}.`;
    gate.textContent = `Evidence gate: ${labelize(record.evidence_gate)}.`;
    card.append(heading, status, gate);
    return card;
  });

  const owner = state.ownerUatDecision;
  const recommendation = state.closeoutRecommendation;
  const ownerTitle = document.createElement("h3");
  const ownerState = document.createElement("p");
  const ownerRef = document.createElement("p");
  const recommendationTitle = document.createElement("h3");
  const recommendationState = document.createElement("p");
  const recommendationBlockers = document.createElement("ul");

  ownerTitle.textContent = "Owner UAT Decision";
  ownerState.textContent = `State: ${labelize(owner.state)}; manual only: ${owner.manual_only ? "yes" : "no"}; no automated acceptance.`;
  ownerRef.textContent = `Decision ref: ${owner.decision_ref || "not recorded"}. ${owner.notes}`;
  recommendationTitle.textContent = "Closeout Recommendation";
  recommendationState.textContent = `State: ${labelize(recommendation.state)}; merge ready: ${recommendation.merge_ready ? "yes" : "no"}; production ready: ${recommendation.production_ready ? "yes" : "no"}; live ready: ${recommendation.live_ready ? "yes" : "no"}.`;
  recommendationBlockers.className = "compact-list";
  recommendationBlockers.replaceChildren(...createTextList(recommendation.blockers));

  $("pr-stack-list").replaceChildren(...stackCards);
  $("owner-uat-decision").replaceChildren(ownerTitle, ownerState, ownerRef);
  $("closeout-recommendation").replaceChildren(recommendationTitle, recommendationState, recommendationBlockers);
}

function renderInboxAttentionView() {
  const cards = state.inboxAttention.map((item) => {
    const card = document.createElement("article");
    const heading = document.createElement("h3");
    const stateLine = document.createElement("p");
    const detail = document.createElement("p");

    card.className = `panel attention-card ${item.state}`;
    heading.textContent = item.label;
    stateLine.textContent = `State: ${labelize(item.state)}; read only: ${item.read_only ? "yes" : "no"}.`;
    detail.textContent = item.detail;
    card.append(heading, stateLine, detail);
    return card;
  });

  $("attention-list").replaceChildren(...cards);
}

function renderSettingsBoundariesView() {
  const cards = state.settingsBoundaries.map((boundary) => {
    const card = document.createElement("article");
    const heading = document.createElement("h3");
    const summary = document.createElement("p");
    const allowedTitle = document.createElement("strong");
    const allowed = document.createElement("ul");
    const blockedTitle = document.createElement("strong");
    const blocked = document.createElement("ul");

    card.className = "panel boundary-card";
    heading.textContent = labelize(boundary.id);
    summary.textContent = boundary.summary;
    allowedTitle.textContent = "Allowed";
    blockedTitle.textContent = "Blocked";
    allowed.className = "compact-list";
    blocked.className = "compact-list";
    allowed.replaceChildren(...createTextList(boundary.allowed));
    blocked.replaceChildren(...createTextList(boundary.blocked));
    card.append(heading, summary, allowedTitle, allowed, blockedTitle, blocked);
    return card;
  });

  $("boundary-list").replaceChildren(...cards);
}
function showRegion(regionName) {
  $("work-items-region").hidden = regionName !== "work_items";
  $("work-item-detail-region").hidden = regionName !== "work_item_detail";
  $("agents-region").hidden = regionName !== "agents";
  $("runtime-worktrees-region").hidden = regionName !== "runtime_worktrees";
  $("evidence-runs-region").hidden = regionName !== "evidence_runs";
  $("pr-uat-closeout-region").hidden = regionName !== "pr_uat_closeout";
  $("inbox-attention-region").hidden = regionName !== "inbox_attention";
  $("settings-boundaries-region").hidden = regionName !== "settings_boundaries";
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
  if (state.activeViewId === "agents") {
    showRegion("agents");
    renderAgentsView();
    return;
  }
  if (state.activeViewId === "runtime_worktrees") {
    showRegion("runtime_worktrees");
    renderRuntimeWorktreesView();
    return;
  }
  if (state.activeViewId === "evidence_runs") {
    showRegion("evidence_runs");
    renderEvidenceRunsView();
    return;
  }
  if (state.activeViewId === "pr_uat_closeout") {
    showRegion("pr_uat_closeout");
    renderPrUatCloseoutView();
    return;
  }
  if (state.activeViewId === "inbox_attention") {
    showRegion("inbox_attention");
    renderInboxAttentionView();
    return;
  }
  if (state.activeViewId === "settings_boundaries") {
    showRegion("settings_boundaries");
    renderSettingsBoundariesView();
    return;
  }

  showRegion("placeholder");
  $("view-owner").textContent = view.implementation_pr;
  $("view-safety").textContent = labelize(view.safety_state);
  $("view-boundary").textContent = `${view.title} remains ${labelize(view.readiness_state)} in EDC-PR-010. Full workflow content belongs to ${view.implementation_pr}.`;
}

function selectWorkItem(workItemId) {
  if (!state.workItemsById[workItemId]) return;
  state.selectedWorkItemId = workItemId;
  state.draftActionNotice = "Select a draft operation.";
  renderWorkItemsBoard();
  renderWorkItemDetail();
}


function updateDraftActionButtons(itemDrafts = state.commandDrafts.filter((draft) => draft.work_item_id === state.selectedWorkItemId)) {
  const selectedDraft = state.commandDraftsById[state.selectedCommandDraftId];
  const availableCommandTypes = new Set(itemDrafts.map((draft) => draft.command_type));
  document.querySelectorAll(".draft-action[data-command-type]").forEach((button) => {
    const selected = button.dataset.commandType === selectedDraft?.command_type;
    button.disabled = itemDrafts.length === 0;
    button.classList.toggle("selected", selected);
    button.classList.toggle("unavailable", itemDrafts.length === 0);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
    button.setAttribute("aria-disabled", availableCommandTypes.has(button.dataset.commandType) ? "false" : "true");
  });
}

function selectCommandDraftByType(commandType) {
  const draft = state.commandDrafts.find(
    (candidate) => candidate.work_item_id === state.selectedWorkItemId && candidate.command_type === commandType
  );
  if (!draft) {
    state.draftActionNotice = "No command draft is available for the selected work item.";
    renderCommandDrafts();
    return;
  }
  selectCommandDraft(draft.draft_id, `Selected: ${draft.label}`);
}
function selectCommandDraft(draftId, notice) {
  const draft = state.commandDraftsById[draftId];
  if (!draft || draft.work_item_id !== state.selectedWorkItemId) {
    state.draftActionNotice = "No command draft is available for the selected work item.";
    renderCommandDrafts();
    return;
  }
  state.selectedCommandDraftId = draftId;
  state.draftActionNotice = notice ?? `Selected: ${draft.label}`;
  renderCommandDrafts();
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
  document.querySelectorAll(".draft-action[data-command-type]").forEach((button) => {
    button.addEventListener("click", () => selectCommandDraftByType(button.dataset.commandType));
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
  renderAgentsView,
  renderRuntimeWorktreesView,
  renderEvidenceRunsView,
  renderPrUatCloseoutView,
  renderInboxAttentionView,
  renderSettingsBoundariesView,
  renderCommandDrafts,
  renderWorkItemDetail,
  renderWorkItemsBoard,
  selectView,
  selectWorkItem,
  selectCommandDraft,
  selectCommandDraftByType
};
