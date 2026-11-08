"use client";

import { ArrowRight, ChevronDown, CircleHelp, Download, LockKeyhole, TriangleAlert } from "lucide-react";
import { API_ROUTES } from "../../../../../packages/contracts/api";
import { canReviewPlan, comparisonSeries, selectedBaseline, verdictHeadline } from "./decision";
import ResearchChart from "./research-chart";
import CheckedFilters from "./checked-filters";
import KineticText from "./kinetic-text";
import { MascotCallout } from "./mascot";
import type { SharedResearchProps } from "./types";
import type { NativeEvaluation, TeamReport } from "../../../../../packages/contracts/research";
import "./comparison.css";

type ComparisonProps = SharedResearchProps & { onReview: () => void };

const percent = (value: number | null | undefined, digits = 1) => value === null || value === undefined ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
const ratio = (value: number | null | undefined, digits = 0) => value === null || value === undefined ? "—" : `${(value * 100).toFixed(digits)}%`;
const points = (value: number | null | undefined) => value === null || value === undefined ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)} p.p.`;
const number = (value: number | null | undefined) => value === null || value === undefined ? "—" : value.toLocaleString("en-GB", { maximumFractionDigits: 2 });
const hours = (value: number | null | undefined) => value === null || value === undefined ? "—" : `${value.toLocaleString("en-GB", { maximumFractionDigits: 1 })} h`;
const choiceList = (labels: string[]) => labels.length < 2 ? labels[0] || "the supplied choices" : labels.length === 2 ? `${labels[0]} or ${labels[1]}` : `${labels.slice(0, -1).join(", ")}, or ${labels[labels.length - 1]}`;
const interval = (values: [number, number] | null | undefined, formatter: (value: number) => string) => values ? `[${formatter(values[0])}, ${formatter(values[1])}]` : "—";
const fall = (value: number | null | undefined) => value === null || value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;

function ruleName(id: string, fallback: string) {
  if (id === "always_on") return "Strategy as-is";
  if (id === "agent_gate" || id === "proposed") return "Proposed rule";
  if (id === "simple_rule") return "Simple rule";
  if (id === "cash") return "Cash";
  return fallback;
}

function sealedOutcome(evaluation: NativeEvaluation) {
  const delta = evaluation.delta_net_return_vs_always_on;
  return {
    title: "Better than original. Still a loss.",
    body: `The sealed look is ${points(delta)} versus strategy as-is. The gate's own net-return range includes zero; the published KILL applies to strategy as-is only, and the arbiter was not rerun on the gate.`,
  };
}

function outcome(experiment: SharedResearchProps["experiment"]) {
  const sealed = experiment.frozen_evaluation?.evaluation;
  if (sealed) return sealedOutcome(sealed);
  const original = experiment.baselines.find(item => item.id === "always_on");
  const candidate = selectedBaseline(experiment);
  const headline = verdictHeadline(experiment.verdict);
  if (!original || !candidate) return { title: headline, body: experiment.recommendation || "The evaluator has not supplied an original and a selected rule for the same period." };
  const delta = candidate.net_return - original.net_return;
  const alternatives = experiment.baselines.filter(item => item.id === "always_on" || item.id === "cash" || item.id === "simple_rule");
  const alternativeLabels = alternatives.map(item => ruleName(item.id, item.name));
  const beaten = alternatives.filter(item => item.id !== candidate.id && candidate.net_return > item.net_return).map(item => ruleName(item.id, item.name));
  const baselineContext = alternatives.length > 0
    ? beaten.length === alternatives.length
      ? `It is ahead of ${choiceList(alternativeLabels)}.`
      : beaten.length === 0
        ? `Does not beat ${choiceList(alternativeLabels)}.`
        : `It is ahead of ${beaten.join(", ")}; keep the other choices visible.`
    : "Keep the supplied baselines visible while reviewing the result.";
  if (experiment.mode === "demo") return { title: "Illustrative comparison only.", body: `Proposed rule: ${points(delta)} vs strategy as-is on the recorded window. ${baselineContext} Illustrative only; not measured market performance.` };
  if (!experiment.policy.holdout_frozen || !experiment.policy.test_evaluated || experiment.mode !== "measured") return { title: headline, body: experiment.recommendation || `The proposed rule is ${points(delta)} versus strategy as-is, but the new-data test is not complete. ${baselineContext}` };
  if (candidate.id === "always_on" || candidate.id === original.id) return { title: headline, body: experiment.recommendation || "The evaluator kept the original strategy. No separate filter was selected." };
  const comparison = delta === 0 ? `${candidate.name} matched the original on this test.` : delta > 0 ? `${candidate.name} is ${points(delta)} versus the original after the recorded costs.` : `The original strategy was ${points(Math.abs(delta))} ahead of ${candidate.name} on this test.`;
  return { title: headline, body: experiment.recommendation || `${comparison} ${baselineContext}` };
}

function SealedLook({ evaluation }: { evaluation: NativeEvaluation }) {
  const gate = evaluation.metrics;
  const original = evaluation.always_on;
  return <section className="cmp-sealed-look" aria-labelledby="cmp-sealed-title">
    <div className="cmp-sealed-heading"><div><span className="eyebrow">SEALED LOOK</span><h3 id="cmp-sealed-title">What did the supplied gate actually show?</h3></div><span className="cmp-sealed-split">{evaluation.split}</span></div>
    <div className="cmp-sealed-grid">
      <div><span>Gate vs strategy as-is</span><strong>{points(evaluation.delta_net_return_vs_always_on)}</strong><small>90% interval {interval(evaluation.ci_delta, points)}</small></div>
      <div><span>Gate net return</span><strong>{percent(gate.net_return)}</strong><small>90% interval {interval(gate.ci_net_return, percent)}</small></div>
      <div><span>Largest fall</span><strong>{fall(gate.max_drawdown)}</strong><small>Strategy as-is: {fall(original.max_drawdown)}</small></div>
    </div>
    <p className="cmp-sealed-note"><TriangleAlert size={15} />The gate result is a recorded sealed look, not a new arbiter verdict. Keep the proposal provisional until an approved test answers the same question on unseen data.</p>
  </section>;
}

type DevelopmentRow = { id: string; label: string; netReturn: number; ci: [number, number] | null };

function recordedEvaluation(report: TeamReport, policyId: string) {
  for (const evidence of report.evidence) {
    if (evidence.tool !== "arbiter_evaluate") continue;
    const payload = evidence.payload as { evaluation?: unknown };
    const value = payload.evaluation;
    if (!value || typeof value !== "object") continue;
    const evaluation = value as { policy_id?: unknown; split?: unknown; metrics?: { net_return?: unknown; ci_net_return?: unknown } };
    if (evaluation.policy_id !== policyId || evaluation.split !== "validation") continue;
    const netReturn = evaluation.metrics?.net_return;
    const ci = evaluation.metrics?.ci_net_return;
    if (typeof netReturn !== "number") continue;
    const confidence = Array.isArray(ci) && ci.length === 2 && typeof ci[0] === "number" && typeof ci[1] === "number" ? [ci[0], ci[1]] as [number, number] : null;
    return { netReturn, ci: confidence };
  }
  return null;
}

function developmentRows(report: TeamReport | undefined): DevelopmentRow[] {
  if (!report || !report.validation_always_on || typeof report.validation_always_on.net_return !== "number") return [];
  const rows: DevelopmentRow[] = [{ id: "always_on", label: "Strategy as-is", netReturn: report.validation_always_on.net_return, ci: report.validation_always_on.ci_net_return }];
  const champion = report.champion_policy_id;
  if (champion) {
    const gate = recordedEvaluation(report, champion);
    if (gate) rows.push({ id: "proposed", label: "Proposed rule", netReturn: gate.netReturn, ci: gate.ci });
  }
  const simpleId = report.evidence.some(item => item.tool === "arbiter_evaluate" && (item.payload as { evaluation?: { policy_id?: unknown } }).evaluation && ((item.payload as { evaluation: { policy_id?: unknown } }).evaluation.policy_id === "rule::trend_up_and_vol_below_train_median"))
    ? "rule::trend_up_and_vol_below_train_median"
    : report.trial_log.find(item => item.split === "validation" && item.source === "rule_baseline")?.policy_id;
  if (simpleId) {
    const simple = recordedEvaluation(report, simpleId);
    if (simple) rows.push({ id: "simple_rule", label: "Simple rule", netReturn: simple.netReturn, ci: simple.ci });
  }
  if (typeof report.validation_cash_net_return === "number") rows.push({ id: "cash", label: "Cash", netReturn: report.validation_cash_net_return, ci: null });
  return rows;
}

function DevelopmentComparison({ report }: { report?: TeamReport }) {
  const rows = developmentRows(report);
  if (rows.length < 2) return null;
  return <details className="tr-development-comparison cmp-development-comparison"><summary>Development comparison <span>recorded validation</span><ChevronDown size={15} /></summary><div className="cmp-development-body"><p>Four supplied choices from the recorded validation stage. This table is separate from the sealed look and does not establish a new-data verdict.</p><table><caption className="kk-sr-only">Recorded validation comparison</caption><thead><tr><th scope="col">Approach</th><th scope="col">Net return</th><th scope="col">90% range</th></tr></thead><tbody>{rows.map(row => <tr key={row.id} className={row.id === "proposed" ? "cmp-proposed" : undefined}><th scope="row">{row.label}</th><td>{percent(row.netReturn, 2)}</td><td>{row.ci ? `[${percent(row.ci[0], 2)}, ${percent(row.ci[1], 2)}]` : "Not supplied"}</td></tr>)}</tbody></table></div></details>;
}

function WindowStrip({ windows, frozen }: { windows: SharedResearchProps["experiment"]["windows"]; frozen: boolean }) {
  const periodLabel = (value: string) => {
    if (!value || value === "pending" || value === "Recorded in native report") return "Exact dates not listed";
    if (value === "Sealed look attached; dates not supplied") return "Test recorded · dates not listed";
    if (value === "Not accessed") return "Test not opened";
    return value;
  };
  return <div className="cmp-window-strip" aria-label="Research data periods">
    <div><span>Training data</span><strong>{periodLabel(windows.train)}</strong><small>Patterns explored</small></div>
    <i aria-hidden="true" />
    <div><span>Validation data</span><strong>{periodLabel(windows.validation)}</strong><small>Candidate rules checked</small></div>
    <i aria-hidden="true" />
    <div className="cmp-window-test"><span>Held-out test</span><strong>{periodLabel(windows.test)}</strong><small>{frozen ? "Rule fixed first" : "No fixed rule yet"}</small></div>
  </div>;
}

export default function ComparisonView({ experiment, strategy, selectedDate, onSelectDate, onEvidence, onReview }: ComparisonProps) {
  const ready = experiment.status === "completed" && experiment.mode === "measured" && experiment.policy.holdout_frozen && experiment.policy.test_evaluated;
  const result = outcome(experiment);
  const sealedEvaluation = experiment.frozen_evaluation?.evaluation;
  const candidate = selectedBaseline(experiment);
  const chart = comparisonSeries(experiment);
  const hasComparisonChoices = candidate !== undefined && experiment.baselines.some(item => item.id === "always_on") && experiment.baselines.some(item => item.id === "cash") && experiment.baselines.some(item => item.id === "simple_rule");
  const canReview = canReviewPlan(experiment) && experiment.paper_eligible !== false;
  const showReviewButton = candidate !== undefined || sealedEvaluation !== undefined;
  const reviewLabel = experiment.mode === "demo" ? "Review example plan" : "Review paper test";
  const nextStep = experiment.verdict === "KILL" ? "Keep the original visible and inspect the failures before considering any practice plan." : experiment.verdict === "INCONCLUSIVE" ? "Not proven. A practice plan stays closed until a later test decides." : experiment.mode === "demo" ? "Measured evaluation still required; this plan is only a labelled rehearsal." : "Complete the new-data test before reviewing a paper test.";
  const mascotPose = ["KEEP", "CONDITIONAL"].includes(experiment.verdict) && ready && !sealedEvaluation ? "bull-compare" : "bear-point-right";
  const mascotTitle = sealedEvaluation ? "A smaller loss is still a loss." : ready ? "Compare the unseen window." : "Keep the test in view.";
  return <section className="cmp-view" aria-labelledby="cmp-title">
    <header className="cmp-heading">
      <div><span className="eyebrow">COMPARE THE RULE</span><h1 id="cmp-title"><KineticText trigger="mount">Is the rule better?</KineticText></h1></div>
    </header>
    <section className="cmp-reading" aria-labelledby="cmp-reading-title">
      <div className="cmp-reading-copy">
        <p className="cmp-result-line" id="cmp-reading-title" data-guide-target="compare-conclusion"><strong>{result.title}</strong> {result.body}</p>
        {showReviewButton ? <button className="kk-action cmp-primary kk-primary-button" type="button" onClick={onReview}>{canReview ? reviewLabel : "Review approval requirements"} <ArrowRight size={16} /></button> : <span className="cmp-next"><LockKeyhole size={15} />{nextStep}</span>}
      </div>
      <MascotCallout pose={mascotPose} title={mascotTitle} className="cmp-annotation">
        {sealedEvaluation ? "The filter helped in this test. It still needs its own decision before a paper plan." : ready ? "The held-out dates are the useful check." : "A pattern can guide the next question without settling it."}
      </MascotCallout>
    </section>
    <section className="cmp-plot-section" aria-label="Strategy comparison" data-guide-target="compare-chart">
      <p className="cmp-chart-note">{sealedEvaluation ? "No equity curve was supplied for this sealed look; the recorded metrics stay visible below." : experiment.equity.length > 0 && hasComparisonChoices ? "Same supplied dates, four choices: strategy as-is, proposed rule, simple rule and cash." : "No supplied comparison series are available yet."}</p>
      {sealedEvaluation ? <SealedLook evaluation={sealedEvaluation} /> : experiment.equity.length > 0 ? <ResearchChart data={experiment.equity} series={chart.series} seriesLabels={chart.labels} selectedDate={selectedDate} onSelectDate={onSelectDate} label="Is the rule better?" mode={experiment.mode} height={440} reveal /> : <div className="cmp-empty"><TriangleAlert size={18} /><span>No comparison curve is available yet.</span></div>}
    </section>
    <CheckedFilters experiment={experiment} strategy={strategy} onEvidence={onEvidence} />
    <details className="cmp-details-disclosure" aria-labelledby="cmp-detail-title"><summary id="cmp-detail-title"><CircleHelp size={16} />Comparison details</summary><div className="cmp-detail-section">
      <WindowStrip windows={experiment.windows} frozen={experiment.policy.holdout_frozen} />
      <DevelopmentComparison report={experiment.native_report} />
      <div className="cmp-section-heading cmp-detail-heading"><div><h2><KineticText trigger="scroll">How did each rule compare?</KineticText></h2><p>Values supplied by the evaluator; the browser does not recalculate returns or risk.</p></div><a className="kk-secondary" href={API_ROUTES.experimentReport(experiment.experiment_id)} download><Download size={15} />Download report</a></div>
      {experiment.baselines.length > 0 ? <div className="cmp-table-wrap"><table className="cmp-table"><caption className="kk-sr-only">Comparison metrics</caption><thead><tr><th>Approach</th><th>Return</th><th>Sharpe</th><th>Sortino</th><th>5% CVaR</th><th>Holding</th><th>Largest fall</th><th>Exposure</th><th>Turnover</th><th>Trades</th></tr></thead><tbody>{experiment.baselines.map(item => { const detail = item as typeof item & { sortino?: number | null; cvar_05?: number | null; avg_holding_bars?: number | null; holding_hours?: number | null }; return <tr key={item.id} className={item.id === candidate?.id ? "cmp-proposed" : undefined}><th scope="row">{ruleName(item.id, item.name)}</th><td>{percent(item.net_return)}</td><td>{number(item.sharpe)}</td><td>{number(detail.sortino)}</td><td>{percent(detail.cvar_05)}</td><td>{hours(detail.holding_hours ?? detail.avg_holding_bars)}</td><td>{percent(item.max_drawdown)}</td><td>{ratio(item.exposure)}</td><td>{item.turnover == null ? "—" : `${number(item.turnover)}×`}</td><td>{item.trades == null ? "—" : item.trades.toLocaleString("en-GB")}</td></tr>; })}</tbody></table></div> : <p className="cmp-detail-empty">Only the sealed metrics supplied by the evaluator are available here. No equity curve or baseline table was attached.</p>}
      <div className="cmp-explainer"><div><p><strong>Return</strong> is the gain or loss after the costs supplied for this run.</p><p><strong>Sharpe</strong> relates return to variability; a short history is not proof. <strong>Sortino</strong> uses only the downside.</p><p><strong>5% CVaR</strong> is the average of the worst 5% of hourly bars. <strong>Holding</strong> is the average time a position stays on.</p><p><strong>Largest fall</strong> is the biggest drop from a previous high. This report supplies the aggregate value, not a separate drawdown time series.</p><p><strong>Exposure and turnover</strong> describe how much capital was active and how much was traded.</p></div></div>
      <aside className="cmp-limitations" aria-label="Comparison limitations"><TriangleAlert size={16} /><p>{experiment.limitations.length ? experiment.limitations.join(" ") : "Keep the tested period, costs, and rule definition attached to this comparison."}</p></aside>
    </div></details>
  </section>;
}
