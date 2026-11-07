"use client";

import { ChevronRight, CircleHelp, ExternalLink } from "lucide-react";
import type { SharedResearchProps } from "./types";
import ResearchChart from "./research-chart";
import "./overview.css";

type Props = SharedResearchProps & {
  onConditions: () => void;
  onCompare: () => void;
};

const percent = (value: number | null | undefined) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
};

function modeLabel(mode: SharedResearchProps["experiment"]["mode"]) {
  if (mode === "demo") return "Illustrative example";
  if (mode === "measured") return "Measured research";
  return "Research pending";
}

function plainHypothesis(hypothesis: SharedResearchProps["experiment"]["hypotheses"][number], mode: SharedResearchProps["experiment"]["mode"]) {
  if (mode !== "demo") return hypothesis;
  const title = hypothesis.title.toLowerCase();
  if (hypothesis.id === "hyp_01" || title.includes("falling volatility")) {
    return { ...hypothesis, title: "Calmer markets helped the strategy", finding: "The example was stronger when price swings became smaller. That is a pattern to test, not proof." };
  }
  if (hypothesis.id === "hyp_02" || title.includes("rising volatility")) {
    return { ...hypothesis, title: "Bigger price swings may not explain every loss", finding: "The example was weaker in these conditions, but it does not prove why the losses happened." };
  }
  if (hypothesis.id === "hyp_03" || title.includes("news caused")) {
    return { ...hypothesis, title: "The news explanation lacked dated evidence", finding: "No dated news records were available in this run, so that explanation was rejected." };
  }
  return hypothesis;
}

function findingLabel(status: SharedResearchProps["experiment"]["hypotheses"][number]["status"]) {
  if (status === "supported") return "Historical finding";
  if (status === "rejected") return "Rejected explanation";
  return "Still unclear";
}

function testedPeriod(experiment: SharedResearchProps["experiment"]) {
  const test = experiment.windows.test;
  if (test && test !== "pending") return test;
  const points = experiment.equity;
  if (points.length > 1) return `${points[0].date} to ${points[points.length - 1].date}`;
  return "Period not available";
}

function baselineReturn(experiment: SharedResearchProps["experiment"]) {
  const baseline = experiment.baselines.find(item => item.id === "always_on") || experiment.baselines[0];
  return baseline ? baseline.net_return : null;
}

export default function ResearchOverview({ experiment, strategy, selectedDate, onSelectDate, onEvidence, onConditions, onCompare }: Props) {
  const findings = experiment.hypotheses.slice(0, 2).map(item => plainHypothesis(item, experiment.mode));
  const measuredAndTested = experiment.mode === "measured" && experiment.policy.holdout_frozen && experiment.policy.test_evaluated;
  const currentReturn = baselineReturn(experiment);
  const primaryLabel = measuredAndTested ? "Review the comparison" : "Explore conditions";
  const primaryAction = measuredAndTested ? onCompare : onConditions;

  return <div className="ov-page">
    <header className="ov-heading">
      <div>
        <h1>{strategy.name}</h1>
        <p className="ov-subtitle">{strategy.symbol} · {strategy.timeframe} · {testedPeriod(experiment)}</p>
      </div>
      <div className={`ov-mode ov-mode-${experiment.mode}`}><span className="ov-mode-dot" />{modeLabel(experiment.mode)}</div>
    </header>

    <section className="ov-hero" aria-label="Original strategy result">
      <div className="ov-hero-copy"><span>Original strategy</span></div>
      <div className="ov-hero-value" aria-label={`Original strategy return ${percent(currentReturn)}`}>
        <span>Net return after costs</span>
        <strong className={currentReturn !== null && currentReturn < 0 ? "is-negative" : ""}>{percent(currentReturn)}</strong>
      </div>
    </section>

    {experiment.equity.length > 0 ? <div className="ov-chart-wrap"><ResearchChart data={experiment.equity} series={["base", "cash"]} selectedDate={selectedDate} onSelectDate={onSelectDate} label="Original strategy over time" mode={experiment.mode} height={430} reveal /></div> : <div className="ov-empty-chart" role="status"><CircleHelp size={18} /><span>No measured curve is available for this run yet.</span></div>}

    {experiment.equity.length > 0 && <details className="ov-guide"><summary>How to read this</summary><p>The line starts at 100. Hover, select a date, or open the data table to inspect each recorded observation.</p></details>}

    <section className="ov-findings" aria-labelledby="ov-findings-title">
      <div className="ov-section-heading"><h2 id="ov-findings-title">What stood out</h2></div>
      {findings.length > 0 ? <div className="ov-finding-list">{findings.map(item => <article className={`ov-finding ov-finding-${item.status}`} key={item.id}><div className="ov-finding-label">{findingLabel(item.status)}</div><h3>{item.title}</h3><p>{item.finding}</p>{item.evidence_ids[0] ? <button type="button" className="ov-text-action" onClick={() => onEvidence(item.evidence_ids[0])}>Open evidence <ExternalLink size={14} /></button> : <span className="ov-no-evidence">No dated evidence was recorded.</span>}</article>)}</div> : <p className="ov-empty-copy">No descriptive findings were recorded for this run.</p>}
    </section>

    <section className="ov-next" aria-labelledby="ov-next-title">
      <div><h2 id="ov-next-title">{measuredAndTested ? "See whether the filter helps." : "Explore the conditions around the result."}</h2><p>{measuredAndTested ? "Same dates and costs, side by side." : "See where the curve held up or struggled."}</p></div>
      <button type="button" className="ov-primary-action" onClick={primaryAction}>{primaryLabel}<ChevronRight size={17} /></button>
    </section>

    <p className="ov-integrity">Original strategy unchanged · {experiment.mode === "measured" ? "Evaluator metrics." : experiment.mode === "demo" ? "Illustrative figures." : "Awaiting evaluator."}</p>
  </div>;
}
