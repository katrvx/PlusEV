"use client";

import {
  ArrowRight,
  FileInput,
  FileText,
  FlaskConical,
  LockKeyhole,
  Play,
  RefreshCw,
  Upload,
} from "lucide-react";
import type { Experiment, Health, Strategy } from "./types";
import ResearchChart from "./research-chart";
import "./strategy-view.css";

type Props = {
  strategy: Strategy | null;
  experiment: Experiment | null;
  health: Health | null;
  onImport: () => void;
  onExample: () => void;
  onRun: () => void;
  running: boolean;
};

const dateLabel = (value?: string | null) => {
  if (!value) return "Not available";
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(parsed);
};

const countLabel = (value?: number | null) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "Not available";
  return Math.round(value).toLocaleString("en-GB");
};

const bpsLabel = (value?: number | null) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "Not set";
  return `${value} bps`;
};

function StatusLine({ tone = "quiet", children }: { tone?: "accent" | "success" | "danger" | "quiet"; children: React.ReactNode }) {
  return <p className="sv-status" data-tone={tone}><span className="sv-status-dot" aria-hidden="true" />{children}</p>;
}

function EmptyStrategy({ onImport, onExample }: Pick<Props, "onImport" | "onExample">) {
  return <section className="sv-empty" aria-labelledby="sv-empty-title">
    <div className="sv-kicker">STRATEGY INTAKE</div>
    <h1 id="sv-empty-title">Test your strategy.</h1>
    <p className="sv-empty-invite"><strong>Add your strategy.</strong> Bring a timestamped export and let the research agents look for where it holds up, where it weakens, and what still needs evidence.</p>
    <div className="sv-empty-actions">
      <button type="button" className="sv-action sv-action-primary kk-primary-button" onClick={onImport}><Upload size={16} aria-hidden="true" />Choose a file <ArrowRight size={15} aria-hidden="true" /></button>
      <button type="button" className="sv-action sv-action-secondary" onClick={onExample}><FlaskConical size={16} aria-hidden="true" />Open the example</button>
    </div>
    <p className="sv-file-note"><FileInput size={15} aria-hidden="true" />CSV or Parquet · timestamped signals or target positions</p>
    <div className="sv-empty-steps" aria-label="What happens after adding a strategy">
      <div><span>01</span><strong>Check the data</strong><p>We show the columns and coverage before anything runs.</p></div>
      <div><span>02</span><strong>Inspect the history</strong><p>Agents compare the original strategy with dated evidence.</p></div>
      <div><span>03</span><strong>Decide what to test</strong><p>Any proposed change stays separate from your original file.</p></div>
    </div>
  </section>;
}

function CostRows({ strategy }: { strategy: Strategy }) {
  const { assumptions } = strategy;
  return <div className="sv-costs-row" aria-label="Cost assumptions">
    <div className="sv-cost"><span>Trading fee</span><strong>{bpsLabel(assumptions.fee_bps)}</strong></div>
    <div className="sv-cost"><span>Slippage</span><strong>{bpsLabel(assumptions.slippage_bps)}</strong></div>
  </div>;
}

function DataDisclosure({ strategy }: { strategy: Strategy }) {
  const { assumptions } = strategy;
  return <details className="sv-disclosure">
    <summary>Data &amp; assumptions</summary>
    <div className="sv-disclosure-grid">
      <div><span>Input</span><strong>{strategy.kind === "positions" ? "Timestamped positions" : "Completed trades"}</strong></div>
      <div><span>Source</span><strong>{strategy.source || "Imported file"}</strong></div>
      <div><span>File hash</span><strong>{strategy.dataset_hash || "Not available"}</strong></div>
      <div><span>Execution</span><strong>{assumptions.execution || "Not specified"}</strong></div>
      <div><span>Timezone</span><strong>{assumptions.timezone || "Not set"}</strong></div>
      <div><span>Notes</span><strong>{assumptions.description || "No additional notes"}</strong></div>
    </div>
  </details>;
}

function ResearchState({ strategy, experiment, health, onRun, running }: { strategy: Strategy; experiment: Experiment | null; health: Health | null; onRun: () => void; running: boolean }) {
  if (strategy.kind === "trades" || strategy.status === "diagnosis_only") {
    return <div className="sv-research-state sv-research-state-note"><FileText size={17} aria-hidden="true" /><span>Completed trades are for diagnosis. Add position history to test an on/off rule.</span></div>;
  }

  const isDemo = strategy.status === "demo";
  const engineAvailable = health?.research_engine === true;
  const canRun = isDemo || engineAvailable;
  const isActive = running || experiment?.status === "queued" || experiment?.status === "running";

  if (isActive) {
    return <div className="sv-research-state" role="status" aria-live="polite"><RefreshCw className="sv-state-icon-spin" size={17} aria-hidden="true" /><span>Research is running{experiment?.message ? ` · ${experiment.message}` : ""}</span></div>;
  }

  if (!canRun) {
    return <div className="sv-research-state sv-research-state-note"><LockKeyhole size={17} aria-hidden="true" /><span>Research engine pending. Your file is ready; no result is estimated here.</span></div>;
  }

  if (experiment?.status === "failed") {
    return <div className="sv-research-state sv-research-state-note"><RefreshCw size={17} aria-hidden="true" /><span>Last run did not finish{experiment.message ? ` · ${experiment.message}` : ""}</span><button type="button" className="sv-inline-action" onClick={onRun}>Try again <ArrowRight size={14} aria-hidden="true" /></button></div>;
  }

  return <div className="sv-run-row"><StatusLine tone={isDemo ? "accent" : "quiet"}>{isDemo ? "Example" : experiment ? "Ready again" : "Ready"}</StatusLine><button type="button" className="sv-action sv-action-primary kk-primary-button" onClick={onRun} disabled={isActive} aria-busy={isActive}><Play size={15} aria-hidden="true" />{isDemo ? "Run example" : experiment ? "Run again" : "Run research"}<ArrowRight size={15} aria-hidden="true" /></button></div>;
}

function ExperimentResult({ experiment }: { experiment: Experiment }) {
  const isDemo = experiment.mode === "demo";
  if (experiment.status !== "completed" || experiment.equity.length === 0) {
    if (experiment.status === "awaiting_engine" || experiment.mode === "pending") {
      return <div className="sv-result-empty" role="status"><LockKeyhole size={16} aria-hidden="true" /><span>{experiment.message || "Measured results will appear here when the research engine is connected."}</span></div>;
    }
    return null;
  }

  return <section className="sv-result" aria-labelledby="sv-result-title">
    <div className="sv-section-heading"><div><h2 id="sv-result-title">{isDemo ? "Example curve." : "Recorded curve."}</h2></div><StatusLine tone={isDemo ? "accent" : "success"}>{isDemo ? "Illustrative" : "Measured"}</StatusLine></div>
    <div className="sv-chart-wrap"><ResearchChart data={experiment.equity} series={["base", "cash"]} label="Original strategy value" mode={experiment.mode} height={310} reveal /></div>
    <div className="sv-chart-caption"><span><i className="sv-line sv-line-original" />Original strategy</span><span><i className="sv-line sv-line-cash" />Cash reference</span><span>{experiment.windows.test && experiment.windows.test !== "pending" ? experiment.windows.test : "Recorded period"}</span></div>
  </section>;
}

export default function StrategyView({ strategy, experiment, health, onImport, onExample, onRun, running }: Props) {
  if (!strategy) return <div className="sv-page"><EmptyStrategy onImport={onImport} onExample={onExample} /></div>;

  const isDemo = strategy.status === "demo";
  const title = experiment ? "Check your strategy." : "Ready to investigate.";
  const period = strategy.date_start && strategy.date_end ? `${dateLabel(strategy.date_start)} → ${dateLabel(strategy.date_end)}` : "Coverage not available";

  return <div className="sv-page">
    <header className="sv-heading">
      <div><h1>{title}</h1><p className="sv-subtitle">{strategy.name}</p></div>
    </header>

    {isDemo && <div className="sv-notice" role="note"><FlaskConical size={15} aria-hidden="true" /><span>Example data — illustrative, not measured performance.</span></div>}

    <section className="sv-check" aria-labelledby="sv-check-title">
      <h2 id="sv-check-title" className="sv-visually-hidden">Strategy details</h2>
      <div className="sv-meta-row" aria-label="Strategy details">
        <div><span>Symbol</span><strong>{strategy.symbol}</strong></div>
        <div><span>Timeframe</span><strong>{strategy.timeframe}</strong></div>
        <div><span>Period</span><strong>{period}</strong></div>
        <div><span>Rows</span><strong>{countLabel(strategy.row_count)}</strong></div>
      </div>
      <CostRows strategy={strategy} />
    </section>

    <DataDisclosure strategy={strategy} />

    <section className="sv-research" aria-labelledby="sv-research-title">
      <div className="sv-section-heading"><div><h2 id="sv-research-title">Run research.</h2></div></div>
      <ResearchState strategy={strategy} experiment={experiment} health={health} onRun={onRun} running={running} />
    </section>

    {experiment && <ExperimentResult experiment={experiment} />}
  </div>;
}
