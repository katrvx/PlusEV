"use client";

import { useState } from "react";
import { ArrowUpRight, Search, SlidersHorizontal, Upload } from "lucide-react";
import type { Experiment, Strategy } from "./types";
import KineticText from "./kinetic-text";
import { MascotCallout } from "./mascot";
import "./portfolio.css";

export type PortfolioProps = {
  strategies: Strategy[];
  experiments: Experiment[];
  loading: boolean;
  onSelect: (strategy: Strategy) => void;
  onImport: () => void;
};

type Verdict = "keep" | "restrict" | "monitor" | "kill" | "not_proven" | "example";

const verdictPriority: Verdict[] = ["kill", "restrict", "not_proven", "monitor", "keep", "example"];

const verdictLabel: Record<Verdict, string> = {
  keep: "Keep",
  restrict: "Restrict",
  monitor: "Monitor",
  kill: "Kill",
  not_proven: "Not proven",
  example: "Example",
};

const verdictFromExperiment = (experiment: Experiment | undefined, strategy: Strategy): Verdict => {
  // A demo is useful for orientation, but it must never read like a measured call.
  if (strategy.status === "demo" || experiment?.mode === "demo") return "example";
  if (!experiment || experiment.status !== "completed" || experiment.mode === "pending") return "not_proven";
  switch (experiment.verdict) {
    case "CONDITIONAL": return "restrict";
    case "KEEP": return "keep";
    case "MONITOR": return "monitor";
    case "KILL": return "kill";
    default: return "not_proven";
  }
};

const latestExperiment = (experiments: Experiment[], strategyId: string) => experiments
  .filter(item => item.strategy_id === strategyId)
  .sort((a, b) => Date.parse(b.created_at || "") - Date.parse(a.created_at || ""))[0];

const reasonFor = (strategy: Strategy, experiment: Experiment | undefined, verdict: Verdict) => {
  if (verdict === "example") return "Illustrative workspace example. Inspect the evidence before treating it as a decision.";
  if (strategy.status === "draft" || strategy.readiness === "awaiting_market_data") return "Rule saved; market data and evaluation are still pending.";
  if (strategy.kind === "trades" || strategy.status === "diagnosis_only") return "Completed trades are for diagnosis; no keep or cut call is proven.";
  if (!experiment) return "No research run has been recorded for this strategy.";
  if (experiment.status !== "completed" || experiment.mode === "pending") return experiment.message || "The evaluator has not produced a measured result.";
  return experiment.recommendation || "The report has no one-line recommendation yet. Open the evidence trail.";
};

const shortSymbol = (strategy: Strategy) => [strategy.symbol, strategy.timeframe].filter(Boolean).join(" · ") || "Details pending";

function FilterButton({ value, selected, count, onClick }: { value: Verdict | "all"; selected: boolean; count: number; onClick: () => void }) {
  const label = value === "all" ? "All" : verdictLabel[value];
  return <button type="button" className={`pf-filter${selected ? " is-selected" : ""}`} aria-pressed={selected} onClick={onClick}>
    <span>{label}</span><small>{count}</small>
  </button>;
}

function PortfolioRow({ strategy, experiment, verdict, onSelect }: { strategy: Strategy; experiment?: Experiment; verdict: Verdict; onSelect: (strategy: Strategy) => void }) {
  const reason = reasonFor(strategy, experiment, verdict);
  return <article className="pf-row" data-verdict={verdict} role="listitem">
    <div className="pf-row-verdict">
      <span className="pf-verdict" data-verdict={verdict}>{verdictLabel[verdict]}</span>
      {strategy.status === "demo" && <span className="pf-example-label">Recorded example</span>}
    </div>
    <div className="pf-row-strategy"><h3>{strategy.name || "Unnamed strategy"}</h3><p>{shortSymbol(strategy)} · {strategy.kind === "trades" ? "trade history" : strategy.kind === "positions" ? "positions" : "rule definition"}</p></div>
    <div className="pf-row-reason"><span className="pf-row-label">Why this call</span><p>{reason}</p></div>
    <button type="button" className="pf-row-action" onClick={() => onSelect(strategy)}>
      Review strategy <ArrowUpRight size={16} aria-hidden="true" />
    </button>
  </article>;
}

export default function Portfolio({ strategies, experiments, loading, onSelect, onImport }: PortfolioProps) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Verdict | "all">("all");

  const records = strategies.map(strategy => {
    const experiment = latestExperiment(experiments, strategy.strategy_id);
    const verdict = verdictFromExperiment(experiment, strategy);
    return { strategy, experiment, verdict };
  });
  const normalizedQuery = query.trim().toLowerCase();
  const visible = records
    .filter(record => filter === "all" || record.verdict === filter)
    .filter(record => !normalizedQuery || `${record.strategy.name} ${record.strategy.symbol} ${record.strategy.timeframe}`.toLowerCase().includes(normalizedQuery))
    .sort((a, b) => {
      const verdictDelta = verdictPriority.indexOf(a.verdict) - verdictPriority.indexOf(b.verdict);
      return verdictDelta || a.strategy.name.localeCompare(b.strategy.name);
    });

  const counts = records.reduce<Record<Verdict, number>>((total, record) => {
    total[record.verdict] += 1;
    return total;
  }, { keep: 0, restrict: 0, monitor: 0, kill: 0, not_proven: 0, example: 0 });

  return <section className="pf-page" aria-labelledby="pf-title">
    <header className="pf-hero">
      <div className="pf-hero-copy">
        <span className="pf-kicker">PLATFORM TRIAGE</span>
        <h1 id="pf-title"><KineticText trigger="mount">Every strategy. A defensible call.</KineticText></h1>
        <p>See which strategies have earned a keep, restrict or kill conversation — and which ones still need evidence.</p>
        <p className="pf-hero-note">The agents propose. Code tests. A human decides.</p>
      </div>
      <MascotCallout pose="bull-frame-region" title="Start with the call." className="pf-hero-mascot">
        Evidence stays one click away. Nothing changes by itself.
      </MascotCallout>
    </header>

    <section className="pf-triage" data-guide-target="portfolio-verdicts" aria-labelledby="pf-triage-title">
      <div className="pf-section-head"><div><span className="pf-kicker">DECISIONS TO REVIEW</span><h2 id="pf-triage-title">What deserves your attention?</h2></div><span className="pf-count">{strategies.length} {strategies.length === 1 ? "strategy" : "strategies"}</span></div>
      <div className="pf-toolbar" aria-label="Filter strategies">
        <label className="pf-search"><Search size={17} aria-hidden="true" /><span className="pf-visually-hidden">Search strategies</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search by name or symbol" /></label>
        <div className="pf-filter-group"><SlidersHorizontal size={16} aria-hidden="true" />{(["all", ...verdictPriority] as const).map(value => <FilterButton key={value} value={value} selected={filter === value} count={value === "all" ? records.length : counts[value]} onClick={() => setFilter(value)} />)}</div>
      </div>

      {loading ? <div className="pf-empty" role="status"><span className="pf-loading-line" aria-hidden="true" /><p>Loading the strategy register.</p></div>
        : strategies.length === 0 ? <div className="pf-empty pf-empty-action"><MascotCallout pose="bear-question" title="Nothing to review yet.">Add one strategy to create the first evidence trail.</MascotCallout><button type="button" className="pf-primary" onClick={onImport}><Upload size={16} aria-hidden="true" />Verify a strategy <ArrowUpRight size={16} aria-hidden="true" /></button></div>
          : visible.length === 0 ? <div className="pf-empty"><h3>No strategies match that filter.</h3><p>Try another search or show all verdicts.</p><button type="button" className="pf-text-action" onClick={() => { setQuery(""); setFilter("all"); }}>Clear filters</button></div>
            : <div className="pf-list" role="list" aria-label="Strategies sorted by verdict"><div className="pf-list-head" aria-hidden="true"><span>Verdict</span><span>Strategy</span><span>Reason</span><span /></div>{visible.map(record => <PortfolioRow key={record.strategy.strategy_id} {...record} onSelect={onSelect} />)}</div>}
    </section>

    {strategies.length > 0 && <footer className="pf-footer"><span>Verdicts are evidence-linked proposals.</span><button type="button" className="pf-primary" data-guide-target="portfolio-action" onClick={onImport}><Upload size={16} aria-hidden="true" />Verify another strategy</button></footer>}
  </section>;
}
