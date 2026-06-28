import { readFileSync } from "node:fs";

const fixture = JSON.parse(
  readFileSync(new URL("../src/fixtures/edc_workbench_shell_state.json", import.meta.url), "utf8")
);

const fail = (message) => {
  throw new Error(message);
};

const requireTrue = (condition, message) => {
  if (!condition) fail(message);
};

const requiredViews = [
  "work_items",
  "work_item_detail",
  "agents",
  "runtime_worktrees",
  "evidence_runs",
  "pr_uat_closeout",
  "inbox_attention",
  "settings_boundaries"
];
const requiredSafety = [
  "runtime_hold",
  "dependency_install_not_authorized",
  "broker_nats_mutation_blocked",
  "live_dispatch_blocked",
  "owner_uat_after_edc_pr_010"
];
const requiredWorkItems = ["EDC-PR-006", "EDC-PR-007", "EDC-PR-008", "EDC-PR-009", "EDC-PR-010", "EDC-PR-011"];
const requiredAgentRoles = ["codex_planning", "codex_execution", "reviewer_reducer", "owner_uat"];
const requiredRuntimeWorktrees = ["EDC-PR-006", "EDC-PR-007", "EDC-PR-008", "EDC-PR-009"];
const requiredEvidenceRuns = ["EDC-PR-006", "EDC-PR-007", "EDC-PR-008", "EDC-PR-009", "EDC-PR-010", "EDC-PR-011"];
const requiredPrStack = ["EDC-PR-001", "EDC-PR-002", "EDC-PR-003", "EDC-PR-004", "EDC-PR-005", "EDC-PR-006", "EDC-PR-007", "EDC-PR-008", "EDC-PR-009", "EDC-PR-010", "EDC-PR-011"];
const requiredAttention = ["owner_uat_needed", "merge_blocked", "runtime_startup_separate_authorization", "dependency_install_not_authorized", "broker_nats_mutation_blocked", "live_dispatch_blocked"];
const requiredSettingsBoundaries = ["planning_execution_role_boundary", "openclaw_private_material_exclusion", "nexus_local_test_vs_openclaw_live_nats", "worktree_location_policy", "evidence_before_claim", "pr_mapping_separation", "no_owner_uat_automation"];
const requiredTaskCardFields = ["goal", "scope_summary", "non_goals", "editable_boundary", "validation_commands", "risks", "write_back_location"];
const allowedReadinessStates = new Set(["validated", "in_review", "planned", "blocked"]);
const allowedEvidenceStates = new Set(["present", "not_run_by_scope", "missing"]);
const edcIdPattern = /^EDC-PR-\d{3}$/;

const mappings = fixture.pr_mappings ?? [];
const views = fixture.views ?? [];
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
const safetyIds = new Set((fixture.safety_boundaries ?? []).map((item) => item.id));

requireTrue(fixture.surface === "Nexus Agent Coding Team Workbench", "fixture surface must be Workbench");
requireTrue(fixture.fixture_only === true, "fixture must be fixture-only");
requireTrue(fixture.non_authoritative === true, "fixture must be non-authoritative");
requireTrue(Boolean(fixture.authority_statement?.includes("Fixture-only")), "authority statement must be explicit");
requireTrue(fixture.live_execution_invoked === false, "live execution must not be invoked");
requireTrue(fixture.runtime_startup_allowed === false, "runtime startup must not be allowed");
requireTrue(fixture.dependency_install_allowed === false, "dependency install must not be allowed");
requireTrue(fixture.broker_mutation_allowed === false, "broker mutation must not be allowed");
requireTrue(fixture.live_dispatch_allowed === false, "live dispatch must not be allowed");
requireTrue(fixture.canonical_mutation_allowed === false, "canonical mutation must not be allowed");
requireTrue(fixture.owner_uat_accepted === false, "owner UAT acceptance must not be claimed");
requireTrue(fixture.uat_pass_claimed === false, "UAT pass must not be claimed");
requireTrue(fixture.merge_approved === false, "merge approval must not be claimed");
requireTrue(fixture.production_readiness_claimed === false, "production readiness must not be claimed");
requireTrue(fixture.live_readiness_claimed === false, "live readiness must not be claimed");
requireTrue(fixture.owner_uat_after === "EDC-PR-010", "owner UAT must remain after EDC-PR-010");
requireTrue(fixture.selected_work_item_id === "EDC-PR-011", "default selected work item must be EDC-PR-011");

const viewIds = views.map((view) => view.id);
requireTrue(viewIds.length === requiredViews.length, "fixture must expose exactly the shell-level required views");
for (const requiredView of requiredViews) {
  requireTrue(viewIds.includes(requiredView), `missing required view: ${requiredView}`);
}
for (const view of views) {
  requireTrue(view.nav_target === view.id, `view nav target must match id: ${view.id}`);
  requireTrue(!String(view.nav_target).startsWith("#"), `view must not use hash navigation: ${view.id}`);
  requireTrue(!String(view.navigation_semantics).includes("anchor"), `view must not use anchor semantics: ${view.id}`);
  requireTrue(!String(view.navigation_semantics).includes("scroll"), `view must not use scroll semantics: ${view.id}`);
  requireTrue(["EDC-PR-008", "EDC-PR-009", "EDC-PR-010"].includes(view.implementation_pr), `unexpected implementation owner: ${view.id}`);
}
for (const required of requiredSafety) {
  requireTrue(safetyIds.has(required), `missing safety boundary: ${required}`);
}

for (const mapping of mappings) {
  requireTrue(edcIdPattern.test(mapping.internal_id), `invalid EDC id: ${mapping.internal_id}`);
  requireTrue(String(mapping.internal_id) !== String(mapping.github_pr_number), `GitHub PR number used as internal id: ${mapping.internal_id}`);
}
const byId = new Map(mappings.map((mapping) => [mapping.internal_id, mapping]));
for (const [internalId, githubNumber] of [["EDC-PR-001", 27], ["EDC-PR-002", 28], ["EDC-PR-003", 29], ["EDC-PR-004", 30], ["EDC-PR-005", 31], ["EDC-PR-006", 32], ["EDC-PR-007", 33], ["EDC-PR-008", 34], ["EDC-PR-009", 35], ["EDC-PR-010", 36], ["EDC-PR-011", 37]]) {
  const mapping = byId.get(internalId);
  requireTrue(Boolean(mapping), `missing PR mapping for ${internalId}`);
  requireTrue(mapping.github_pr_number === githubNumber, `${internalId} must map to GitHub PR #${githubNumber}`);
}
requireTrue(byId.get("EDC-PR-010")?.github_pr_label === "#36", "EDC-PR-010 GitHub label must be #36");
requireTrue(byId.get("EDC-PR-010")?.status === "draft_pr_open", "EDC-PR-010 status must be draft_pr_open");
requireTrue(byId.get("EDC-PR-011")?.github_pr_number === 37, "EDC-PR-011 must map to GitHub PR #37");
requireTrue(byId.get("EDC-PR-011")?.github_pr_label === "#37", "EDC-PR-011 GitHub label must be #37");
requireTrue(byId.get("EDC-PR-011")?.status === "draft_pr_open", "EDC-PR-011 status must be draft_pr_open");
requireTrue(byId.get("EDC-PR-004")?.baseline_role === "superseded_prototype", "EDC-PR-004/#30 must be superseded");
requireTrue(byId.get("EDC-PR-005")?.baseline_role === "superseded_prototype", "EDC-PR-005/#31 must be superseded");
requireTrue(!mappings.some((mapping) => mapping.baseline_role === "uat_baseline"), "no mapping may be UAT baseline in EDC-PR-010");

const workItemsById = new Map(workItems.map((item) => [item.internal_id, item]));
requireTrue(workItems.length === requiredWorkItems.length, "fixture must expose the required EDC work items only");
for (const requiredWorkItem of requiredWorkItems) {
  requireTrue(workItemsById.has(requiredWorkItem), `missing work item: ${requiredWorkItem}`);
}
for (const item of workItems) {
  requireTrue(edcIdPattern.test(item.internal_id), `invalid work item id: ${item.internal_id}`);
  requireTrue(String(item.internal_id) !== String(item.github_pr_number), `${item.internal_id} confuses internal ID and GitHub PR number`);
  requireTrue(item.owner_uat_state !== "accepted_by_owner", `${item.internal_id} must not claim owner UAT acceptance`);
  requireTrue(["not_required", "hold"].includes(item.runtime_authorization_state), `${item.internal_id} has unsafe runtime authorization`);
  requireTrue(allowedReadinessStates.has(item.readiness_state), `${item.internal_id} has missing readiness state`);
  requireTrue(allowedEvidenceStates.has(item.evidence_state), `${item.internal_id} has missing evidence state`);
  for (const field of requiredTaskCardFields) {
    const value = item.task_card?.[field];
    requireTrue(Array.isArray(value) ? value.length > 0 : Boolean(value), `${item.internal_id} missing task-card field: ${field}`);
  }
}
requireTrue(workItemsById.get("EDC-PR-009")?.github_pr_number === 35, "EDC-PR-009 work item must map to GitHub PR #35");
requireTrue(workItemsById.get("EDC-PR-010")?.github_pr_number === 36, "EDC-PR-010 work item must map to GitHub PR #36");
requireTrue(workItemsById.get("EDC-PR-010")?.github_pr_label === "#36", "EDC-PR-010 work item label must be #36");
requireTrue(workItemsById.get("EDC-PR-010")?.branch === "codex/edc-pr-010-evidence-uat-closeout", "EDC-PR-010 work item branch is invalid");
requireTrue(workItemsById.get("EDC-PR-010")?.base_commit === "68eca33", "EDC-PR-010 work item base is invalid");
requireTrue(workItemsById.get("EDC-PR-010")?.owner_uat_state === "awaiting_owner", "EDC-PR-010 must keep owner UAT awaiting owner");
requireTrue(workItemsById.get("EDC-PR-011")?.github_pr_number === 37, "EDC-PR-011 work item must map to GitHub PR #37");
requireTrue(workItemsById.get("EDC-PR-011")?.branch === "codex/edc-pr-011-agent-runtime-command-drafts", "EDC-PR-011 work item branch is invalid");
requireTrue(workItemsById.get("EDC-PR-011")?.base_commit === "dd4f9b0", "EDC-PR-011 work item base is invalid");
requireTrue(workItemsById.get("EDC-PR-011")?.owner_uat_state === "awaiting_owner", "EDC-PR-011 must keep owner UAT awaiting owner");

const agentsByRole = new Map(agents.map((agent) => [agent.role_id, agent]));
requireTrue(agents.length === requiredAgentRoles.length, "fixture must expose the required agent roles only");
for (const role of requiredAgentRoles) {
  requireTrue(agentsByRole.has(role), `missing agent role: ${role}`);
}
for (const agent of agents) {
  requireTrue(agent.forbidden_actions?.includes("live_dispatch"), `${agent.role_id} must forbid live dispatch`);
  requireTrue(agent.forbidden_actions?.includes("credential_access"), `${agent.role_id} must forbid credential access`);
  requireTrue(agent.forbidden_actions?.includes("private_session_access"), `${agent.role_id} must forbid private session access`);
}
requireTrue(!agentsByRole.get("codex_execution")?.allowed_actions.includes("owner_uat_acceptance"), "Execution must not own owner UAT acceptance");
requireTrue(!agentsByRole.get("owner_uat")?.allowed_actions.includes("automated_validation"), "Owner UAT must not be automated validation");

const runtimeById = new Map(runtimeWorktrees.map((record) => [record.internal_id, record]));
requireTrue(runtimeWorktrees.length === requiredRuntimeWorktrees.length, "fixture must expose the required runtime worktrees only");
for (const internalId of requiredRuntimeWorktrees) {
  requireTrue(runtimeById.has(internalId), `missing runtime worktree: ${internalId}`);
}
for (const record of runtimeWorktrees) {
  requireTrue(record.startup_allowed === false, `${record.internal_id} must block runtime startup`);
  requireTrue(record.dependency_install_allowed === false, `${record.internal_id} must block dependency install`);
  requireTrue(record.broker_mutation_allowed === false, `${record.internal_id} must block broker mutation`);
  requireTrue(record.live_dispatch_allowed === false, `${record.internal_id} must block live dispatch`);
  requireTrue(record.cleanup_allowed === false, `${record.internal_id} must block cleanup`);
}

const evidenceById = new Map(evidenceRuns.map((record) => [record.internal_id, record]));
requireTrue(evidenceRuns.length === requiredEvidenceRuns.length, "fixture must expose required evidence records only");
for (const internalId of requiredEvidenceRuns) {
  requireTrue(evidenceById.has(internalId), `missing evidence record: ${internalId}`);
}
for (const record of evidenceRuns) {
  requireTrue(edcIdPattern.test(record.internal_id), `invalid evidence record id: ${record.internal_id}`);
  requireTrue(Boolean(record.command), `${record.internal_id} evidence record missing command`);
  requireTrue(["passed", "not_run"].includes(record.status), `${record.internal_id} evidence status is invalid`);
  requireTrue(["present", "not_run_by_scope"].includes(record.evidence_state), `${record.internal_id} evidence state is invalid`);
  if (record.status === "passed") {
    requireTrue(record.exit_code === 0, `${record.internal_id} passed evidence requires exit 0`);
    requireTrue(Boolean(record.evidence_ref), `${record.internal_id} passed evidence requires evidence ref`);
  }
  if (record.evidence_state === "not_run_by_scope") {
    requireTrue(Boolean(record.not_run_reason), `${record.internal_id} not_run_by_scope requires reason`);
  }
}
requireTrue(evidenceById.get("EDC-PR-010")?.github_pr_number === 36, "EDC-PR-010 evidence must map to GitHub PR #36");
requireTrue(evidenceById.get("EDC-PR-011")?.github_pr_number === 37, "EDC-PR-011 evidence must map to GitHub PR #37");

const prStackById = new Map(prStack.map((record) => [record.internal_id, record]));
requireTrue(prStack.length === requiredPrStack.length, "fixture must expose required PR stack records only");
for (const internalId of requiredPrStack) {
  requireTrue(prStackById.has(internalId), `missing PR stack record: ${internalId}`);
}
for (const record of prStack) {
  requireTrue(edcIdPattern.test(record.internal_id), `invalid PR stack id: ${record.internal_id}`);
  requireTrue(String(record.internal_id) !== String(record.github_pr_number), `${record.internal_id} confuses GitHub PR number with internal ID`);
}
requireTrue(prStackById.get("EDC-PR-004")?.baseline_role === "superseded_prototype", "EDC-PR-004 must remain superseded");
requireTrue(prStackById.get("EDC-PR-005")?.baseline_role === "superseded_prototype", "EDC-PR-005 must remain superseded");
requireTrue(prStackById.get("EDC-PR-010")?.github_pr_number === 36, "EDC-PR-010 PR stack must map to GitHub PR #36");
requireTrue(prStackById.get("EDC-PR-010")?.status === "draft_pr_open", "EDC-PR-010 PR stack status must be draft_pr_open");
requireTrue(prStackById.get("EDC-PR-011")?.github_pr_number === 37, "EDC-PR-011 PR stack must map to GitHub PR #37");
requireTrue(prStackById.get("EDC-PR-011")?.status === "draft_pr_open", "EDC-PR-011 PR stack status must be draft_pr_open");
requireTrue(!prStack.some((record) => record.baseline_role === "uat_baseline"), "PR stack must not claim UAT baseline");

const owner = fixture.owner_uat_decision;
const recommendation = fixture.closeout_recommendation;
requireTrue(owner?.state === "awaiting_owner", "owner UAT decision must await owner");
requireTrue(owner?.decision_ref === "", "owner decision ref must remain blank");
requireTrue(owner?.acceptance_claimed === false, "owner acceptance must not be claimed");
requireTrue(owner?.uat_pass_claimed === false, "UAT pass must not be claimed");
requireTrue(recommendation?.state === "prepared_blocked_awaiting_owner", "closeout recommendation must remain blocked awaiting owner");
requireTrue(recommendation?.merge_ready === false, "merge readiness must not be claimed");
requireTrue(recommendation?.production_ready === false, "production readiness must not be claimed");
requireTrue(recommendation?.live_ready === false, "live readiness must not be claimed");
requireTrue(recommendation?.closeout_accepted === false, "closeout acceptance must not be claimed");

const attentionIds = inboxAttention.map((item) => item.id);
for (const id of requiredAttention) {
  requireTrue(attentionIds.includes(id), `missing attention item: ${id}`);
}
for (const item of inboxAttention) {
  requireTrue(item.read_only === true, `${item.id} attention item must be read-only`);
}
const boundaryIds = settingsBoundaries.map((item) => item.id);
for (const id of requiredSettingsBoundaries) {
  requireTrue(boundaryIds.includes(id), `missing settings boundary: ${id}`);
}
const natsBoundary = settingsBoundaries.find((item) => item.id === "nexus_local_test_vs_openclaw_live_nats");
requireTrue(natsBoundary?.local_test_nats === "127.0.0.1:7422", "settings must show Nexus local-test NATS");
requireTrue(natsBoundary?.openclaw_live_nats === "127.0.0.1:4222", "settings must show OpenClaw live NATS");
requireTrue(natsBoundary?.openclaw_live_mutable === false, "OpenClaw live NATS must not be mutable");

const nats = fixture.nats_boundary;
requireTrue(nats?.local_test?.nats === "127.0.0.1:7422", "local-test NATS address is missing");
requireTrue(nats?.local_test?.monitor === "http://127.0.0.1:8422/varz", "local-test NATS monitor is missing");
requireTrue(nats?.local_test?.use_allowed === false, "local-test NATS must not be used in this slice");
requireTrue(nats?.openclaw_live?.nats === "127.0.0.1:4222", "OpenClaw live NATS address is missing");
requireTrue(nats?.openclaw_live?.use_allowed === false, "OpenClaw live NATS must not be usable");
requireTrue(nats?.openclaw_live?.mutation_allowed === false, "OpenClaw live NATS must not be mutable");
requireTrue(fixture.base_decision?.continue_from === "EDC-PR-006 / GitHub PR #32", "base decision must continue from EDC-PR-006/#32");
requireTrue((fixture.base_decision?.bypass ?? []).includes("EDC-PR-004 / GitHub PR #30"), "base decision must bypass PR #30");
requireTrue((fixture.base_decision?.bypass ?? []).includes("EDC-PR-005 / GitHub PR #31"), "base decision must bypass PR #31");

const agentDefinitionIds = new Set(agentDefinitions.map((record) => record.agent_id));
const providerIds = new Set(runtimeProviders.map((record) => record.provider_id));
const runtimeInstanceIds = new Set(runtimeInstances.map((record) => record.runtime_instance_id));
const runSessionIds = new Set(runSessions.map((record) => record.run_session_id));
requireTrue(agentDefinitions.length >= 4, "fixture must expose agent definitions");
requireTrue(runtimeProviders.length >= 3, "fixture must expose runtime providers");
requireTrue(runtimeInstances.length >= 2, "fixture must expose runtime instances");
requireTrue(runSessions.length >= 1, "fixture must expose run sessions");
for (const id of agentDefinitionIds) {
  requireTrue(!providerIds.has(id), `agent id must not equal provider id: ${id}`);
  requireTrue(!runtimeInstanceIds.has(id), `agent id must not equal runtime instance id: ${id}`);
  requireTrue(!runSessionIds.has(id), `agent id must not equal run session id: ${id}`);
}
for (const runtimeId of runtimeInstanceIds) {
  requireTrue(!runSessionIds.has(runtimeId), `runtime instance id must not equal run session id: ${runtimeId}`);
}
for (const provider of runtimeProviders) {
  requireTrue(provider.executable === false, `${provider.provider_id} must not be executable in EDC-PR-011`);
  if (provider.provider_family === "openclaw") {
    requireTrue(Boolean(provider.blocked_reason), "OpenClaw provider requires blocked reason");
  }
}
for (const runtime of runtimeInstances) {
  requireTrue(runtime.startup_allowed === false, `${runtime.runtime_instance_id} must block startup`);
  requireTrue(runtime.dependency_install_allowed === false, `${runtime.runtime_instance_id} must block dependency install`);
  requireTrue(runtime.broker_mutation_allowed === false, `${runtime.runtime_instance_id} must block broker mutation`);
  requireTrue(runtime.live_dispatch_allowed === false, `${runtime.runtime_instance_id} must block live dispatch`);
}
const allowedCommandTypes = new Set([
  "evaluate_assignment_candidate",
  "prepare_execution_handoff_draft",
  "request_owner_uat_decision_draft",
  "refresh_projection_draft",
  "record_validation_evidence_draft"
]);
requireTrue(commandDrafts.length >= 3, "fixture must expose command drafts");
for (const draft of commandDrafts) {
  requireTrue(allowedCommandTypes.has(draft.command_type), `unsafe command draft type: ${draft.command_type}`);
  requireTrue(draft.draft_only === true, `${draft.draft_id} must be draft-only`);
  requireTrue(draft.non_authoritative === true, `${draft.draft_id} must be non-authoritative`);
  requireTrue(draft.live_dispatch_claimed === false, `${draft.draft_id} must not claim live dispatch`);
  requireTrue(draft.runtime_startup_claimed === false, `${draft.draft_id} must not claim runtime startup`);
  requireTrue(draft.dependency_install_claimed === false, `${draft.draft_id} must not claim dependency install`);
  requireTrue(draft.broker_mutation_claimed === false, `${draft.draft_id} must not claim broker mutation`);
  requireTrue(draft.merge_claimed === false, `${draft.draft_id} must not claim merge`);
  requireTrue(draft.owner_uat_acceptance_claimed === false, `${draft.draft_id} must not claim owner UAT acceptance`);
  requireTrue(draft.production_readiness_claimed === false, `${draft.draft_id} must not claim production readiness`);
  requireTrue(draft.live_readiness_claimed === false, `${draft.draft_id} must not claim live readiness`);
  requireTrue((draft.blocked_authorities ?? []).includes("live_dispatch"), `${draft.draft_id} must block live dispatch`);
  requireTrue(Boolean(draft.handoff_preview_ref), `${draft.draft_id} requires handoff preview ref`);
  requireTrue(Boolean(draft.write_back_location), `${draft.draft_id} requires write-back location`);
  requireTrue((draft.evidence_requirements ?? []).length > 0, `${draft.draft_id} requires evidence requirements`);
}
requireTrue(dispatchCandidates.length >= 1, "fixture must expose dispatch candidate projection");
const edcPr011Candidate = dispatchCandidates.find((candidate) => candidate.work_item_id === "EDC-PR-011");
requireTrue(Boolean(edcPr011Candidate), "fixture must expose EDC-PR-011 dispatch candidate projection");
for (const candidate of dispatchCandidates) {
  requireTrue(candidate.eligible === false, `${candidate.candidate_id} must not be dispatch eligible`);
  requireTrue((candidate.blocked_reasons ?? []).includes("draft_only"), `${candidate.candidate_id} must remain draft-only`);
  if (candidate.work_item_id === "EDC-PR-011") {
    requireTrue(candidate.agent_id === "agent.codex.execution", "EDC-PR-011 dispatch candidate must target Codex Execution");
    requireTrue(candidate.runtime_instance_id === "runtime.codex.edc-pr-011.local", "EDC-PR-011 dispatch candidate must target local Codex runtime projection");
  }
}
requireTrue(handoffPreviews.length >= 1, "fixture must expose handoff preview");
for (const preview of handoffPreviews) {
  requireTrue(Boolean(preview.preview_id), "handoff preview requires id");
  requireTrue(Boolean(preview.write_back_location), `${preview.preview_id} requires write-back location`);
  requireTrue(Boolean(preview.task_card_ref), `${preview.preview_id} requires task card ref`);
}
console.log("edc workbench evidence closeout fixture verified");
