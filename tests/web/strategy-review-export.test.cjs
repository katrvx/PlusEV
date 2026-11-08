const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(repoRoot, relativePath), "utf8"));
}

function loadExportHelper() {
  const source = fs.readFileSync(path.join(repoRoot, "apps/web/src/lib/strategy-review-export.ts"), "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    fileName: "strategy-review-export.ts",
  }).outputText;
  const module = { exports: {} };
  const context = {
    module,
    exports: module.exports,
    require,
    console,
    JSON,
    Date,
    URL: undefined,
    document: undefined,
    window: undefined,
    setTimeout,
  };
  vm.runInNewContext(output, context, { filename: "strategy-review-export.ts" });
  return module.exports;
}

const { buildStrategyReviewPackage } = loadExportHelper();
const trendReport = readJson("experiments/investigation_argon_lane_a.json");
const meanrevReport = readJson("experiments/investigation_argon_meanrev.json");
const frozenLook = readJson("experiments/frozen_look_btc-meanrev-48-demo.json");
const syntheticReport = readJson("experiments/investigation_fixture.json");

function strategyFor(report, overrides = {}) {
  return {
    strategy_id: report.strategy_id,
    name: report.strategy_id,
    symbol: "BTCUSDT",
    timeframe: "native report",
    strategy_version: "argon-native-report",
    source: "native_report",
    kind: "positions",
    status: "ready",
    row_count: 0,
    date_start: "",
    date_end: "",
    dataset_hash: "",
    assumptions: { timezone: "Not supplied", fee_bps: null, slippage_bps: null, execution: "Not supplied", description: "" },
    ...overrides,
  };
}

function experimentFor(report, overrides = {}) {
  return {
    experiment_id: report.experiment_id,
    strategy_id: report.strategy_id,
    status: "completed",
    mode: "measured",
    source: "native_report",
    synthetic: false,
    paper_eligible: false,
    native_report: report,
    frozen_evaluation: null,
    verdict_scope: report.strategy_id === "btc-trend-24-72-demo" ? "candidate" : "always_on",
    verdict: report.verdict === "candidate_for_frozen_test" ? "INCONCLUSIVE" : report.verdict,
    policy_id: report.champion_policy_id || "pending-native-report",
    dataset_hash: "",
    created_at: report.generated_at,
    progress: 100,
    message: "",
    windows: { train: "Recorded", validation: "Recorded", test: "Not accessed" },
    metrics: [],
    baselines: [],
    equity: [],
    regimes: [],
    evidence: [],
    steps: [],
    hypotheses: [],
    recommendation: "",
    limitations: [],
    policy: { description: "", conditions: [], holdout_frozen: false, test_evaluated: false },
    ...overrides,
  };
}

function selectedCandidate(report, overrides = {}) {
  const candidate = report.candidates.find((item) => item.status === "accepted_for_frozen_test") || report.candidates[0];
  return {
    policyId: candidate.policy_id,
    specHash: candidate.spec_hash,
    policySpec: candidate.policy_spec,
    status: candidate.status,
    historicalSelection: true,
    evidenceIds: candidate.evidence_ids,
    reasons: candidate.reasons,
    trialRows: report.trial_log.filter((row) => row.policy_id === candidate.policy_id),
    ...overrides,
  };
}

test("mean-reversion export preserves the selected spec but never claims approval", () => {
  const selected = selectedCandidate(meanrevReport);
  const experiment = experimentFor(meanrevReport, {
    frozen_evaluation: frozenLook,
    paper_eligible: false,
    policy: { description: "", conditions: [], holdout_frozen: true, test_evaluated: true },
  });
  const payload = buildStrategyReviewPackage({ experiment, strategy: strategyFor(meanrevReport), selectedFilter: selected });

  assert.equal(payload.runnable, false);
  assert.equal(payload.execution_claim, "none");
  assert.equal(payload.decision.status, "accepted_for_frozen_test");
  assert.equal(payload.decision.historical_selection, true);
  assert.equal(payload.decision.paper_eligible, false);
  assert.equal(payload.decision.paper_eligible_supplied, true);
  assert.equal(payload.decision.approval_claim, false);
  assert.equal(payload.decision.approval_status, "not approved");
  assert.deepEqual(payload.selected_filter.policySpec, selected.policySpec);
  assert.equal(payload.selected_filter.specHash, "spec_dbd7812c913a");
  assert.deepEqual(payload.frozen_evidence, frozenLook);
  assert.deepEqual(payload.native_report, meanrevReport);
});

test("trend export keeps the report policy count distinct from trial-log IDs and refusals", () => {
  const payload = buildStrategyReviewPackage({
    experiment: experimentFor(trendReport),
    strategy: strategyFor(trendReport),
    selectedFilter: null,
  });
  const trialIds = new Set(trendReport.trial_log.map((row) => row.policy_id));
  const refused = trendReport.trial_log.filter((row) => row.status === "refused");

  assert.equal(payload.native_report.n_policies_tried, 15);
  assert.equal(trialIds.size, 22);
  assert.equal(refused.length, 4);
  assert.equal(payload.decision.status, "No filter selected");
  assert.equal(payload.frozen_evidence, null);
});

test("a frozen look is excluded when its strategy, experiment, or selected policy identity mismatches", () => {
  const selected = selectedCandidate(meanrevReport);
  const baseExperiment = experimentFor(meanrevReport, { frozen_evaluation: frozenLook });
  const mismatches = [
    { ...frozenLook, strategy_id: "other-strategy" },
    { ...frozenLook, experiment_id: "other-experiment" },
    { ...frozenLook, evaluation: { ...frozenLook.evaluation, policy_id: "other-policy" } },
  ];

  for (const mismatch of mismatches) {
    const payload = buildStrategyReviewPackage({
      experiment: { ...baseExperiment, frozen_evaluation: mismatch },
      strategy: strategyFor(meanrevReport),
      selectedFilter: selected,
    });
    assert.equal(payload.frozen_evidence, null);
  }
});

test("synthetic demo records cannot become approved through copied flags", () => {
  const syntheticExperiment = experimentFor(syntheticReport, {
    source: "native_report_example",
    synthetic: true,
    mode: "demo",
    verdict: "KEEP",
    verdict_scope: "candidate",
    paper_eligible: true,
    policy_id: syntheticReport.champion_policy_id || "synthetic-policy",
    policy: { description: "", conditions: [], holdout_frozen: true, test_evaluated: true },
  });
  const payload = buildStrategyReviewPackage({
    experiment: syntheticExperiment,
    strategy: strategyFor(syntheticReport, { source: "native_report_example", synthetic: true, status: "demo" }),
    selectedFilter: selectedCandidate(syntheticReport),
  });

  assert.equal(payload.decision.paper_eligible, false);
  assert.equal(payload.decision.approval_claim, false);
  assert.equal(payload.decision.approval_status, "not approved");
});

test("a positive eligibility flag is not enough without an explicit measured verdict matching the selected policy", () => {
  const selected = selectedCandidate(meanrevReport);
  const validFrozen = { ...frozenLook, evaluation: { ...frozenLook.evaluation, policy_id: selected.policyId } };
  const base = experimentFor(meanrevReport, {
    paper_eligible: true,
    frozen_evaluation: validFrozen,
    native_report: { ...meanrevReport, verdict: "KEEP", champion_policy_id: selected.policyId },
    policy_id: selected.policyId,
    verdict: "KEEP",
    verdict_scope: "candidate",
    policy: { description: "", conditions: [], holdout_frozen: true, test_evaluated: true },
  });
  const positive = buildStrategyReviewPackage({ experiment: base, strategy: strategyFor(meanrevReport), selectedFilter: selected });
  assert.equal(positive.decision.paper_eligible, true);
  assert.equal(positive.decision.approval_claim, false);

  for (const mismatch of [
    { verdict: "INCONCLUSIVE" },
    { verdict_scope: "always_on" },
    { policy_id: "different-policy" },
    { mode: "demo" },
  ]) {
    const payload = buildStrategyReviewPackage({
      experiment: { ...base, ...mismatch },
      strategy: strategyFor(meanrevReport),
      selectedFilter: selected,
    });
    assert.equal(payload.decision.paper_eligible, false);
    assert.equal(payload.decision.approval_claim, false);
  }
});
