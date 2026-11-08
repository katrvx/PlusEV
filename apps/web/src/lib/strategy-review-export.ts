import type { Experiment, Strategy } from "../../../../packages/contracts/types";

export type StrategyReviewFilterExport = {
  policyId: string | null;
  /** Representative ID plus alternate IDs that share the same recorded spec hash. */
  policyIds?: string[];
  specHash?: string | null;
  policySpec?: Record<string, unknown> | null;
  status: string;
  historicalSelection: boolean;
  evidenceIds?: string[];
  reasons?: string[];
  trialRows?: unknown[];
};

export type StrategyReviewPackageInput = {
  experiment: Experiment;
  strategy: Strategy;
  selectedFilter?: StrategyReviewFilterExport;
};

export type StrategyReviewPackage = {
  package_type: "strategy review package";
  package_version: "1";
  generated_at: string;
  runnable: false;
  execution_claim: "none";
  original_strategy_identity: Record<string, unknown>;
  original_strategy_definition: Strategy["definition"] | null;
  strategy_record: Strategy;
  experiment_record: Experiment;
  report_decision_scope: string;
  decision: {
    status: string;
    historical_selection: boolean;
    paper_eligible: boolean;
    paper_eligible_supplied: boolean;
    approval_claim: false;
    approval_status: "not approved";
    note: string;
  };
  selected_filter: StrategyReviewFilterExport | null;
  frozen_evidence: Experiment["frozen_evaluation"] | null;
  native_report: Experiment["native_report"] | null;
};

function copy<T>(value: T): T {
  if (value === undefined || value === null) return value;
  return JSON.parse(JSON.stringify(value)) as T;
}

export function buildStrategyReviewPackage({ experiment, strategy, selectedFilter }: StrategyReviewPackageInput): StrategyReviewPackage {
  const selected = selectedFilter ? copy(selectedFilter) : null;
  const selectedId = selected?.policyId ?? null;
  const frozen = experiment.frozen_evaluation;
  const frozenMatches = Boolean(
    selectedId
      && frozen
      && frozen.experiment_id === experiment.experiment_id
      && frozen.strategy_id === strategy.strategy_id
      && frozen.evaluation.policy_id === selectedId,
  );

  const suppliedPaperEligible = experiment.paper_eligible === true;
  const selectedPolicyMatches = Boolean(selectedId && selectedId === experiment.policy_id);
  const measuredGate = experiment.mode === "measured"
    && experiment.status === "completed"
    && experiment.synthetic !== true
    && strategy.synthetic !== true
    && experiment.policy.holdout_frozen
    && experiment.policy.test_evaluated;
  const explicitCandidateVerdict = experiment.verdict === "KEEP"
    && experiment.verdict_scope === "candidate"
    && selectedPolicyMatches;
  const paperEligible = suppliedPaperEligible && measuredGate && explicitCandidateVerdict;

  return {
    package_type: "strategy review package",
    package_version: "1",
    generated_at: new Date().toISOString(),
    runnable: false,
    execution_claim: "none",
    original_strategy_identity: copy({
      strategy_id: strategy.strategy_id,
      name: strategy.name,
      symbol: strategy.symbol,
      timeframe: strategy.timeframe,
      strategy_version: strategy.strategy_version,
      source: strategy.source,
      kind: strategy.kind,
      dataset_hash: strategy.dataset_hash,
      definition_hash: strategy.definition_hash ?? null,
      definition_schema_version: strategy.definition_schema_version ?? null,
      definition_path: strategy.definition_path ?? null,
    }),
    original_strategy_definition: copy(strategy.definition ?? null),
    strategy_record: copy(strategy),
    experiment_record: copy(experiment),
    report_decision_scope: experiment.verdict_scope ?? (experiment.native_report ? "candidate" : "legacy experiment"),
    decision: {
      status: selected?.status ?? "No filter selected",
      historical_selection: selected?.historicalSelection ?? false,
      paper_eligible: paperEligible,
      paper_eligible_supplied: typeof experiment.paper_eligible === "boolean",
      approval_claim: false,
      approval_status: "not approved",
      note: "A strategy review package preserves recorded research; it is not a runnable bot and does not approve a paper or live plan.",
    },
    selected_filter: selected,
    frozen_evidence: frozenMatches ? copy(frozen) : null,
    native_report: copy(experiment.native_report ?? null),
  };
}

export function downloadStrategyReviewPackage(input: StrategyReviewPackageInput): StrategyReviewPackage {
  const payload = buildStrategyReviewPackage(input);
  if (typeof document === "undefined" || typeof URL === "undefined" || typeof URL.createObjectURL !== "function") return payload;

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const strategyId = input.strategy.strategy_id.replace(/[^a-z0-9_-]+/gi, "-");
  const experimentId = input.experiment.experiment_id.replace(/[^a-z0-9_-]+/gi, "-");
  anchor.href = url;
  anchor.download = `strategy-review-${strategyId}-${experimentId}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
  return payload;
}
