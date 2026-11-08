"use client";

import { ArrowRight, CircleHelp } from "lucide-react";
import type { SharedResearchProps } from "./types";
import ResearchChart from "./research-chart";
import { MagneticAction } from "./ui-motion";
import { MascotCallout } from "./mascot";
import StrategyHealth, { type StrategyHealthShape } from "./strategy-health";
import "./overview.css";

type Props = SharedResearchProps & {
  onConditions: () => void;
  onCompare: () => void;
  strategyHealth?: StrategyHealthShape | null;
  onHealthEvidence?: (evidenceId: string) => void;
  onHealthNext?: () => void;
};

type ExperimentWithHealth = SharedResearchProps["experiment"] & {
  strategy_health?: StrategyHealthShape | null;
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

export default function ResearchOverview({ experiment, selectedDate, onSelectDate, onConditions, onCompare, strategyHealth, onHealthEvidence, onHealthNext, onEvidence }: Props) {
  const findings = experiment.hypotheses.map(item => plainHypothesis(item, experiment.mode));
  const mainFinding = findings.find(item => item.status === "supported") ?? findings.find(item => item.status === "inconclusive");
  const measuredAndTested = experiment.mode === "measured" && experiment.policy.holdout_frozen && experiment.policy.test_evaluated;
  const currentReturn = baselineReturn(experiment);
  const primaryLabel = measuredAndTested ? "Compare" : "See why";
  const primaryAction = measuredAndTested ? onCompare : onConditions;
  const returnIsReady = currentReturn !== null && Number.isFinite(currentReturn);
  const returnText = returnIsReady ? percent(currentReturn) : "Awaiting a fair test";
  const nativeHealth = (experiment as ExperimentWithHealth).strategy_health;
  const resolvedHealth = strategyHealth !== undefined ? strategyHealth : nativeHealth;
  const healthSupplied = resolvedHealth !== undefined && resolvedHealth !== null;
  const calloutPose = !mainFinding || experiment.mode === "pending"
    ? "bear-neutral"
    : mainFinding.status === "supported"
      ? (selectedDate ? "bull-frame-region" : "bull-point-left")
      : mainFinding.status === "inconclusive"
        ? "bull-thoughtful"
        : "bear-neutral";

  return <div className={`ov-page ${healthSupplied ? "ov-page-health" : ""}`}>
    {healthSupplied ? <>
      <StrategyHealth health={resolvedHealth} onEvidence={onHealthEvidence ?? onEvidence} onNext={onConditions} />
      {experiment.equity.length > 0 && <div className="ov-chart-wrap" data-guide-target="overview-chart"><ResearchChart data={experiment.equity} series={["base"]} selectedDate={selectedDate} onSelectDate={onSelectDate} label="Original strategy over time" mode={experiment.mode} height={300} presentation="overview" reveal /></div>}
    </> : <>
      <section className="ov-hero" aria-label="Strategy at a glance">
        <div className="ov-hero-value" aria-label={`Original strategy return ${returnText}`}>
          <strong className={returnIsReady ? undefined : "ov-awaiting"}>{returnText}</strong>
          <p className="ov-period">{returnIsReady ? "Recorded return after costs" : "A result on unseen data is still needed."}</p>
        </div>
        <div className="ov-hero-action" data-guide-target="overview-finding">
          <MascotCallout pose={calloutPose} title={mainFinding?.title ?? (experiment.mode === "pending" ? "Research is pending." : "No clear finding yet.")} className="ov-scene-callout">
            {mainFinding?.finding ?? "Read the conditions and source records before deciding what to test next."}
          </MascotCallout>
          <MagneticAction><button type="button" className="ov-primary-action kk-primary-button" onClick={primaryAction}>{primaryLabel}<ArrowRight size={17} /></button></MagneticAction>
        </div>
      </section>

      {experiment.equity.length > 0 ? <div className="ov-chart-wrap" data-guide-target="overview-chart"><ResearchChart data={experiment.equity} series={["base"]} selectedDate={selectedDate} onSelectDate={onSelectDate} label="Original strategy over time" mode={experiment.mode} height={300} presentation="overview" reveal /></div> : <div className="ov-empty-chart" data-guide-target="overview-chart" role="status"><CircleHelp size={18} /><span>No measured curve is available yet.</span></div>}

      <StrategyHealth onNext={onHealthNext ?? primaryAction} />
    </>}
  </div>;
}
