"use client";

import { ArrowUpRight, Info, MousePointer2 } from "lucide-react";
import { useEffect, useState } from "react";
import type { Regime } from "../../../../../packages/contracts/types";
import type { SharedResearchProps } from "./types";
import ResearchChart from "./research-chart";
import KineticText from "./kinetic-text";
import { MascotCallout } from "./mascot";
import "./conditions.css";

const trendLabel = (value: string) => {
  const normalized = value.toLowerCase();
  if (normalized.includes("positive") || normalized.includes("bull")) return "Prices rose";
  if (normalized.includes("negative") || normalized.includes("bear")) return "Prices fell";
  if (normalized.includes("sideways") || normalized.includes("flat")) return "Prices moved sideways";
  return value;
};

const volatilityLabel = (value: string) => {
  const normalized = value.toLowerCase();
  if (normalized.includes("fall") || normalized.includes("low") || normalized.includes("calm")) return "swings became smaller";
  if (normalized.includes("ris") || normalized.includes("high")) return "swings grew";
  return value;
};

const signedPercent = (value: number | null) => value === null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
const rangePercent = (low: number, high: number) => `${signedPercent(low)} to ${signedPercent(high)}`;

type ConditionFinding = {
  id: string;
  title: string;
  finding: string;
  plainFinding: string;
  conditions: string[];
  evidenceIds: string[];
  direction?: "works_better" | "works_worse";
  confidence?: string;
};

const conditionLabel = (value: string) => {
  const normalized = value.toLowerCase().replace(/\s/g, "");
  const readable: Record<string, string> = {
    "vol_regime=low": "Smaller price swings",
    "vol_regime=high": "Larger price swings",
    "trend_regime=bull": "Rising-price markets",
    "trend_regime=bear": "Falling-price markets",
    "trend_regime=sideways": "Sideways markets",
    "liquidity_regime=deep": "Deeper liquidity",
    "liquidity_regime=thin": "Thinner liquidity",
    "sentiment_regime=greed": "More optimistic sentiment",
    "sentiment_regime=fear": "More fearful sentiment",
  };
  if (readable[normalized]) return readable[normalized];
  const [feature, state] = value.split("=", 2);
  const featureLabel = feature
    .replace(/_regime$/i, "")
    .replaceAll("_", " ")
    .trim();
  const stateLabel = (state || "").replaceAll("_", " ").trim();
  if (!stateLabel) return featureLabel || value;
  return `${featureLabel || "condition"}: ${stateLabel}`;
};

const conditionTitleLabel = (value: string) => {
  const normalized = value.toLowerCase().replace(/\s/g, "");
  const readable: Record<string, string> = {
    "vol_regime=low": "Calm markets",
    "vol_regime=high": "More volatile markets",
    "trend_regime=bull": "Rising-price markets",
    "trend_regime=bear": "Falling-price markets",
    "trend_regime=sideways": "Sideways markets",
    "liquidity_regime=deep": "Deeper-liquidity markets",
    "liquidity_regime=thin": "Thinner-liquidity markets",
    "sentiment_regime=greed": "More optimistic markets",
    "sentiment_regime=fear": "More fearful markets",
  };
  return readable[normalized] || conditionLabel(value);
};

const nativePlainFinding = (direction: ConditionFinding["direction"], conditions: string[]) => {
  const condition = conditions[0] ? conditionLabel(conditions[0]).toLowerCase() : "this condition";
  if (conditions[0]?.toLowerCase().replace(/\s/g, "") === "vol_regime=low" && direction === "works_worse") {
    return "Small price swings were a weak spot in training. The evidence supports investigating a filter; it does not predict what happens next.";
  }
  if (direction === "works_worse") {
    return `The report found a weaker pattern in ${condition} during training. It is a lead to investigate, not a prediction.`;
  }
  if (direction === "works_better") {
    return `The report found a more favorable pattern in ${condition} during training. It still needs an unseen-data test.`;
  }
  return "The report recorded a condition to investigate. It is not a prediction.";
};

const availableEvidenceId = (finding: ConditionFinding, evidenceIds: Set<string>) => finding.evidenceIds.find(id => evidenceIds.has(id));

function NativeFindingList({ findings, evidence, evidenceIds, onEvidence }: { findings: ConditionFinding[]; evidence: SharedResearchProps["experiment"]["evidence"]; evidenceIds: Set<string>; onEvidence: (id: string) => void }) {
  if (findings.length < 2) return null;
  return <div className="cv-finding-list" aria-label="Recorded condition findings">
    {findings.slice(1).map(finding => {
      const evidenceId = availableEvidenceId(finding, evidenceIds);
      const source = evidenceId ? evidence.find(item => item.id === evidenceId)?.source : undefined;
      return <article className="cv-finding-row" key={finding.id}>
        <div className="cv-finding-copy">
          <h3>{finding.title}</h3>
          {finding.conditions.length > 0 && <p className="cv-finding-conditions">{finding.conditions.map(conditionLabel).join(" · ")}</p>}
          <p>{finding.plainFinding}</p>
          <details className="cv-finding-detail"><summary>Technical detail</summary><p>{finding.finding}</p>{finding.confidence && <p>Recorded confidence: {finding.confidence}.</p>}{source && <p>Source: {source}</p>}</details>
        </div>
        {evidenceId && <button className="kk-action cv-finding-link" type="button" onClick={() => onEvidence(evidenceId)}><span>Open evidence</span><ArrowUpRight size={15} /></button>}
      </article>;
    })}
  </div>;
}

function IntervalGraphic({ regimes, selectedId, onSelect, demo }: { regimes: Regime[]; selectedId: string | null; onSelect: (id: string) => void; demo: boolean }) {
  const values = regimes.flatMap(regime => [regime.confidence_low, regime.confidence_high, regime.net_return]);
  const range = Math.max(...values.map(value => Math.abs(value)), 0.01) * 1.12;
  const position = (value: number) => `${Math.max(0, Math.min(100, ((value + range) / (range * 2)) * 100))}%`;
  const zero = position(0);
  return <div className="cv-interval-plot" data-guide-target="conditions-table" role="group" aria-label="Likely range by market situation">
    <div className="cv-interval-axis"><div className="cv-axis-track"><span>Lower result</span><span className="cv-axis-zero" style={{ left: zero }}>0</span><span>Higher result</span></div></div>
    <div className="cv-interval-rows">
      {regimes.map(regime => {
        const low = position(regime.confidence_low);
        const high = position(regime.confidence_high);
        const returnPosition = position(regime.net_return);
        const title = regime.label ?? trendLabel(regime.trend);
        const detail = regime.label ? null : volatilityLabel(regime.volatility);
        return <button key={regime.id} className={`cv-interval-row ${selectedId === regime.id ? "selected" : ""}`} type="button" onClick={() => onSelect(regime.id)} aria-label={`${title}${detail ? `, ${detail}` : ""}. Result ${signedPercent(regime.net_return)} across ${regime.trades} trades. Likely range ${rangePercent(regime.confidence_low, regime.confidence_high)}.`}>
          <span className="cv-interval-label"><strong>{title}</strong>{detail ? <small>{detail}</small> : null}</span>
          <span className="cv-interval-track"><i className="cv-interval-zero" style={{ left: zero }} /><i className="cv-interval-line" style={{ left: low, width: `calc(${high} - ${low})` }} /><i className="cv-interval-point" style={{ left: returnPosition }} /></span>
          <span className={`cv-interval-value ${regime.net_return < 0 ? "negative" : "positive"}`}>{signedPercent(regime.net_return)}</span>
        </button>;
      })}
    </div>
    <p className="cv-interval-caption"><span className="cv-interval-key" />Likely range supplied by the research run <span className="cv-point-key" />{demo ? "Illustrative result" : "Observed result"}</p>
  </div>;
}

function SituationDetail({ regime, scope, source, demo, onEvidence, onClose }: { regime: Regime; scope: string; source: string; demo: boolean; onEvidence: (id: string) => void; onClose: () => void }) {
  const smallSample = regime.trades < 20;
  return <aside className="cv-situation-detail" aria-live="polite">
    <div className="cv-detail-top"><h3>{regime.label ?? `${trendLabel(regime.trend)} · ${volatilityLabel(regime.volatility)}`}</h3><button className="cv-close" type="button" aria-label="Close selected situation" onClick={onClose}><span aria-hidden="true">×</span></button></div>
    <p className="cv-detail-scope">{scope}</p>
    <dl className="cv-detail-facts"><div><dt>{demo ? "Illustrative result" : "Recorded result"}</dt><dd className={regime.net_return < 0 ? "negative" : "positive"}>{signedPercent(regime.net_return)}</dd></div><div><dt>Likely range</dt><dd>{rangePercent(regime.confidence_low, regime.confidence_high)}</dd></div><div><dt>Trades</dt><dd>{regime.trades}</dd></div><div><dt>Source</dt><dd>{source}</dd></div></dl>
    {smallSample && <p className="cv-small-sample"><Info size={15} />Fewer than 20 trades; treat this as a pattern to investigate.</p>}
    {regime.evidence_id && <button className="kk-action cv-evidence-action" type="button" onClick={() => onEvidence(regime.evidence_id)}><span>Open supporting evidence</span><ArrowUpRight size={16} /></button>}
  </aside>;
}

export default function ConditionsView({ experiment, strategy, selectedDate, onSelectDate, onEvidence }: SharedResearchProps) {
  const regimes = experiment.regimes;
  const [selectedRegimeId, setSelectedRegimeId] = useState<string | null>(regimes[0]?.id ?? null);
  useEffect(() => { setSelectedRegimeId(regimes[0]?.id ?? null); }, [experiment.experiment_id, regimes]);
  const selectedRegime = regimes.find(regime => regime.id === selectedRegimeId) ?? null;
  const regimeScope = experiment.windows.train !== "pending" ? `Training evidence · ${experiment.windows.train}` : "Training window not recorded";
  const equityScope = experiment.windows.test !== "pending" ? `Original strategy · indexed value · ${experiment.windows.test}` : `Original strategy · ${strategy.date_start} to ${strategy.date_end}`;
  const selectedSource = selectedRegime ? experiment.evidence.find(item => item.id === selectedRegime.evidence_id)?.source ?? "Evidence record" : "Evidence record";
  const selectedPose = !selectedRegime
    ? "bear-neutral"
    : selectedRegime.confidence_low <= 0 && selectedRegime.confidence_high >= 0
      ? "bear-compare"
      : selectedRegime.net_return < 0
        ? "bear-point-left"
        : selectedRegime.confidence_low > 0
          ? "bull-present-up"
          : "bear-present-up";
  const selectedTitle = selectedRegime
    ? `${trendLabel(selectedRegime.trend)} while ${volatilityLabel(selectedRegime.volatility)}.`
    : "Choose a situation to inspect.";
  const selectedSummary = selectedRegime
    ? `${signedPercent(selectedRegime.net_return)} across ${selectedRegime.trades} recorded trades. ${experiment.mode === "demo" ? "This is illustrative evidence." : "Treat this as a pattern to investigate."}`
    : "Select a situation to see its supplied range and source.";

  const nativeFindings: ConditionFinding[] = (experiment.native_report?.diagnostic.hypotheses ?? []).map(item => ({
    id: item.hypothesis_id,
    title: item.conditions[0]
      ? `${conditionTitleLabel(item.conditions[0])} ${item.direction === "works_worse" ? "were a weak spot." : "looked more favorable."}`
      : "Recorded condition finding",
    finding: item.statement.trim() || "The report recorded a condition to investigate.",
    plainFinding: nativePlainFinding(item.direction, item.conditions),
    conditions: item.conditions,
    evidenceIds: item.evidence_ids,
    direction: item.direction,
    confidence: item.confidence,
  }));
  const mappedFindings: ConditionFinding[] = experiment.hypotheses
    .filter(item => item.finding.trim() || item.title.trim())
    .map(item => ({ id: item.id, title: item.title.trim() || "Recorded condition finding", finding: item.finding.trim() || "The report recorded a condition to investigate.", plainFinding: item.finding.trim() || "The report recorded a condition to investigate.", conditions: [], evidenceIds: item.evidence_ids }));
  const conditionFindings = nativeFindings.length > 0 ? nativeFindings : mappedFindings;
  const leadFinding = conditionFindings[0];
  const evidenceIds = new Set(experiment.evidence.map(item => item.id));
  const leadEvidenceId = leadFinding ? availableEvidenceId(leadFinding, evidenceIds) : undefined;
  const nativeSummary = experiment.native_report?.diagnostic.summary?.trim();
  const noRegimeCopy = leadFinding?.plainFinding || "No grouped condition trace was supplied. Read the recorded report for details.";
  const noRegimeTitle = leadFinding?.title || "Read the recorded finding.";
  const leadSource = leadEvidenceId ? experiment.evidence.find(item => item.id === leadEvidenceId)?.source : undefined;
  const leadRawFinding = leadFinding?.finding || nativeSummary;

  return <section className="cv-page">
    <header className="cv-header"><div><span className="cv-kicker">EXPLORE / CONDITIONS</span><h1 className="cv-page-title"><KineticText trigger="mount">Where does it work?</KineticText></h1><p>Grouped history · a clue, not a prediction</p></div><span className={`cv-result-status ${experiment.mode === "demo" ? "example" : experiment.mode}`}>{experiment.mode === "demo" ? "Example evidence" : experiment.mode === "measured" ? "Measured evidence" : "Research pending"}</span></header>

    <section className="cv-patterns" aria-labelledby="cv-pattern-title"><header className="cv-section-head cv-pattern-head"><div><span className="cv-kicker">GROUPED EVIDENCE</span><h2 id="cv-pattern-title"><KineticText trigger="scroll">By market condition</KineticText></h2></div><div className="cv-pattern-aside" data-guide-target="conditions-finding"><span className="cv-scope">{regimeScope}</span>{regimes.length > 0 && <div className="cv-leading-note"><MascotCallout pose={selectedPose} title={selectedTitle} className="cv-scene-callout">{selectedSummary}</MascotCallout></div>}</div></header>{regimes.length ? <><IntervalGraphic regimes={regimes} selectedId={selectedRegimeId} onSelect={setSelectedRegimeId} demo={experiment.mode === "demo"} />{selectedRegime && <SituationDetail regime={selectedRegime} scope={regimeScope} source={selectedSource} demo={experiment.mode === "demo"} onEvidence={onEvidence} onClose={() => setSelectedRegimeId(null)} />}</> : <div className="cv-no-conditions" data-guide-target="conditions-finding"><MascotCallout pose="bear-question" title={noRegimeTitle} className="cv-no-conditions-scene"><span className="cv-lead-condition">{leadFinding?.conditions.map(conditionLabel).join(" · ") || "No grouped condition trace was supplied."}</span><span>{noRegimeCopy}</span></MascotCallout>{leadEvidenceId && <button className="kk-action cv-evidence-action" type="button" onClick={() => onEvidence(leadEvidenceId)}><span>Open supporting evidence</span><ArrowUpRight size={16} /></button>}{leadRawFinding && <details className="cv-lead-detail"><summary>Technical detail</summary><div><p>{leadRawFinding}</p>{leadFinding?.confidence && <p>Recorded confidence: {leadFinding.confidence}.</p>}{leadSource && <p>Source: {leadSource}</p>}</div></details>}<NativeFindingList findings={conditionFindings} evidence={experiment.evidence} evidenceIds={evidenceIds} onEvidence={onEvidence} /></div>}</section>

    <details className="cv-about"><summary><Info size={16} />About this evidence</summary><p>This report supplies grouped results for market situations. A time-aligned trend and volatility trace was not supplied, so the context below cannot be lined up to individual chart points.</p><p>The interval is the likely range supplied by the research run. It is descriptive evidence, not proof of causation or future performance.</p></details>

    {experiment.equity.length > 0 && <section className="cv-chart-section" data-guide-target="conditions-chart" aria-labelledby="cv-equity-title"><div className="cv-section-head"><div><span className="cv-kicker">ORIGINAL STRATEGY</span><h2 id="cv-equity-title"><KineticText trigger="scroll">What happened over time</KineticText></h2></div><span className="cv-scope">{equityScope}</span></div><ResearchChart data={experiment.equity} series={["base"]} selectedDate={selectedDate} onSelectDate={onSelectDate} label="Original strategy · indexed value" mode={experiment.mode} height={410} reveal /></section>}

    <details className="cv-explainer"><summary><MousePointer2 size={15} />How to read the interval</summary><p>The line is the strategy’s indexed result. The grouped rows are a separate training summary. A wider interval means more uncertainty.</p></details>
  </section>;
}
