"use client";

import {
  ArrowRight,
  Download,
  FileInput,
  FileText,
  FlaskConical,
  LockKeyhole,
  Play,
  RefreshCw,
  Upload,
} from "lucide-react";
import type { Experiment, Health, Strategy } from "./types";
import type { StrategyDefinition } from "../../../../../packages/contracts/types";
import { API_ROUTES } from "../../../../../packages/contracts/api";
import ResearchChart from "./research-chart";
import KineticText from "./kinetic-text";
import { MascotCallout } from "./mascot";
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

type StrategyRecord = Omit<Strategy, "source"> & {
  source?: string;
  definition?: StrategyDefinition;
};

const strategyRecord = (strategy: Strategy) => strategy as StrategyRecord;
const isDefinitionStrategy = (strategy: Strategy) => strategyRecord(strategy).source === "strategy_definition";
const isNativeReportSource = (source?: string) => source === "native_report" || source === "native_report_example";
const familyLabel = (family?: StrategyDefinition["rule"]["family"]) => family === "ema_crossover"
  ? "EMA crossover"
  : family === "rsi_mean_reversion"
    ? "RSI mean reversion"
    : "Supported rule";
const parameterLabel = (rule?: StrategyDefinition["rule"]) => {
  if (!rule) return "Rule details pending";
  if (rule.family === "ema_crossover") return `Fast ${rule.fast_period} · slow ${rule.slow_period}`;
  return `Period ${rule.period} · enter below ${rule.entry_below} · exit above ${rule.exit_above}`;
};

const dateLabel = (value?: string | null) => {
  if (!value) return "Not recorded";
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
  if (value === null || value === undefined || !Number.isFinite(value)) return "Not recorded";
  return Math.round(value).toLocaleString("en-GB");
};

const bpsLabel = (value?: number | null) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "Not recorded";
  return `${value} bps`;
};

function StatusLine({ tone = "quiet", children }: { tone?: "accent" | "success" | "danger" | "quiet"; children: React.ReactNode }) {
  return <p className="sv-status" data-tone={tone}><span className="sv-status-dot" aria-hidden="true" />{children}</p>;
}

function EmptyStrategy({ onImport, onExample }: Pick<Props, "onImport" | "onExample">) {
  return <section className="sv-empty" aria-labelledby="sv-empty-title">
    <div className="sv-kicker">STRATEGY DEFINITION</div>
    <h1 id="sv-empty-title"><KineticText trigger="mount">Define the rules.</KineticText></h1>
    <p className="sv-empty-invite"><strong>Add your strategy.</strong> Start with a small, inspectable rule. Add market history later as supporting evidence for the research.</p>
    <div className="sv-empty-actions">
      <button type="button" className="sv-action sv-action-primary kk-primary-button" onClick={onImport}><Upload size={16} aria-hidden="true" />Define your strategy <ArrowRight size={15} aria-hidden="true" /></button>
      <button type="button" className="sv-action sv-action-secondary" onClick={onExample}><FlaskConical size={16} aria-hidden="true" />Open the example</button>
    </div>
    <MascotCallout pose="bull-welcome" title="Start with a rule you can inspect." className="sv-mascot-callout">
      Keep the source definition stable while the evaluator checks where it holds up.
    </MascotCallout>
    <p className="sv-file-note"><FileInput size={15} aria-hidden="true" />JSON strategy definition · market history can come later</p>
    <div className="sv-empty-steps" aria-label="What happens after adding a strategy">
      <div><span>01</span><strong>Define the rule</strong><p>Choose a supported family and make its boundaries explicit.</p></div>
      <div><span>02</span><strong>Review assumptions</strong><p>Check the market, timing and costs before anything is evaluated.</p></div>
      <div><span>03</span><strong>Add evidence later</strong><p>Keep history separate so the source rule stays inspectable.</p></div>
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
  const definition = isDefinitionStrategy(strategy);
  const nativeReport = isNativeReportSource(strategy.source);
  const payload = strategyRecord(strategy).definition;
  return <details className="sv-disclosure">
    <summary>Data &amp; assumptions</summary>
    <div className="sv-disclosure-grid">
      <div><span>Input</span><strong>{definition ? "Rule definition" : nativeReport ? "Saved research report" : strategy.kind === "positions" ? "Timestamped positions" : "Completed trades"}</strong></div>
      <div><span>Source</span><strong>{definition ? "Strategy definition" : nativeReport ? "Native research report" : strategy.source || "Imported file"}</strong></div>
      {definition && <><div><span>Rule family</span><strong>{familyLabel(payload?.rule.family)}</strong></div><div><span>Parameters</span><strong>{parameterLabel(payload?.rule)}</strong></div></>}
      <div><span>File hash</span><strong>{strategy.dataset_hash || "Not recorded"}</strong></div>
      <div><span>Execution</span><strong>{assumptions.execution || "Not specified"}</strong></div>
      <div><span>Timezone</span><strong>{assumptions.timezone || "Not set"}</strong></div>
      <div><span>Notes</span><strong>{assumptions.description || "No additional notes"}</strong></div>
    </div>
  </details>;
}

function ResearchState({ strategy, experiment, health, onRun, onExample, running }: { strategy: Strategy; experiment: Experiment | null; health: Health | null; onRun: () => void; onExample: () => void; running: boolean }) {
  if (strategy.kind === "trades" || strategy.status === "diagnosis_only") {
    return <div className="sv-research-state sv-research-state-note"><FileText size={17} aria-hidden="true" /><span>Completed trades are for diagnosis. Add position history to test an on/off rule.</span></div>;
  }

  const isDemo = strategy.status === "demo";
  const isNativeReport = isNativeReportSource(strategy.source);
  const isDefinition = isDefinitionStrategy(strategy);
  const engineAvailable = health?.research_engine === true;
  const canRun = isDemo || (!isDefinition && engineAvailable);
  const isActive = running || experiment?.status === "queued" || experiment?.status === "running";

  if (isNativeReport) {
    return <div className="sv-run-row"><StatusLine tone="accent">Saved verdict</StatusLine><button type="button" className="sv-action sv-action-primary kk-primary-button" onClick={onExample}><FileText size={15} aria-hidden="true" />Open saved verdict <ArrowRight size={15} aria-hidden="true" /></button></div>;
  }

  if (experiment?.status === "queued") {
    return <div className="sv-research-state sv-research-state-note" role="status" aria-live="polite"><LockKeyhole size={17} aria-hidden="true" /><span>Request saved. Waiting to start.</span></div>;
  }

  if (isDefinition && !experiment && !running) {
    return <div className="sv-research-state sv-research-state-note" role="status" aria-live="polite"><LockKeyhole size={17} aria-hidden="true" /><span>Research is not available yet.</span></div>;
  }

  if (running || experiment?.status === "running") {
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
  const isNativeReport = isNativeReportSource(strategy.source);
  const isDefinition = isDefinitionStrategy(strategy);
  const period = strategy.date_start && strategy.date_end ? `${dateLabel(strategy.date_start)} → ${dateLabel(strategy.date_end)}` : "Not recorded";
  const definition = strategyRecord(strategy).definition;
  const enginePending = !isDefinition && !isDemo && health?.research_engine !== true;
  const mascotPose = isNativeReport
      ? "bull-take-note"
      : experiment?.status === "failed"
        ? "bull-neutral"
      : isDefinition
          ? "bull-read-sheet"
          : experiment?.status === "queued"
            ? "bull-read-sheet"
            : running || experiment?.status === "running"
              ? "bull-take-note"
              : isDemo
                ? "bull-take-note"
                : "bull-read-sheet";
  const mascotTitle = isNativeReport
      ? "Saved verdict."
      : experiment?.status === "failed"
        ? "Research needs another pass."
        : isDefinition
          ? "Rules saved."
          : experiment?.status === "queued"
            ? "Request saved."
            : running || experiment?.status === "running"
              ? "Research is running."
              : experiment?.status === "completed"
                ? "Result ready."
                : enginePending
                  ? "Research engine pending."
                  : isDemo
                    ? "Example ready."
                    : "Next: test the conditions.";
  const mascotCopy = isNativeReport
      ? "Open the saved verdict and evidence. No new run is started."
      : experiment?.status === "failed"
        ? "The last run did not finish. Review the message below before trying again."
        : isDefinition
          ? "Market data and the research engine are still pending."
          : experiment?.status === "queued"
            ? "Waiting to start."
            : running || experiment?.status === "running"
              ? "The research engine is checking the supplied data."
              : experiment?.status === "completed"
                ? "Read the chart, conditions and evidence before saving a paper plan."
                : enginePending
                  ? "Your strategy is saved. No measured result is estimated here."
                  : isDemo
                    ? "Run the example to see how the workspace traces a result."
                    : "Run the research to see where this strategy holds up.";

  return <div className="sv-page">
    <header className="sv-heading sv-heading-with-mascot" aria-labelledby="sv-source-title">
      <div className="sv-heading-copy"><span className="sv-kicker">SOURCE &amp; ASSUMPTIONS</span><h2 id="sv-source-title" className="sv-source-heading"><KineticText trigger="mount">Source and assumptions.</KineticText></h2><p className="sv-subtitle">{strategy.name}</p></div>
      <MascotCallout pose={mascotPose} title={mascotTitle} className="sv-mascot-callout sv-mascot-callout-intro">{mascotCopy}</MascotCallout>
    </header>

    {isNativeReport ? <div className="sv-notice" role="note"><FileText size={15} aria-hidden="true" /><span>Saved research report — read-only. No new run is started.</span></div> : isDemo && <div className="sv-notice" role="note"><FlaskConical size={15} aria-hidden="true" /><span>Example data — illustrative, not measured performance.</span></div>}

    <section className="sv-check" aria-labelledby="sv-check-title" data-guide-target="strategy-input">
      <h2 id="sv-check-title" className="sv-visually-hidden">Strategy details</h2>
      {isDefinition ? <div className="sv-definition-summary" aria-label="Strategy definition details">
        <div className="sv-definition-lead"><div><span>RULE DEFINITION</span><strong>{strategy.name || "Your strategy"}</strong><p>{familyLabel(definition?.rule.family)} · saved rules</p></div><span className="sv-definition-badge">Source rule</span></div>
        <dl className="sv-definition-facts"><div><dt>Market</dt><dd>{strategy.symbol || "Pending market"}</dd></div><div><dt>Timeframe</dt><dd>{strategy.timeframe || "Pending"}</dd></div><div><dt>Parameters</dt><dd>{parameterLabel(definition?.rule)}</dd></div><div><dt>Research</dt><dd>Pending engine</dd></div></dl>
      </div> : <div className="sv-meta-row" aria-label="Strategy details">
        <div><span>Symbol</span><strong>{strategy.symbol}</strong></div>
        <div><span>Timeframe</span><strong>{strategy.timeframe}</strong></div>
        <div><span>Period</span><strong>{period}</strong></div>
        <div><span>Rows</span><strong>{isNativeReport ? "Not recorded" : countLabel(strategy.row_count)}</strong></div>
      </div>}
      <CostRows strategy={strategy} />
    </section>

    {isDefinition ? <section className="sv-research sv-definition-actions" aria-labelledby="sv-research-title" data-guide-target="strategy-action">
      <div className="sv-section-heading"><div><span className="sv-kicker">NEXT ACTION</span><h2 id="sv-research-title">Next action.</h2></div></div>
      <div className="sv-definition-actions-row">
        <a className="sv-action sv-action-primary kk-primary-button" href={API_ROUTES.strategyDefinition(strategy.strategy_id)} download><Download size={15} aria-hidden="true" />Download rules</a>
        <button type="button" className="sv-action sv-action-secondary" onClick={onImport}><Upload size={15} aria-hidden="true" />Add another strategy</button>
      </div>
    </section> : <section className="sv-research" aria-labelledby="sv-research-title" data-guide-target="strategy-action">
      <div className="sv-section-heading"><div><span className="sv-kicker">NEXT ACTION</span><h2 id="sv-research-title"><KineticText trigger="scroll">Next action.</KineticText></h2></div></div>
      <ResearchState strategy={strategy} experiment={experiment} health={health} onRun={onRun} onExample={onExample} running={running} />
    </section>}

    <DataDisclosure strategy={strategy} />

    {experiment && <ExperimentResult experiment={experiment} />}
  </div>;
}
