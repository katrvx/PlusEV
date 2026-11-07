"use client";

import { ArrowRight, CircleHelp, Download, LockKeyhole, TriangleAlert } from "lucide-react";
import { API_ROUTES } from "../../../../../packages/contracts/api";
import ResearchChart from "./research-chart";
import type { SharedResearchProps } from "./types";
import "./comparison.css";

type ComparisonProps = SharedResearchProps & { onReview: () => void };

const percent = (value: number | null | undefined, digits = 1) => value === null || value === undefined ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
const ratio = (value: number | null | undefined, digits = 0) => value === null || value === undefined ? "—" : `${(value * 100).toFixed(digits)}%`;
const points = (value: number | null | undefined) => value === null || value === undefined ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)} p.p.`;
const number = (value: number | null | undefined) => value === null || value === undefined ? "—" : value.toLocaleString("en-GB", { maximumFractionDigits: 2 });

function ruleName(id: string, fallback: string) {
  if (id === "always_on") return "Original strategy";
  if (id === "agent_gate") return "Suggested filter";
  if (id === "simple_rule") return "Simple rule";
  if (id === "cash") return "Cash";
  return fallback;
}

function outcome(experiment: SharedResearchProps["experiment"]) {
  const original = experiment.baselines.find(item => item.id === "always_on");
  const candidate = experiment.baselines.find(item => item.id === "agent_gate" || item.id === "proposed");
  if (!original || !candidate) return { title: "The comparison is not ready yet.", body: "The evaluator has not supplied an original and filtered result for the same period." };
  const delta = candidate.net_return - original.net_return;
  if (experiment.mode === "demo") return { title: "Illustrative comparison only.", body: `The example filter is ${points(delta)} versus the original strategy on the recorded test window. It is a workflow example, not measured market performance.` };
  if (!experiment.policy.holdout_frozen || !experiment.policy.test_evaluated || experiment.mode !== "measured") return { title: "A pattern worth testing, not a conclusion.", body: `The filtered result is ${points(delta)} versus the original, but the new-data test is not complete.` };
  if (delta > 0) return { title: "The filter improved this unseen comparison.", body: `The suggested filter is ${points(delta)} versus the original strategy after the recorded costs. Review the assumptions before a paper test.` };
  if (delta < 0) return { title: "The filter did not improve this unseen comparison.", body: `The original strategy was ${points(Math.abs(delta))} ahead of the suggested filter on this test. Keep the original visible and inspect the failures.` };
  return { title: "The two approaches were effectively level.", body: "The new-data test did not show a clear improvement from the suggested filter." };
}

function WindowStrip({ windows, frozen }: { windows: SharedResearchProps["experiment"]["windows"]; frozen: boolean }) {
  return <div className="cmp-window-strip" aria-label="Chronological research windows">
    <div><span>Learn</span><strong>{windows.train}</strong><small>Patterns explored</small></div>
    <i aria-hidden="true" />
    <div><span>Choose</span><strong>{windows.validation}</strong><small>Rule selected</small></div>
    <i aria-hidden="true" />
    <div className="cmp-window-test"><span>Unseen test</span><strong>{windows.test}</strong><small>{frozen ? "Rule fixed first" : "Awaiting a fixed rule"}</small></div>
  </div>;
}

export default function ComparisonView({ experiment, strategy, selectedDate, onSelectDate, onReview }: ComparisonProps) {
  const ready = experiment.mode === "measured" && experiment.policy.holdout_frozen && experiment.policy.test_evaluated;
  const result = outcome(experiment);
  const candidate = experiment.baselines.find(item => item.id === "agent_gate" || item.id === "proposed");
  const demoPlanReady = experiment.mode === "demo" && experiment.status === "completed" && experiment.policy.holdout_frozen && experiment.policy.test_evaluated && candidate !== undefined;
  const canReview = candidate !== undefined && (ready || demoPlanReady) && experiment.verdict !== "KILL";
  const reviewLabel = experiment.mode === "demo" ? "Review example plan" : "Review paper test";
  const nextStep = experiment.verdict === "KILL" ? "Keep the original visible and inspect the failures before considering any practice plan." : experiment.mode === "demo" ? "Measured evaluation still required; this plan is only a labelled rehearsal." : "Complete the new-data test before reviewing a paper test.";
  return <section className="cmp-view" aria-labelledby="cmp-title">
    <header className="cmp-heading">
      <div><h1 id="cmp-title">Does the filter help?</h1><p>{strategy.name}</p></div>
      <span className={`cmp-basis ${ready ? "measured" : "illustrative"}`}>{ready ? "Measured unseen history" : experiment.mode === "demo" ? "Illustrative example" : "Comparison pending"}</span>
    </header>
    <section className="cmp-plot-section" aria-label="Strategy comparison">
      {experiment.equity.length > 0 ? <ResearchChart data={experiment.equity} series={["base", "rule", "proposed", "cash"]} selectedDate={selectedDate} onSelectDate={onSelectDate} label="Original vs filtered" mode={experiment.mode} height={440} reveal /> : <div className="cmp-empty"><TriangleAlert size={18} /><span>No comparison curve is available yet.</span></div>}
    </section>
    <section className="cmp-reading" aria-labelledby="cmp-reading-title">
      <p className="cmp-result-line" id="cmp-reading-title"><strong>{result.title}</strong> {result.body}</p>
      {canReview ? <button className="kk-action cmp-primary kk-primary-button" type="button" onClick={onReview}>{reviewLabel} <ArrowRight size={16} /></button> : <span className="cmp-next"><LockKeyhole size={15} />{nextStep}</span>}
    </section>
    <details className="cmp-details-disclosure" aria-labelledby="cmp-detail-title"><summary id="cmp-detail-title"><CircleHelp size={16} />Comparison details</summary><div className="cmp-detail-section">
      <WindowStrip windows={experiment.windows} frozen={experiment.policy.holdout_frozen} />
      <div className="cmp-section-heading cmp-detail-heading"><div><h2>How did each rule compare?</h2><p>Values supplied by the evaluator; the browser does not recalculate returns or risk.</p></div><a className="kk-secondary" href={API_ROUTES.experimentReport(experiment.experiment_id)} download><Download size={15} />Download report</a></div>
      <div className="cmp-table-wrap"><table className="cmp-table"><caption className="kk-sr-only">Comparison metrics</caption><thead><tr><th>Approach</th><th>Return</th><th>Sharpe</th><th>Largest fall</th><th>Exposure</th><th>Turnover</th><th>Trades</th></tr></thead><tbody>{experiment.baselines.map(item => <tr key={item.id} className={item.id === "agent_gate" ? "cmp-proposed" : undefined}><th scope="row">{ruleName(item.id, item.name)}</th><td>{percent(item.net_return)}</td><td>{number(item.sharpe)}</td><td>{percent(item.max_drawdown)}</td><td>{ratio(item.exposure)}</td><td>{number(item.turnover)}×</td><td>{item.trades.toLocaleString("en-GB")}</td></tr>)}</tbody></table></div>
      <div className="cmp-explainer"><div><p><strong>Return</strong> is the gain or loss after the costs supplied for this run.</p><p><strong>Sharpe</strong> relates return to variability; a short history is not proof.</p><p><strong>Largest fall</strong> is the biggest drop from a previous high. This report supplies the aggregate value, not a separate drawdown time series.</p><p><strong>Exposure and turnover</strong> describe how much capital was active and how much was traded.</p></div></div>
      <aside className="cmp-limitations" aria-label="Comparison limitations"><TriangleAlert size={16} /><p>{experiment.limitations.length ? experiment.limitations.join(" ") : "Keep the tested period, costs, and rule definition attached to this comparison."}</p></aside>
    </div></details>
  </section>;
}
