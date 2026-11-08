"use client";

import { ArrowUpRight, Info, MousePointer2 } from "lucide-react";
import { useState } from "react";
import type { Regime } from "../../../../../packages/contracts/types";
import type { SharedResearchProps } from "./types";
import ResearchChart from "./research-chart";
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

const signedPercent = (value: number | null) => {
  if (value === null) return "—";
  const pct = value * 100;
  const digits = pct !== 0 && Math.abs(pct) < 0.1 ? 3 : 1;
  return `${pct > 0 ? "+" : ""}${pct.toFixed(digits)}%`;
};
const rangePercent = (low: number, high: number) => `${signedPercent(low)} to ${signedPercent(high)}`;

function IntervalGraphic({ regimes, selectedId, onSelect, demo }: { regimes: Regime[]; selectedId: string | null; onSelect: (id: string) => void; demo: boolean }) {
  const values = regimes.flatMap(regime => [regime.confidence_low, regime.confidence_high, regime.net_return]);
  const range = Math.max(...values.map(value => Math.abs(value)), 0.01) * 1.12;
  const position = (value: number) => `${Math.max(0, Math.min(100, ((value + range) / (range * 2)) * 100))}%`;
  const zero = position(0);
  return <div className="cv-interval-plot" role="group" aria-label="Likely range by market situation">
    <div className="cv-interval-axis"><span>Lower result</span><span className="cv-axis-zero" style={{ left: zero }}>0</span><span>Higher result</span></div>
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
  const selectedRegime = regimes.find(regime => regime.id === selectedRegimeId) ?? null;
  const regimeScope = experiment.windows.train !== "pending" ? `Training evidence · ${experiment.windows.train}` : "Training window not recorded";
  const equityScope = experiment.windows.test !== "pending" ? `Original strategy · indexed value · ${experiment.windows.test}` : `Original strategy · ${strategy.date_start} to ${strategy.date_end}`;
  const selectedSource = selectedRegime ? experiment.evidence.find(item => item.id === selectedRegime.evidence_id)?.source ?? "Evidence record" : "Evidence record";

  return <section className="cv-page">
    <header className="cv-header"><div><span className="cv-kicker">EXPLORE / CONDITIONS</span><h1>Where does it work?</h1><p>Grouped history · not a prediction</p></div><span className={`cv-result-status ${experiment.mode === "demo" ? "example" : experiment.mode}`}>{experiment.mode === "demo" ? "Example evidence" : experiment.mode === "measured" ? "Measured evidence" : "Research pending"}</span></header>

    <section className="cv-chart-section" aria-labelledby="cv-equity-title"><div className="cv-section-head"><div><span className="cv-kicker">ORIGINAL STRATEGY</span><h2 id="cv-equity-title">The strategy’s result over time</h2></div><span className="cv-scope">{equityScope}</span></div><ResearchChart data={experiment.equity} series={["base"]} selectedDate={selectedDate} onSelectDate={onSelectDate} label="Original strategy · indexed value" mode={experiment.mode} height={410} reveal /></section>

    <details className="cv-about"><summary><Info size={16} />About this evidence</summary><p>This report supplies grouped results for market situations. A time-aligned trend and volatility trace was not supplied, so the context below cannot be lined up to individual chart points.</p><p>The interval is the likely range supplied by the research run. It is descriptive evidence, not proof of causation or future performance.</p></details>

    <section className="cv-patterns" aria-labelledby="cv-pattern-title"><header className="cv-section-head"><div><span className="cv-kicker">GROUPED EVIDENCE</span><h2 id="cv-pattern-title">Recorded market situations</h2></div><span className="cv-scope">{regimeScope}</span></header>{regimes.length ? <><IntervalGraphic regimes={regimes} selectedId={selectedRegimeId} onSelect={setSelectedRegimeId} demo={experiment.mode === "demo"} />{selectedRegime && <SituationDetail regime={selectedRegime} scope={regimeScope} source={selectedSource} demo={experiment.mode === "demo"} onEvidence={onEvidence} onClose={() => setSelectedRegimeId(null)} />}</> : <div className="cv-empty"><Info size={17} /><p>No grouped market situations were recorded for this research run.</p></div>}</section>

    <details className="cv-explainer"><summary><MousePointer2 size={15} />How to read the interval</summary><p>The line is the strategy’s indexed result. The grouped rows are a separate training summary. A wider interval means more uncertainty.</p></details>
  </section>;
}
