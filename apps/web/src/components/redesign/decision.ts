import type { ChartSeries, Experiment } from "./types";

const BLOCKED = new Set<Experiment["verdict"]>(["KILL", "INCONCLUSIVE"]);

export function verdictLabel(verdict: Experiment["verdict"]) {
  if (verdict === "CONDITIONAL" || verdict === "MODIFY") return "Activate conditionally";
  if (verdict === "REDUCE" || verdict === "RESTRICT") return "Reduce";
  if (verdict === "COMBINE") return "Combine";
  if (verdict === "MONITOR") return "Monitor";
  if (verdict === "INCONCLUSIVE") return "Not proven";
  if (verdict === "KEEP") return "Keep";
  if (verdict === "KILL") return "Kill";
  return verdict;
}

export function verdictHeadline(verdict: Experiment["verdict"]) {
  if (verdict === "CONDITIONAL" || verdict === "MODIFY") return "Activate it only where it holds up.";
  if (verdict === "KEEP") return "Keep the strategy.";
  if (verdict === "KILL") return "Kill the strategy.";
  if (verdict === "REDUCE" || verdict === "RESTRICT") return "Reduce size where the risk cap allows it.";
  if (verdict === "COMBINE") return "Combine it with the paired book.";
  if (verdict === "MONITOR") return "Monitor it before changing.";
  if (verdict === "INCONCLUSIVE") return "Not proven.";
  return "More evidence is needed before deciding.";
}

/** The line the arbiter froze. Demo fixtures use an illustrative id, so they fall back to the agent gate. */
export function selectedBaseline(experiment: Experiment) {
  return experiment.baselines.find(item => item.id === experiment.policy_id)
    ?? experiment.baselines.find(item => item.id === "agent_gate" || item.id === "proposed");
}

export function canReviewPlan(experiment: Experiment) {
  const selected = selectedBaseline(experiment);
  if (!selected || BLOCKED.has(experiment.verdict)) return false;
  const frozen = experiment.status === "completed" && experiment.policy.holdout_frozen && experiment.policy.test_evaluated;
  if (experiment.mode === "measured") return frozen;
  return experiment.mode === "demo" && frozen;
}

export function comparisonSeries(experiment: Experiment): { series: ChartSeries[]; labels: Partial<Record<ChartSeries, string>> } {
  const selected = selectedBaseline(experiment);
  const simple = experiment.baselines.find(item => item.id === "simple_rule");
  const labels: Partial<Record<ChartSeries, string>> = { rule: simple?.name ?? "Simple trend / vol rule" };
  if (!selected || selected.id === "always_on" || selected.id === "cash") return { series: ["base", "cash"], labels };
  if (selected.id === "simple_rule") return { series: ["base", "proposed", "cash"], labels: { ...labels, proposed: selected.name } };
  return { series: ["base", "rule", "proposed", "cash"], labels: { ...labels, proposed: selected.name } };
}
