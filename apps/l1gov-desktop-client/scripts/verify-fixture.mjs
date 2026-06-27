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

requireTrue(fixture.fixture_only === true, "fixture must be marked fixture_only");
requireTrue(fixture.non_authoritative === true, "fixture must be marked non_authoritative");
requireTrue(Boolean(fixture.authority_statement?.includes("Fixture-backed")), "fixture authority statement must be explicit");
requireTrue(fixture.live_execution_invoked === false, "fixture must not invoke live execution");
requireTrue(fixture.live_dispatch_allowed === false, "fixture must not allow live dispatch");
requireTrue(fixture.runtime_startup_allowed === false, "fixture must not allow runtime startup");
requireTrue(fixture.dependency_install_allowed === false, "fixture must not allow dependency install");
requireTrue(fixture.broker_mutation_allowed === false, "fixture must not allow broker mutation");
requireTrue(fixture.canonical_mutation_allowed === false, "fixture must not allow canonical mutation");

requireTrue(workItems.length >= 4, "fixture must include representative EDC work items");
for (const item of workItems) {
  requireTrue(edcIdPattern.test(item.internal_id), `invalid internal work item id: ${item.internal_id}`);
  requireTrue(String(item.internal_id) !== String(item.github_pr_number), `GitHub PR number used as internal id: ${item.internal_id}`);
  requireTrue(item.validation?.state, `${item.internal_id} missing validation state`);
  requireTrue(item.evidence_state, `${item.internal_id} missing evidence state`);
  requireTrue(item.owner_uat_state, `${item.internal_id} missing owner UAT state`);
  requireTrue(item.runtime_authorization_state, `${item.internal_id} missing runtime authorization state`);
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

const activeItem = workItems.find((item) => item.internal_id === "EDC-PR-004");
requireTrue(Boolean(activeItem), "missing EDC-PR-004 work item");
requireTrue(activeItem.branch === "codex/edc-pr-004-desktop-delivery-board", "EDC-PR-004 work item branch is invalid");
requireTrue(Boolean(activeItem.worktree?.includes(".worktrees\\edc-pr-004-desktop-delivery-board")), "EDC-PR-004 worktree mapping is invalid");
requireTrue(activeItem.runtime_authorization_state === "hold", "EDC-PR-004 runtime authorization must be hold");

for (const requiredAttention of [
  "runtime_hold",
  "live_dispatch_blocked",
  "owner_uat_not_accepted",
  "dependency_install_not_authorized",
  "scope_evidence_gate"
]) {
  requireTrue(attentionIds.has(requiredAttention), `missing attention state: ${requiredAttention}`);
}

const disabledLabels = new Set((fixture.disabled_actions ?? []).map((action) => action.label));
for (const requiredAction of ["Assign agent", "Start runtime", "Merge PR", "Dispatch live agent", "Accept owner UAT"]) {
  requireTrue(disabledLabels.has(requiredAction), `missing disabled action: ${requiredAction}`);
}

console.log("edc delivery board fixture verified");
