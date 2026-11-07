"use client";

import { ArrowRight, ArrowUpRight, Beaker, Check, ChevronRight, CircleCheck, CircleHelp, FlaskConical, GitBranch, LockKeyhole, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import type { Experiment } from "../../../../packages/contracts/types";
import EquityChart from "./equity-chart";
import "./research-overview.css";

type OverviewTab = "overview" | "investigation" | "comparison" | "decision";

const percent = (value: number | null) => value === null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
const percentagePoints = (value: number | null) => value === null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)} p.p.`;
const integer = (value: number) => Math.round(value).toLocaleString("en-GB");
const number = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 });

function marketTrend(value: string) {
  const normalized = value.trim().toLowerCase();
  if (normalized === "positive" || normalized === "up" || normalized === "rising") return "Prices rose";
  if (normalized === "negative" || normalized === "down" || normalized === "falling") return "Prices fell";
  if (normalized === "sideways" || normalized === "flat") return "Prices moved sideways";
  return value;
}

function marketVolatility(value: string) {
  const normalized = value.trim().toLowerCase();
  if (normalized === "falling" || normalized === "low") return "swings became smaller";
  if (normalized === "rising" || normalized === "high") return "swings grew";
  return `${value} price swings`;
}

function marketSummary(regime: Experiment["regimes"][number]) {
  return `${marketTrend(regime.trend)} while ${marketVolatility(regime.volatility)}: ${percent(regime.net_return)} across ${integer(regime.trades)} trades.`;
}

function displayedHypothesis(hypothesis: Experiment["hypotheses"][number], mode: Experiment["mode"]) {
  if (mode !== "demo") return hypothesis;
  if (hypothesis.id === "hyp_01" || hypothesis.title.toLowerCase().includes("falling volatility")) {
    return { ...hypothesis, title: "Calmer markets helped the trend strategy", finding: "The example shows stronger results when price swings were getting smaller. This is a pattern to test, not proof." };
  }
  if (hypothesis.id === "hyp_02" || hypothesis.title.toLowerCase().includes("rising volatility")) {
    return { ...hypothesis, title: "Bigger price swings may not explain every loss", finding: "The example was weaker in these conditions, but it does not prove why the losses happened." };
  }
  if (hypothesis.id === "hyp_03" || hypothesis.title.toLowerCase().includes("news caused")) {
    return { ...hypothesis, title: "The news explanation lacked dated evidence", finding: "No dated news records were available in this run, so that explanation was rejected." };
  }
  return hypothesis;
}

function metricLabel(label: string) {
  const normalized = label.trim().toLowerCase();
  if (normalized.includes("base") && normalized.includes("return")) return "Original strategy return";
  if (normalized.includes("proposed") && normalized.includes("return")) return "Suggested rule return";
  if (label.trim().startsWith("Δ")) return "Difference";
  return label;
}

function statusLabel(status: Experiment["hypotheses"][number]["status"]) {
  if (status === "supported") return "Looks promising here";
  if (status === "rejected") return "Rejected explanation";
  return "Still unclear";
}

function modeLabel(mode: Experiment["mode"]) {
  if (mode === "demo") return "Illustrative demo";
  if (mode === "measured") return "Measured result";
  return "Research pending";
}

function modeClass(mode: Experiment["mode"]) {
  if (mode === "demo") return "example";
  if (mode === "measured") return "measured";
  return "pending";
}

function MetricValue({ value, format, percentagePointValue = false }: { value: number | null; format: "percent" | "number" | "integer"; percentagePointValue?: boolean }) {
  if (value === null) return <>—</>;
  if (percentagePointValue) return <>{percentagePoints(value)}</>;
  if (format === "percent") return <>{percent(value)}</>;
  if (format === "integer") return <>{integer(value)}</>;
  return <>{number.format(value)}</>;
}

function Legend() {
  return <div className="ro-legend" aria-label="Equity curve legend">
    <span><i className="ro-swatch proposed" />Suggested rule</span>
    <span><i className="ro-swatch rule" />Simple baseline</span>
    <span><i className="ro-swatch base" />Original strategy</span>
    <span><i className="ro-swatch cash" />Cash</span>
  </div>;
}

function HypothesisCard({
  hypothesis,
  index,
  onEvidence,
  setTab,
}: {
  hypothesis: Experiment["hypotheses"][number];
  index: number;
  onEvidence: (id: string) => void;
  setTab: (tab: OverviewTab) => void;
}) {
  const tone = hypothesis.status === "supported" ? "positive" : hypothesis.status === "rejected" ? "negative" : "neutral";
  const evidenceId = hypothesis.evidence_ids[0];
  return <article className={`ro-hypothesis ${tone}`}>
    <div className="ro-hypothesis-top">
      <span className="ro-hypothesis-index">{String(index + 1).padStart(2, "0")}</span>
      <span className="ro-status"><span className="ro-status-dot" />{statusLabel(hypothesis.status)}</span>
    </div>
    <h3>{hypothesis.title}</h3>
    <p>{hypothesis.finding}</p>
    <button className="ro-evidence-link" type="button" onClick={() => evidenceId ? onEvidence(evidenceId) : setTab("investigation")}>
      {evidenceId ? <>Inspect evidence <ArrowUpRight size={14} /></> : <>Open investigation <ChevronRight size={14} /></>}
    </button>
  </article>;
}

function RegimeCell({ regime, onEvidence, setTab }: { regime: Experiment["regimes"][number]; onEvidence: (id: string) => void; setTab: (tab: OverviewTab) => void }) {
  const tone = regime.net_return >= 0 ? "positive" : "negative";
  return <article className={`ro-regime ${tone}`}>
    <button
      className="ro-regime-main"
      type="button"
      onClick={() => regime.evidence_id ? onEvidence(regime.evidence_id) : setTab("investigation")}
      aria-label={`Inspect ${regime.trend} trend and ${regime.volatility} volatility evidence`}
    >
      <span className="ro-regime-heading"><span>{marketTrend(regime.trend)}</span><small>{marketVolatility(regime.volatility)}</small></span>
      <strong>{percent(regime.net_return)}</strong>
      <span className="ro-regime-meta"><span>{integer(regime.trades)} trades</span><ArrowUpRight size={14} /></span>
    </button>
    <details className="ro-confidence"><summary>How certain?</summary><span>Likely range: {percent(regime.confidence_low)} to {percent(regime.confidence_high)}</span></details>
  </article>;
}

export default function ResearchOverview({ experiment, setTab, onEvidence }: { experiment: Experiment; setTab: (tab: OverviewTab) => void; onEvidence: (id: string) => void }) {
  const hypotheses = experiment.hypotheses.slice(0, 3);
  const testReady = experiment.policy.holdout_frozen && experiment.policy.test_evaluated;
  const newDataChecked = testReady && experiment.mode === "measured";
  const positiveRegime = [...experiment.regimes].filter(item => item.net_return > 0).sort((a, b) => b.net_return - a.net_return)[0];
  const negativeRegime = [...experiment.regimes].filter(item => item.net_return < 0).sort((a, b) => a.net_return - b.net_return)[0];
  const supportedHypothesis = experiment.hypotheses.find(item => item.status === "supported");
  const unclearHypothesis = experiment.hypotheses.find(item => item.status === "inconclusive");
  const briefTitle = experiment.verdict === "CONDITIONAL" ? "Promising in the right conditions." : experiment.verdict === "KEEP" ? "This strategy is holding up." : experiment.verdict === "KILL" ? "The strategy is not earning its keep." : experiment.verdict === "REDUCE" ? "Cut size where the risk cap allows it." : experiment.verdict === "MONITOR" ? "Worth watching before changing." : "More evidence is needed before deciding.";
  const plainSupportedHypothesis = supportedHypothesis ? displayedHypothesis(supportedHypothesis, experiment.mode) : null;
  const plainUnclearHypothesis = unclearHypothesis ? displayedHypothesis(unclearHypothesis, experiment.mode) : null;
  const worksSummary = positiveRegime ? marketSummary(positiveRegime) : plainSupportedHypothesis ? `${plainSupportedHypothesis.title}: ${plainSupportedHypothesis.finding}` : "No clear strength was recorded in this run.";
  const strugglesSummary = negativeRegime ? marketSummary(negativeRegime) : plainUnclearHypothesis ? `${plainUnclearHypothesis.title}: ${plainUnclearHypothesis.finding}` : "No clear weak spot was recorded in this run.";
  const nextTestSummary = experiment.mode === "demo" ? "Check the suggested rule on fresh data before a practice run." : newDataChecked ? "Run the same suggested change on new, unseen data." : "Run a new-data test before changing exposure.";
  const briefCopy = experiment.mode === "demo" ? "See where this example worked, where it struggled, and what deserves a closer look." : experiment.recommendation;
  const decisionCopy = experiment.mode === "demo" ? "This is a rehearsal of the decision path. The suggested rule still needs a measured evaluator before any paper test." : experiment.recommendation;

  return <div className="ro-overview tab-content">
    <section className="ro-brief panel" aria-labelledby="research-brief-title">
      <div className="ro-brief-main">
        <div className="ro-kicker"><Sparkles size={14} />WHAT WE LEARNED <span className={`ro-mode ${modeClass(experiment.mode)}`}>{experiment.mode === "demo" && <Beaker size={12} />}{modeLabel(experiment.mode)}</span></div>
        <h2 id="research-brief-title">{briefTitle}</h2>
        <p className="ro-brief-copy">{briefCopy}</p>
        <div className="ro-plain-summary"><div><span>Works when</span><p>{worksSummary}</p></div><div><span>Struggles when</span><p>{strugglesSummary}</p></div><div><span>Next test</span><p>{nextTestSummary}</p></div></div>
        {experiment.mode === "demo" && <p className="ro-caveat"><Beaker size={14} />Illustrative demo: confidence is limited; these figures do not prove future performance.</p>}
      </div>
      <div className="ro-brief-action">
        <span className="ro-action-label">See how we know</span>
        <strong>Follow the investigation.</strong>
        <p>See the tools, challenges, and attempts behind this summary.</p>
        <button className="button primary" type="button" onClick={() => setTab("investigation")}><FlaskConical size={15} />Follow investigation <ArrowRight size={15} /></button>
      </div>
    </section>

    <nav className="ro-progress" aria-label="Research process">
      <span className="ro-progress-step complete"><span><Check size={13} /></span><strong>Inspect</strong><small>Data reviewed</small></span>
      <span className="ro-progress-line complete" />
      <span className="ro-progress-step complete"><span><Check size={13} /></span><strong>Investigate</strong><small>{experiment.steps.length} recorded steps</small></span>
      <span className={`ro-progress-line ${newDataChecked ? "complete" : ""}`} />
      <span className={`ro-progress-step ${newDataChecked ? "complete" : "current"}`}><span>{newDataChecked ? <Check size={13} /> : <span>3</span>}</span><strong>New-data test</strong><small>{experiment.mode === "demo" ? "Demo only · not measured" : newDataChecked ? "Checked on unseen data" : "Not run yet"}</small></span>
      <span className={`ro-progress-line ${experiment.verdict !== "INCONCLUSIVE" ? "complete" : ""}`} />
      <span className={`ro-progress-step ${experiment.verdict !== "INCONCLUSIVE" ? "current" : ""}`}><span>{experiment.verdict !== "INCONCLUSIVE" ? <CircleCheck size={13} /> : <span>4</span>}</span><strong>Decide</strong><small>{experiment.verdict}</small></span>
    </nav>

    <section className="ro-hypotheses" aria-labelledby="hypotheses-title">
      <div className="ro-section-heading"><div><span className="eyebrow">AGENT RESEARCH</span><h2 id="hypotheses-title">What the agents found</h2><p>Each idea has a plain-language outcome and a link to the evidence behind it.</p></div><span className="ro-count">{experiment.hypotheses.length} findings</span></div>
      <div className="ro-hypothesis-grid">{hypotheses.length ? hypotheses.map((hypothesis, index) => <HypothesisCard key={hypothesis.id} hypothesis={displayedHypothesis(hypothesis, experiment.mode)} index={index} onEvidence={onEvidence} setTab={setTab} />) : <div className="ro-empty panel"><CircleHelp size={18} />No hypotheses were recorded for this run.</div>}</div>
    </section>

    <section className="ro-analysis-grid">
      <article className="ro-regime-panel panel" aria-labelledby="regime-title">
        <div className="ro-panel-heading"><div><span className="eyebrow">MARKET CONDITIONS</span><h2 id="regime-title">When did it work or struggle?</h2><p>Historical results in different market situations. Volatility means the size of price swings. Click a situation to see its evidence.</p></div><span className="subtle-badge"><GitBranch size={12} />Patterns, not promises</span></div>
        <div className="ro-regime-grid">{experiment.regimes.map(regime => <RegimeCell key={regime.id} regime={regime} onEvidence={onEvidence} setTab={setTab} />)}</div>
        <div className="ro-panel-foot"><span><CircleHelp size={14} />Open “How certain?” on a card for its likely range.</span><button className="text-button" type="button" onClick={() => setTab("investigation")}>Review all evidence <ArrowRight size={14} /></button></div>
      </article>

      <aside className="ro-verdict panel" aria-labelledby="verdict-title">
        <div className="ro-verdict-head"><span className="eyebrow"><ShieldCheck size={14} />NEXT DECISION</span><span className={`ro-verdict-pill ${experiment.verdict.toLowerCase()}`}>{experiment.mode === "demo" ? "Illustrative only" : experiment.verdict === "CONDITIONAL" ? "Activate conditionally" : experiment.verdict === "REDUCE" ? "Reduce size" : experiment.verdict}</span></div>
        <h2 id="verdict-title">Try a better rule.</h2>
        <p>{decisionCopy}</p>
        <div className="ro-policy"><span className="eyebrow">SUGGESTED CHANGE</span><strong>{experiment.policy.description}</strong>{experiment.policy.conditions.length > 0 && <ul>{experiment.policy.conditions.slice(0, 3).map(condition => <li key={condition}><Check size={13} />{condition}</li>)}</ul>}</div>
        <button className="text-button ro-verdict-link" type="button" onClick={() => setTab("decision")}>Review decision report <ArrowRight size={14} /></button>
      </aside>
    </section>

    <section className="ro-performance panel" aria-labelledby="performance-title">
      <div className="ro-panel-heading"><div><span className="eyebrow">COMPARE APPROACHES</span><h2 id="performance-title">Does the suggested change help?</h2><p>Indexed value · starting value 100 · figures from this research run.</p></div><span className="subtle-badge"><LockKeyhole size={12} />{experiment.mode === "demo" ? "Illustrative comparison" : newDataChecked ? "Unseen-data comparison" : "New-data test pending"}</span></div>
      {experiment.equity.length > 0 ? <><Legend /><EquityChart data={experiment.equity} /><div className="ro-metric-strip">{experiment.metrics.slice(0, 4).map(metric => <div key={metric.label}><span>{metricLabel(metric.label)}</span><strong className={metric.value !== null && metric.value < 0 ? "negative" : ""}><MetricValue value={metric.value} format={metric.format} percentagePointValue={metric.label.trim().startsWith("Δ")} /></strong><small>{metric.description}</small></div>)}</div></> : <div className="ro-empty ro-empty-performance"><TriangleAlert size={18} />No comparison series are available for this run.</div>}
      <div className="ro-panel-foot"><span><GitBranch size={14} />Detailed numbers and assumptions are in the comparison view.</span><button className="text-button" type="button" onClick={() => setTab("comparison")}>Compare approaches <ArrowRight size={14} /></button></div>
    </section>
  </div>;
}
