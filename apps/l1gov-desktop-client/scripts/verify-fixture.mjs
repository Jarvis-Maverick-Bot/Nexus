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

const requiredWorkItems = ["EDC-PR-006", "EDC-PR-007", "EDC-PR-008", "EDC-PR-009", "EDC-PR-010"];
const requiredTaskCardFields = [
  "goal",
  "scope_summary",
  "non_goals",
  "editable_boundary",
  "validation_commands",
  "risks",
  "write_back_location"
];
const allowedEvidenceStates = new Set(["validated", "in_review", "planned", "blocked"]);
const allowedValidationStates = new Set(["present", "not_run_by_scope", "missing"]);
const edcIdPattern = /^EDC-PR-\d{3}$/;
const mappings = fixture.pr_mappings ?? [];
const views = fixture.views ?? [];
const workItems = fixture.work_items ?? [];
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
for (const [internalId, githubNumber] of [
  ["EDC-PR-001", 27],
  ["EDC-PR-002", 28],
  ["EDC-PR-003", 29],
  ["EDC-PR-004", 30],
  ["EDC-PR-005", 31],
  ["EDC-PR-006", 32],
  ["EDC-PR-007", 33],
  ["EDC-PR-008", 34]
]) {
  const mapping = byId.get(internalId);
  requireTrue(Boolean(mapping), `missing PR mapping for ${internalId}`);
  requireTrue(mapping.github_pr_number === githubNumber, `${internalId} must map to GitHub PR #${githubNumber}`);
}

requireTrue(byId.get("EDC-PR-004")?.baseline_role === "superseded_prototype", "EDC-PR-004/#30 must be superseded");
requireTrue(byId.get("EDC-PR-005")?.baseline_role === "superseded_prototype", "EDC-PR-005/#31 must be superseded");
requireTrue(!mappings.some((mapping) => mapping.baseline_role === "uat_baseline"), "no mapping may be UAT baseline in EDC-PR-008");

const edc008 = byId.get("EDC-PR-008");
requireTrue(Boolean(edc008), "missing EDC-PR-008 mapping");
requireTrue(edc008.github_pr_number === 34 && edc008.github_pr_label === "#34", "EDC-PR-008 GitHub PR must map to #34");
requireTrue(edc008.branch === "codex/edc-pr-008-work-items-surface", "EDC-PR-008 branch mapping is invalid");
requireTrue(edc008.status === "draft_pr_open", "EDC-PR-008 status must be draft_pr_open");
requireTrue(edc008.worktree?.endsWith(".worktrees\\edc-pr-008-work-items-surface"), "EDC-PR-008 worktree mapping is invalid");
requireTrue(edc008.base_commit === "e14d71e", "EDC-PR-008 base commit must be e14d71e");

const workItemsById = new Map(workItems.map((item) => [item.internal_id, item]));
requireTrue(workItems.length === requiredWorkItems.length, "fixture must expose the required EDC work items only");
requireTrue(fixture.selected_work_item_id === "EDC-PR-008", "default selected work item must be EDC-PR-008");
for (const requiredWorkItem of requiredWorkItems) {
  requireTrue(workItemsById.has(requiredWorkItem), `missing work item: ${requiredWorkItem}`);
}
for (const item of workItems) {
  requireTrue(edcIdPattern.test(item.internal_id), `invalid work item id: ${item.internal_id}`);
  requireTrue(String(item.internal_id) !== String(item.github_pr_number), `${item.internal_id} confuses internal ID and GitHub PR number`);
  requireTrue(item.owner_uat_state !== "accepted_by_owner", `${item.internal_id} must not claim owner UAT acceptance`);
  requireTrue(["not_required", "hold"].includes(item.runtime_authorization_state), `${item.internal_id} has unsafe runtime authorization`);
  requireTrue(allowedEvidenceStates.has(item.readiness_state), `${item.internal_id} has missing readiness state`);
  requireTrue(allowedValidationStates.has(item.evidence_state), `${item.internal_id} has missing evidence state`);
  for (const field of requiredTaskCardFields) {
    const value = item.task_card?.[field];
    requireTrue(Array.isArray(value) ? value.length > 0 : Boolean(value), `${item.internal_id} missing task-card field: ${field}`);
  }
}
requireTrue(workItemsById.get("EDC-PR-008")?.github_pr_number === 34, "EDC-PR-008 work item must map to GitHub PR #34");
requireTrue(workItemsById.get("EDC-PR-008")?.github_pr_label === "#34", "EDC-PR-008 work item must show PR #34");
requireTrue(workItemsById.get("EDC-PR-008")?.branch === "codex/edc-pr-008-work-items-surface", "EDC-PR-008 work item branch is invalid");
requireTrue(workItemsById.get("EDC-PR-008")?.worktree?.endsWith(".worktrees\\edc-pr-008-work-items-surface"), "EDC-PR-008 work item worktree is invalid");
requireTrue(workItemsById.get("EDC-PR-010")?.owner_uat_state === "awaiting_owner", "EDC-PR-010 must keep owner UAT awaiting owner");

requireTrue(fixture.base_decision?.continue_from === "EDC-PR-006 / GitHub PR #32", "base decision must continue from EDC-PR-006/#32");
requireTrue((fixture.base_decision?.bypass ?? []).includes("EDC-PR-004 / GitHub PR #30"), "base decision must bypass PR #30");
requireTrue((fixture.base_decision?.bypass ?? []).includes("EDC-PR-005 / GitHub PR #31"), "base decision must bypass PR #31");

console.log("edc workbench work items fixture verified");
