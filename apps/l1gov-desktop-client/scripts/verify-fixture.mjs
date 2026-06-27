import { readFileSync } from "node:fs";

const fixture = JSON.parse(
  readFileSync(new URL("../src/fixtures/edc_delivery_board_state.json", import.meta.url), "utf8")
);

const fail = (message) => {
  throw new Error(message);
};

const requireTrue = (condition, message) => {
  if (!condition) fail(message);
};

const edcIdPattern = /^EDC-PR-\d{3}$/;
const workItems = fixture.work_items ?? [];
const mappings = fixture.pr_mappings ?? [];
const attentionIds = new Set((fixture.attention_states ?? []).map((item) => item.id));
const noGoStates = new Set(fixture.closeout?.no_go_states ?? []);

requireTrue(fixture.fixture_only === true, "fixture must be marked fixture_only");
requireTrue(fixture.non_authoritative === true, "fixture must be marked non_authoritative");
requireTrue(Boolean(fixture.authority_statement?.includes("Fixture-backed")), "fixture authority statement must be explicit");
requireTrue(fixture.live_execution_invoked === false, "fixture must not invoke live execution");
requireTrue(fixture.live_dispatch_allowed === false, "fixture must not allow live dispatch");
requireTrue(fixture.runtime_startup_allowed === false, "fixture must not allow runtime startup");
requireTrue(fixture.dependency_install_allowed === false, "fixture must not allow dependency install");
requireTrue(fixture.broker_mutation_allowed === false, "fixture must not allow broker mutation");
requireTrue(fixture.canonical_mutation_allowed === false, "fixture must not allow canonical mutation");

requireTrue(workItems.length >= 5, "fixture must include EDC-PR-001 through EDC-PR-005 work items");
for (const item of workItems) {
  requireTrue(edcIdPattern.test(item.internal_id), `invalid internal work item id: ${item.internal_id}`);
  requireTrue(String(item.internal_id) !== String(item.github_pr_number), `GitHub PR number used as internal id: ${item.internal_id}`);
  requireTrue(item.validation?.state, `${item.internal_id} missing validation state`);
  requireTrue(item.evidence_state, `${item.internal_id} missing evidence state`);
  requireTrue(item.owner_uat_state, `${item.internal_id} missing owner UAT state`);
  requireTrue(item.runtime_authorization_state, `${item.internal_id} missing runtime authorization state`);
  requireTrue(item.owner_uat_state !== "accepted_by_owner", `${item.internal_id} must not claim owner UAT acceptance`);
}

for (const mapping of mappings) {
  requireTrue(edcIdPattern.test(mapping.internal_id), `invalid PR mapping internal id: ${mapping.internal_id}`);
  requireTrue(String(mapping.internal_id) !== String(mapping.github_pr_number), `PR mapping confuses internal and GitHub id: ${mapping.internal_id}`);
}

for (const githubNumber of [27, 28, 29, 30]) {
  requireTrue(
    mappings.some((mapping) => mapping.github_pr_number === githubNumber),
    `missing GitHub PR #${githubNumber} mapping`
  );
}

const edc004 = mappings.find((mapping) => mapping.internal_id === "EDC-PR-004");
requireTrue(Boolean(edc004), "missing EDC-PR-004 PR mapping");
requireTrue(edc004.github_pr_number === 30 && edc004.github_pr_label === "#30", "EDC-PR-004 GitHub PR must map to #30");
requireTrue(edc004.branch === "codex/edc-pr-004-desktop-delivery-board", "EDC-PR-004 branch mapping is invalid");

const edc005 = mappings.find((mapping) => mapping.internal_id === "EDC-PR-005");
requireTrue(Boolean(edc005), "missing EDC-PR-005 PR mapping");
requireTrue(edc005.github_pr_number === null && edc005.github_pr_label === "TBD", "EDC-PR-005 GitHub PR must remain TBD");
requireTrue(edc005.branch === "codex/edc-pr-005-owner-uat-closeout", "EDC-PR-005 branch mapping is invalid");
requireTrue(edc005.status === "not_created", "EDC-PR-005 GitHub PR must not be marked open yet");

const activeItem = workItems.find((item) => item.internal_id === "EDC-PR-005");
requireTrue(Boolean(activeItem), "missing EDC-PR-005 work item");
requireTrue(activeItem.branch === "codex/edc-pr-005-owner-uat-closeout", "EDC-PR-005 work item branch is invalid");
requireTrue(Boolean(activeItem.worktree?.includes(".worktrees\\edc-pr-005-owner-uat-closeout")), "EDC-PR-005 worktree mapping is invalid");
requireTrue(activeItem.runtime_authorization_state === "hold", "EDC-PR-005 runtime authorization must be hold");
requireTrue(activeItem.owner_uat_state === "awaiting_owner", "EDC-PR-005 must await owner UAT");

const closeout = fixture.closeout;
requireTrue(Boolean(closeout), "missing closeout read model");
requireTrue(closeout.state === "blocked_awaiting_owner", "closeout must be blocked awaiting owner");
requireTrue(closeout.owner_decision?.state === "awaiting_owner", "owner decision must await owner");
requireTrue(closeout.owner_decision?.automated_validation_is_owner_acceptance === false, "automated validation must not be owner acceptance");
requireTrue(!closeout.owner_decision?.decision_ref, "fixture must not record a fake owner decision");

for (const gate of closeout.evidence_gates ?? []) {
  requireTrue(edcIdPattern.test(gate.internal_id), `invalid evidence gate id: ${gate.internal_id}`);
  requireTrue(gate.automated_validation_state, `${gate.internal_id} missing automated validation gate`);
  requireTrue(gate.owner_uat_state !== "accepted_by_owner", `${gate.internal_id} must not treat validation as owner acceptance`);
}

requireTrue(closeout.recommendation?.state === "blocked_awaiting_owner", "closeout recommendation must remain blocked");
requireTrue(closeout.recommendation?.merge_ready === false, "merge readiness must not be claimed");
requireTrue(closeout.recommendation?.uat_pass_claimed === false, "UAT pass must not be claimed");
requireTrue(closeout.recommendation?.production_readiness_claimed === false, "production readiness must not be claimed");
requireTrue(closeout.recommendation?.live_ready_claimed === false, "live readiness must not be claimed");
requireTrue(closeout.recommendation?.closeout_accepted === false, "closeout accepted must not be claimed");

for (const requiredAttention of [
  "runtime_hold",
  "dependency_install_not_authorized",
  "broker_nats_mutation_blocked",
  "live_dispatch_blocked",
  "owner_uat_not_accepted",
  "merge_blocked",
  "uat_pass_blocked",
  "production_readiness_blocked",
  "closeout_blocked_awaiting_owner",
  "scope_evidence_gate"
]) {
  requireTrue(attentionIds.has(requiredAttention), `missing attention state: ${requiredAttention}`);
}

for (const requiredNoGo of [
  "merge_blocked",
  "uat_pass_blocked",
  "production_readiness_blocked",
  "runtime_startup_hold",
  "dependency_install_not_authorized",
  "broker_nats_mutation_blocked",
  "live_dispatch_blocked",
  "closeout_blocked_awaiting_owner"
]) {
  requireTrue(noGoStates.has(requiredNoGo), `missing closeout no-go state: ${requiredNoGo}`);
}

const disabledLabels = new Set((fixture.disabled_actions ?? []).map((action) => action.label));
for (const requiredAction of [
  "Assign agent",
  "Start runtime",
  "Merge PR",
  "Dispatch live agent",
  "Accept owner UAT",
  "Claim UAT pass",
  "Mark closeout accepted"
]) {
  requireTrue(disabledLabels.has(requiredAction), `missing disabled action: ${requiredAction}`);
}

console.log("edc delivery board fixture verified");