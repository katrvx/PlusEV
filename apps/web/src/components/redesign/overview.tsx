"use client";

import { useEffect, useState } from "react";
import { ArrowRight, CircleHelp } from "lucide-react";
import { verdictLabel } from "./decision";
import type { SharedResearchProps } from "./types";
import { teamApi } from "@/lib/team-api";
import type { TeamReport } from "../../../../../packages/contracts/research";
import ResearchChart from "./research-chart";
import { MagneticAction } from "./ui-motion";
import "./overview.css";

type StrategyHealth = NonNullable<TeamReport["strategy_health"]>;

function HealthStrip({ experimentId, strategyId }: { experimentId: string; strategyId: string }) {
  const [health, setHealth] = useState<StrategyHealth | null>(null);
  useEffect(() => {
    let cancelled = false;
    teamApi.investigations().then(async items => {
      const match = items.find(item => item.experiment_id === experimentId) || items.find(item => item.strategy_id === strategyId);
      if (!match) return null;
      const wrapper = await teamApi.investigation(match.experiment_id);
      return wrapper.report.strategy_health ?? null;
    }).then(value => { if (!cancelled) setHealth(value); }).catch(() => { if (!cancelled) setHealth(null); });
    return () => { cancelled = true; };
  }, [experimentId, strategyId]);
  if (!health?.validation_blocks?.length) return null;
  const low = health.train_range?.low;
  const high = health.train_range?.high;
  const range = low === undefined || high === undefined ? "" : ` Training range ${percent(low)} to ${percent(high)}.`;
  return <section className="ov-health" aria-label="Unlucky or broken">
    <div className="ov-health-head"><h2>Unlucky or broken</h2><span>{health.status === "within_training_range" ? "Inside the training range" : "Outside the training range"}</span></div>
    <ol className="ov-blocks">{health.validation_blocks.map(block => <li key={block.start} className={`ov-block ov-block-${block.position}`}><span className="kk-sr-only">{new Date(block.start).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })} {block.position} {percent(block.net_return)}</span></li>)}</ol>
    <p>{health.summary}{range}</p>
    <p className="ov-health-window">Each cell is one 14-day validation block on the 2018–2026 book. The sealed test is the last 20% of that book, opened once.</p>
  </section>;
}

type Props = SharedResearchProps & {
  onConditions: () => void;
  onCompare: () => void;
};

const percent = (value: number | null | undefined) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value < 0 ? "−" : value > 0 ? "+" : ""}${Math.abs(value * 100).toFixed(1)}%`;
};

function plainHypothesis(hypothesis: SharedResearchProps["experiment"]["hypotheses"][number], mode: SharedResearchProps["experiment"]["mode"]) {
  if (mode !== "demo") return hypothesis;
  const title = hypothesis.title.toLowerCase();
  if (hypothesis.id === "hyp_01" || title.includes("falling volatility")) {
    return { ...hypothesis, title: "Calmer markets helped.", finding: "The example was stronger when price swings eased. A pattern to test, not proof." };
  }
  if (hypothesis.id === "hyp_02" || title.includes("rising volatility")) {
    return { ...hypothesis, title: "Bigger price swings may not explain every loss", finding: "The example was weaker in these conditions, but it does not prove why the losses happened." };
  }
  if (hypothesis.id === "hyp_03" || title.includes("news caused")) {
    return { ...hypothesis, title: "The news explanation lacked dated evidence", finding: "No dated news records were available in this run, so that explanation was rejected." };
  }
  return hypothesis;
}

function baselineReturn(experiment: SharedResearchProps["experiment"]) {
  const baseline = experiment.baselines.find(item => item.id === "always_on") || experiment.baselines[0];
  return baseline ? baseline.net_return : null;
}

export default function ResearchOverview({ experiment, strategy, selectedDate, onSelectDate, onConditions, onCompare }: Props) {
  const findings = experiment.hypotheses.map(item => plainHypothesis(item, experiment.mode));
  const mainFinding = findings.find(item => item.status === "supported") ?? findings.find(item => item.status === "inconclusive");
  const measuredAndTested = experiment.mode === "measured" && experiment.policy.holdout_frozen && experiment.policy.test_evaluated;
  const currentReturn = baselineReturn(experiment);
  const primaryLabel = measuredAndTested ? "Compare" : "See why";
  const primaryAction = measuredAndTested ? onCompare : onConditions;

  return <div className="ov-page">
    <header className="ov-heading">
      <div>
        <h1>{strategy.name}</h1>
      </div>
      <div className={`ov-mode ov-mode-${experiment.verdict.toLowerCase()}`}>{experiment.mode === "pending" ? "Research pending" : verdictLabel(experiment.verdict)}</div>
    </header>

    <HealthStrip experimentId={experiment.experiment_id} strategyId={strategy.strategy_id} />

    <section className="ov-hero" aria-label="Strategy at a glance">
      <div className="ov-hero-value" aria-label={`Original strategy return ${percent(currentReturn)}`}>
        <strong>{percent(currentReturn)}</strong>
        <p className="ov-period">Return after costs</p>
      </div>
    </section>

    {experiment.equity.length > 0 ? <div className="ov-chart-wrap"><ResearchChart data={experiment.equity} series={["base"]} selectedDate={selectedDate} onSelectDate={onSelectDate} label="Original strategy over time" mode={experiment.mode} height={300} presentation="overview" reveal /></div> : <div className="ov-empty-chart" role="status"><CircleHelp size={18} /><span>No measured curve is available yet.</span></div>}

    <section className="ov-takeaway" aria-label="Next step">
      {mainFinding && <p className="ov-finding">{mainFinding.title}</p>}
      <MagneticAction><button type="button" className="ov-primary-action kk-primary-button" onClick={primaryAction}>{primaryLabel}<ArrowRight size={17} /></button></MagneticAction>
    </section>

  </div>;
}
