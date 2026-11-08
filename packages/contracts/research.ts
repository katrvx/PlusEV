/** Native Lane B investigation report shape consumed by Part C. */
export type AgentMode = "llm" | "llm_with_fallback" | "deterministic_fallback";

export type NativeStrategyHealth = {
  status: string;
  summary: string;
  changed_assumptions: string[];
  train_range: { low: number; high: number; horizon_bars: number; horizon_days: number; source: string };
  validation_blocks: { start: string; net_return: number; position: "inside" | "below" | "above" }[];
  n_blocks: number;
  n_below: number;
  n_above: number;
  validation_net_return: number;
  checks: { assumption: string; train: number | Record<string, number>; validation: number | Record<string, number>; ratio?: number; total_variation?: number; changed: boolean; note: string }[];
  evidence_id: string;
};

export type NativeMetrics = {
  net_return: number; sharpe: number; sortino: number; max_drawdown: number;
  turnover: number; n_switches: number; exposure: number; ci_net_return: [number, number];
  cvar_05?: number; avg_holding_bars?: number;
};
export type NativeEvaluation = {
  policy_id: string; split: string; metrics: NativeMetrics; always_on: NativeMetrics;
  delta_net_return_vs_always_on: number; ci_delta: [number, number];
  allocation_mix: Record<string, number>; n_decisions: number; n_in_position: number;
  fold: number | null; audit_id: string;
};
export type FrozenEvaluation = {
  what: string; experiment_id: string; strategy_id: string;
  champion_policy_id: string; champion_spec_hash: string; selected_in_report: string;
  report_committed_before_look: string; looked_at: string; evaluation: NativeEvaluation;
};

export type TeamEvidence = {
  evidence_id: string;
  tool: string;
  args: Record<string, unknown>;
  payload: Record<string, unknown>;
  created_at: string;
};
export type TeamHypothesis = {
  hypothesis_id: string;
  statement: string;
  direction: "works_better" | "works_worse";
  conditions: string[];
  evidence_ids: string[];
  confidence: "low" | "medium" | "high";
  caveats: string[];
  suggested_test: string;
};
export type TeamProposal = {
  proposal_id: string;
  family: string;
  based_on: string[];
  conditions: { feature: string; op: "<=" | ">"; threshold: number }[];
  allocation_when_true: number;
  allocation_when_false: number;
  rationale: string;
  evidence_ids: string[];
  falsification_test: string;
};
export type TeamTrial = {
  policy_id: string;
  spec_hash?: string | null;
  source: "agent" | "arbiter" | "rule_baseline" | "meta_model";
  split: "train" | "validation" | "test";
  delta_net_return_vs_always_on: number | null;
  ci_delta: [number, number] | null;
  allocation_mix?: Record<string, number>;
  evidence_id: string | null;
  status: "evaluated" | "refused" | "error";
  note: string;
  net_return?: number | null;
  /** Walk-forward train fold (arbiter stability check); null for every policy attempt. */
  fold?: number | null;
};
/** One finding of agent 4 (market sentiment around the best and worst training weeks). */
export type TeamContextFinding = {
  finding_id: string;
  statement: string;
  episode_ids?: string[];
  evidence_ids: string[];
  tally?: string | null;
  strength: "none" | "weak" | "moderate";
  caveats?: string[];
};
export type TeamContext = { summary: string; findings: TeamContextFinding[]; limitations?: string[] };
export type TeamCandidate = {
  policy_id: string;
  spec_hash?: string | null;
  source: "agent" | "rule_baseline" | "meta_model";
  role?: "agent_champion" | "agent_not_selected" | "competitor";
  policy_spec: Record<string, unknown>;
  status: "accepted_for_frozen_test" | "rejected" | "competitor";
  validation_delta_vs_always_on?: number | null;
  validation_ci?: [number, number] | null;
  validation_delta_vs_simple_rule?: number | null;
  allocation_mix?: Record<string, number>;
  reasons: string[];
  evidence_ids: string[];
};
export type TeamReport = {
  experiment_id: string;
  strategy_id: string;
  generated_at: string;
  agent_mode: AgentMode;
  model_id: string | null;
  agent_failures?: string[];
  verdict?: "candidate_for_frozen_test" | "INCONCLUSIVE";
  champion_policy_id?: string | null;
  verdict_basis?: string[];
  strategy_health?: NativeStrategyHealth | null;
  validation_always_on?: Pick<NativeMetrics, "net_return" | "ci_net_return">;
  validation_cash_net_return?: number;
  context?: TeamContext | null;
  diagnostic: {
    summary: string;
    hypotheses: TeamHypothesis[];
    rejected_explanations: string[];
    limitations: string[];
  };
  proposals: TeamProposal[];
  critiques: { proposal_id: string; verdict: string; leakage_concerns: string[]; overfit_risks: string[]; fragile_samples: string[]; counterexamples: string[]; evidence_ids: string[] }[];
  trial_log: TeamTrial[];
  candidates: TeamCandidate[];
  test_requests: string[];
  limitations: string[];
  evidence: TeamEvidence[];
  n_distinct_agent_policies?: number;
  n_policies_tried: number;
  holdout_accessed: boolean;
};
export type TeamLookMetrics = {
  net_return: number;
  max_drawdown: number;
  sharpe?: number;
  exposure?: number;
  ci_net_return?: [number, number] | null;
  [key: string]: unknown;
};
/** One pre-registered look at the test window (experiments/frozen_look_<strategy_id>.json), served as `frozen_look`. */
export type TeamFrozenLook = {
  what?: string;
  experiment_id: string;
  strategy_id: string;
  champion_policy_id?: string | null;
  looked_at?: string;
  evaluation: {
    policy_id?: string;
    split: "train" | "validation" | "test";
    metrics: TeamLookMetrics;
    always_on: TeamLookMetrics;
    delta_net_return_vs_always_on: number | null;
    ci_delta: [number, number] | null;
    allocation_mix?: Record<string, number>;
  };
};
/**
 * Plain-language view of one report (packages/research_agents/presentation.py).
 * Built by code from the report; it adds no numbers and no decisions.
 * Every `_pp` field is a fraction: 0.273 means +27.3 percentage points (pp).
 * Returns, drawdowns and sizes are fractions too: -0.289 means -28.9%.
 */
export type PresentationStageName = "Training" | "Validation" | "Held-out test";
export type PresentationOutcome = "rejected" | "not_run" | "selected_for_further_testing" | "approved" | "reference";
export type PresentationHeadline = {
  finding: string;
  meaning: string;
  next_action: string;
  verdict?: string | null;
  verdict_label: string;
  verdict_scope?: string | null;
  verdict_source?: string | null;
};
export type PresentationStage = {
  stage: PresentationStageName | string;
  window?: string | null;
  what_happened: string;
  result: string;
  evidence_ids: string[];
};
export type PresentationHeldOut = {
  looked_at?: string | null;
  vs_original_pp?: number | null;
  vs_original_ci_pp?: [number, number] | null;
  own_return?: number | null;
  original_return?: number | null;
  max_drawdown?: number | null;
  original_max_drawdown?: number | null;
  summary: string;
  source?: string | null;
};
/** Did the filter choose WHEN, or just hold less? Validation, identical costs. A diagnostic, not the selection rule. */
export type PresentationTiming = {
  vs_half_size_pp?: number | null;
  vs_same_average_size_pp?: number | null;
  /** Constant size equal to the filter's average Training size. */
  same_average_size?: number | null;
  vs_validation_size_pp?: number | null;
  validation_size?: number | null;
  size_note?: string | null;
  read: string;
  source: string;
};
export type PresentationFilter = {
  policy_id: string;
  label: string;
  plain_rule: string;
  exposure_change: string;
  proposed_by: string;
  stages_checked: string[];
  outcome: PresentationOutcome;
  outcome_label: string;
  reason: string;
  validation_vs_original_pp?: number | null;
  validation_vs_original_ci_pp?: [number, number] | null;
  validation_own_return?: number | null;
  average_size_on_validation?: number | null;
  held_out?: PresentationHeldOut | null;
  /** Agent filters only, when a timing check was recorded. */
  timing?: PresentationTiming | null;
  details: string[];
  spec: Record<string, unknown>;
  evidence_ids: string[];
};
export type PresentationTraceItem = {
  step: number;
  actor: string;
  actor_kind: "AI agent" | "Code";
  action: "proposed" | "checked" | "challenged" | "decided";
  title: string;
  summary: string;
  items: string[];
  changed_conclusion?: string | null;
  evidence_ids: string[];
};
export type PresentationStrategy = {
  strategy_id: string;
  what_we_have: "definition" | "positions_and_reference" | "positions_only";
  name?: string | null;
  rule?: string | null;
  parameters?: Record<string, unknown> | null;
  source?: string | null;
  runnable_code_included: boolean;
  note: string;
};
export type PresentationSelectedFilter = {
  policy_id: string;
  label: string;
  plain_rule: string;
  status: string;
  spec: Record<string, unknown>;
};
export type PresentationEvidenceRef = { label: string; path?: string | null; evidence_id?: string | null };
export type PresentationTakeaway = {
  strategy: PresentationStrategy;
  selected_filter?: PresentationSelectedFilter | null;
  selected_filter_note?: string | null;
  evidence: PresentationEvidenceRef[];
  plans: string;
};
export type PresentationFilterCounts = Partial<Record<PresentationOutcome, number>>;
export type ReportPresentation = {
  version?: number;
  headline: PresentationHeadline;
  stages: PresentationStage[];
  filters: PresentationFilter[];
  filter_counts: PresentationFilterCounts;
  trace: PresentationTraceItem[];
  takeaway: PresentationTakeaway;
  glossary: { term: string; meaning: string }[];
  generated_by?: string;
};
export type InvestigationWrapper = {
  source: "team_artifact" | "bundled_lane_b_fixture";
  synthetic: boolean;
  source_path: string;
  report: TeamReport;
  /** Optional: the one pre-registered test-window look for this exact report. */
  frozen_look?: TeamFrozenLook | null;
  /** Optional plain-language view; null or absent for reports it cannot describe. */
  presentation?: ReportPresentation | null;
};
export type InvestigationSummary = {
  experiment_id: string;
  strategy_id: string;
  generated_at: string;
  agent_mode: AgentMode;
  model_id: string | null;
  holdout_accessed: boolean;
  source: InvestigationWrapper["source"];
  synthetic: boolean;
  source_path: string;
  diagnostic_summary: string;
  hypothesis_count: number;
  proposal_count: number;
  trial_count: number;
  evidence_count: number;
  n_policies_tried: number;
  /** Optional: the plain-language finding and verdict label. */
  headline?: Pick<PresentationHeadline, "finding" | "verdict_label"> | null;
  /** Optional: how many checked filters ended in each outcome. */
  filter_counts?: PresentationFilterCounts | null;
};
