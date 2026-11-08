// Part C interface v1. Financial metrics arrive from the API; the UI only formats them.
export type ImportKind = "positions" | "trades";
export type Strategy = {
  strategy_id: string; name: string; symbol: string; timeframe: string;
  strategy_version: string; source: string; kind: ImportKind;
  status: "demo" | "ready" | "diagnosis_only";
  row_count: number; date_start: string; date_end: string;
  dataset_hash: string; created_at: string;
  assumptions: { timezone: string; fee_bps: number; slippage_bps: number; execution: string; description: string };
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
export type Metric = { label: string; value: number | null; format: "percent" | "number" | "integer"; description: string };
export type Baseline = {
  id: string; name: string; net_return: number; sharpe: number; max_drawdown: number;
  exposure: number; turnover: number; trades: number;
  sortino?: number | null; cvar_05?: number | null; avg_holding_bars?: number | null; holding_hours?: number | null;
};
export type EquityPoint = { date: string; base: number; rule: number; proposed: number; cash: number };
export type Regime = { id: string; trend: string; volatility: string; net_return: number; trades: number; confidence_low: number; confidence_high: number; evidence_id: string; label?: string };
export type Evidence = { id: string; title: string; kind: string; summary: string; source: string; window: string; facts: { label: string; value: string }[] };
export type ResearchStep = { id: string; role: string; action: string; title: string; body: string; status: "complete" | "rejected" | "running" | "pending"; tool: string; evidence_ids: string[]; timestamp: string };
export type Hypothesis = { id: string; title: string; status: "supported" | "rejected" | "inconclusive"; finding: string; evidence_ids: string[] };
export type Experiment = {
  experiment_id: string; strategy_id: string;
  status: "queued" | "running" | "completed" | "awaiting_engine" | "failed";
  mode: "demo" | "measured" | "pending"; progress: number; message: string;
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
