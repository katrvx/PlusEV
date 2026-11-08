// Part C interface v1. Financial metrics arrive from the API; the UI only formats them.
import type { FrozenEvaluation, NativeStrategyHealth, TeamReport } from "./research";
export type ImportKind = "positions" | "trades";
export type StrategyDefinitionFamily = "ema_crossover" | "rsi_mean_reversion";
export type StrategyDefinitionTimeframe = "1m" | "5m" | "15m" | "1h" | "4h" | "1d";
export type StrategyDefinitionRule = (
  | { family: "ema_crossover"; fast_period: number; slow_period: number }
  | { family: "rsi_mean_reversion"; period: number; entry_below: number; exit_above: number }
) & { long_position: number; flat_position: number };
export type StrategyDefinition = {
  schema_version: "1";
  name: string;
  symbol: string;
  timeframe: StrategyDefinitionTimeframe;
  strategy_version: string;
  rule: StrategyDefinitionRule;
  period: { start: string | null; end: string | null };
  market_data: { source: "awaiting_upload"; upload_id: null };
  costs: { timezone: string; fee_bps: number; slippage_bps: number; execution: "next_bar_open" };
  description: string;
};
export type Strategy = {
  strategy_id: string; name: string; symbol: string; timeframe: string;
  strategy_version: string; source: string; kind: ImportKind;
  status: "demo" | "ready" | "diagnosis_only" | "draft";
  /** Optional provenance flags for read-only examples and future adapters. */
  synthetic?: boolean;
  original_dataset_available?: boolean;
  readiness?: "awaiting_market_data" | "ready";
  execution_status?: "definition_saved" | "awaiting_engine" | "generated";
  row_count: number; date_start: string; date_end: string;
  dataset_hash: string; created_at: string;
  market_data_hash?: string | null;
  definition_hash?: string;
  definition_schema_version?: "1";
  definition_path?: string;
  definition?: StrategyDefinition;
  assumptions: { timezone: string; fee_bps: number | null; slippage_bps: number | null; execution: string; description: string };
};
export type ValidationIssue = { severity: "error" | "warning"; code: string; message: string; row?: number };
export type ImportPreview = {
  upload_id: string; filename: string; columns: string[];
  rows: Record<string, string | number | null>[]; row_count: number;
  suggested_mapping: Record<string, string>; detected_kind: ImportKind;
  issues: ValidationIssue[];
};
export type ImportRequest = {
  upload_id: string; name: string; symbol: string; timeframe: string;
  strategy_version: string; kind: ImportKind; mapping: Record<string, string>;
  timezone: string; fee_bps: number; slippage_bps: number; description: string;
};
export type ImportResult = { strategy: Strategy | null; issues: ValidationIssue[]; valid: boolean };
export type StrategyDefinitionResult = {
  strategy: Strategy | null;
  definition: StrategyDefinition | null;
  definition_hash: string | null;
  issues: ValidationIssue[];
  valid: boolean;
};
export type Metric = { label: string; value: number | null; format: "percent" | "number" | "integer"; description: string };
export type Baseline = {
  id: string; name: string; net_return: number; sharpe: number | null; max_drawdown: number | null;
  exposure: number | null; turnover: number | null; trades: number | null;
  sortino?: number | null; cvar_05?: number | null; avg_holding_bars?: number | null; holding_hours?: number | null;
};
export type EquityPoint = { date: string; base: number; rule: number; proposed: number; cash: number };
export type Regime = { id: string; trend: string; volatility: string; net_return: number; trades: number; confidence_low: number; confidence_high: number; evidence_id: string; label?: string };
export type Evidence = {
  id: string; title: string; kind: string; summary: string; source: string; window: string;
  facts: { label: string; value: string }[];
  args?: Record<string, unknown>;
  output?: Record<string, unknown>;
};
export type ResearchStep = { id: string; role: string; action: string; title: string; body: string; status: "complete" | "rejected" | "running" | "pending"; tool: string; evidence_ids: string[]; timestamp: string };
export type Hypothesis = { id: string; title: string; status: "supported" | "rejected" | "inconclusive"; finding: string; evidence_ids: string[] };
export type Experiment = {
  experiment_id: string; strategy_id: string;
  status: "queued" | "running" | "completed" | "awaiting_engine" | "failed";
  mode: "demo" | "measured" | "pending"; progress: number; message: string;
  /** Optional provenance/eligibility metadata; absent on legacy records. */
  source?: string;
  synthetic?: boolean;
  native_report_available?: boolean;
  paper_eligible?: boolean;
  native_report?: TeamReport;
  native_source_path?: string;
  strategy_health?: NativeStrategyHealth;
  frozen_evaluation?: FrozenEvaluation;
  verdict_scope?: "always_on" | "candidate";
  verdict_source_path?: string;
  created_at: string; policy_id: string; dataset_hash: string;
  windows: { train: string; validation: string; test: string };
  metrics: Metric[]; baselines: Baseline[]; equity: EquityPoint[]; regimes: Regime[];
  evidence: Evidence[]; steps: ResearchStep[]; hypotheses: Hypothesis[];
  verdict: "KEEP" | "MODIFY" | "COMBINE" | "RESTRICT" | "MONITOR" | "KILL" | "INCONCLUSIVE" | "CONDITIONAL" | "REDUCE";
  recommendation: string; limitations: string[];
  policy: { description: string; conditions: string[]; holdout_frozen: boolean; test_evaluated: boolean };
};
export type PaperPlanSnapshot = {
  strategy_id: string;
  dataset_hash: string;
  policy_id: string;
  windows: { train: string; validation: string; test: string };
  policy: { description: string; conditions: string[]; holdout_frozen: boolean; test_evaluated: boolean };
  assumptions: Partial<Strategy["assumptions"]>;
};
export type PaperShadow = {
  interval: "1h";
  horizon_bars: number;
  horizon_days: number;
  fills_recorded: number;
  conclusion: "INCONCLUSIVE" | "MONITOR" | null;
  message: string;
};
export type PaperPlan = {
  paper_test_id: string; experiment_id: string;
  status: "planned" | "awaiting_bars" | "running" | "completed";
  duration_days: number; approved_at: string; policy_id: string; mode: "demo" | "measured";
  snapshot?: PaperPlanSnapshot;
  shadow?: PaperShadow;
  message?: string;
};
export type Health = { status: string; research_engine: boolean; version: string };
