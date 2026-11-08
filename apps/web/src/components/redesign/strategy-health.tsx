"use client";

import { ArrowUpRight, ChevronDown, CircleHelp } from "lucide-react";
import type { ReactNode } from "react";
import type { NativeStrategyHealth } from "../../../../../packages/contracts/research";
import { MascotCallout, type MascotPose } from "./mascot";
import "./strategy-health.css";

/** Native `strategy_health` from the Argon investigation reports. */
export type StrategyHealthShape = NativeStrategyHealth;
export type StrategyHealthRange = NativeStrategyHealth["train_range"];
export type StrategyHealthBlock = NativeStrategyHealth["validation_blocks"][number];

export type StrategyHealthProps = {
  health?: StrategyHealthShape | null;
  onEvidence?: (evidenceId: string) => void;
  onNext?: () => void;
};

type Range = { low: number; high: number; horizonDays: number; source: string };
type Block = { id: string; start: string; end: string; value: number; status: StrategyHealthBlock["position"] };
type NormalizedHealth = {
  range: Range | null;
  blocks: Block[];
  summary: string;
  missing: string[];
  evidenceId: string | null;
  changedAssumptions: string[];
  validationNetReturn: number | null;
  reportedBlockCount: number | null;
};

const finite = (value: number | null | undefined) => typeof value === "number" && Number.isFinite(value) ? value : null;
const text = (value: string | null | undefined) => typeof value === "string" && value.trim() ? value.trim() : "";
const validDate = (value: string) => {
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
};

function normalizeHealth(input: StrategyHealthShape | null | undefined): NormalizedHealth {
  const source: Partial<NativeStrategyHealth> = input ?? {};
  const trainRange = source.train_range;
  const low = finite(trainRange?.low);
  const high = finite(trainRange?.high);
  const horizonDays = finite(trainRange?.horizon_days);
  const range = low !== null && high !== null && high > low && horizonDays !== null && horizonDays > 0
    ? { low, high, horizonDays, source: text(trainRange?.source) || "Training evidence" }
    : null;
  const blocks: Block[] = [];
  if (range && Array.isArray(source.validation_blocks)) {
    source.validation_blocks.forEach((block, index) => {
      const start = text(block.start);
      const startTime = validDate(start);
      const value = finite(block.net_return);
      if (startTime === null || value === null) return;
      const endTime = startTime + range.horizonDays * 24 * 60 * 60 * 1000;
      if (!Number.isFinite(endTime) || !["inside", "above", "below"].includes(block.position)) return;
      blocks.push({ id: `validation-${index + 1}`, start, end: new Date(endTime).toISOString(), value, status: block.position });
    });
  }
  const missing: string[] = [];
  if (!range) missing.push("the evaluator's training range and horizon");
  if (blocks.length === 0) missing.push("dated validation blocks");
  return {
    range,
    blocks,
    summary: text(source.summary),
    missing,
    evidenceId: text(source.evidence_id) || null,
    changedAssumptions: Array.isArray(source.changed_assumptions)
      ? source.changed_assumptions.filter((value): value is string => typeof value === "string" && value.trim().length > 0)
      : [],
    validationNetReturn: finite(source.validation_net_return),
    reportedBlockCount: finite(source.n_blocks),
  };
}

function displayValue(value: number) {
  return `${value < 0 ? "−" : value > 0 ? "+" : ""}${Math.abs(value * 100).toFixed(1)}%`;
}

function displayDate(value: string) {
  const parsed = validDate(value);
  if (parsed === null) return value;
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(parsed);
}

function StatusScene({ pose, title, children }: { pose: MascotPose; title: string; children: ReactNode }) {
  return <MascotCallout pose={pose} title={title} className="sh-scene-callout">{children}</MascotCallout>;
}

export function StrategyHealth({ health, onEvidence, onNext }: StrategyHealthProps) {
  const normalized = normalizeHealth(health);
  const usable = Boolean(normalized.range && normalized.blocks.length > 0);
  if (!usable) {
    const missing = normalized.missing.length > 0 ? normalized.missing.join(" and ") : "the evaluator's training range and dated validation blocks";
    return <details className="sh-health sh-health-empty" data-guide-target="strategy-health">
      <summary className="sh-empty-summary"><span className="sh-eyebrow">STRATEGY HEALTH</span><strong>Unlucky or broken?</strong><span className="sh-empty-status">Not assessed</span><ChevronDown size={17} aria-hidden="true" /></summary>
      <div className="sh-empty-details"><p>Not assessed yet. We need {missing} before we can separate an unlucky run from a broken edge.</p>{normalized.summary && <p className="sh-source-note">{normalized.summary}</p>}</div>
    </details>;
  }

  const range = normalized.range!;
  const outsideCount = normalized.blocks.filter(block => block.status !== "inside").length;
  const insideCount = normalized.blocks.length - outsideCount;
  const reportedCount = normalized.reportedBlockCount ?? normalized.blocks.length;
  const outside = outsideCount > 0;
  const negativeValidation = normalized.validationNetReturn !== null && normalized.validationNetReturn < 0;
  const summary = `${insideCount} of ${reportedCount} validation blocks are inside the supplied training range.`;
  const pose: MascotPose = outside ? "bear-question" : negativeValidation ? "bear-point-left" : "bull-present-up";
  const title = outside
    ? `${outsideCount} block${outsideCount === 1 ? " sits" : "s sit"} outside the range.`
    : negativeValidation ? "Inside the range, but still down." : "Blocks stay inside the range.";
  const callout = outside
    ? "Investigate the changed conditions before calling the strategy broken."
    : "A familiar range is a consistency signal, not proof the strategy will profit.";
  const rangeLabel = `${displayValue(range.low)} to ${displayValue(range.high)}`;
  const chartWidth = 760;
  const chartHeight = 260;
  const chartLeft = 94;
  const chartRight = 16;
  const chartTop = 18;
  const chartBottom = 38;
  const plotWidth = chartWidth - chartLeft - chartRight;
  const plotHeight = chartHeight - chartTop - chartBottom;
  const chartValues = [range.low, range.high, 0, ...normalized.blocks.map(block => block.value)];
  const chartMin = Math.min(...chartValues);
  const chartMax = Math.max(...chartValues);
  const chartPadding = Math.max((chartMax - chartMin) * 0.12, 0.01);
  const domainLow = chartMin - chartPadding;
  const domainHigh = chartMax + chartPadding;
  const yFor = (value: number) => chartTop + (1 - ((value - domainLow) / (domainHigh - domainLow))) * plotHeight;
  const points = normalized.blocks.map((block, index) => ({
    block,
    x: chartLeft + (normalized.blocks.length === 1 ? plotWidth / 2 : (index / (normalized.blocks.length - 1)) * plotWidth),
    y: yFor(block.value),
  }));
  const zeroY = yFor(0);
  const yTicks = [range.high, ...(range.low < 0 && range.high > 0 ? [0] : []), range.low];

  return <section className="sh-health sh-health-available" data-guide-target="strategy-health" aria-labelledby="sh-title">
    <header className="sh-heading"><div><span className="sh-eyebrow">STRATEGY HEALTH</span><h2 id="sh-title">Unlucky or broken?</h2><p>{summary}</p>{normalized.summary && <details className="sh-source-details"><summary>Evaluator note <ChevronDown size={14} aria-hidden="true" /></summary><p>{normalized.summary}</p>{normalized.changedAssumptions.length > 0 && <p>Assumptions flagged: {normalized.changedAssumptions.join(", ")}.</p>}</details>}</div><span className="sh-range-label">Train range · {rangeLabel}<small>{range.source}</small></span></header>
    <div className="sh-scene">
      <div className="sh-explanation">
        <StatusScene pose={pose} title={title}>{callout}</StatusScene>
        {onNext && <button type="button" className="sh-action" onClick={onNext}>Explore conditions <ArrowUpRight size={15} /></button>}
      </div>
      <div className="sh-range-panel" data-guide-target="strategy-health-range">
        <figure className="sh-chart"><svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img" aria-labelledby="sh-chart-title sh-chart-desc">
          <title id="sh-chart-title">Validation history against the supplied training range</title>
          <desc id="sh-chart-desc">{reportedCount} dated {range.horizonDays}-day validation blocks, plotted by net return. The lavender band is the supplied training range from {displayValue(range.low)} to {displayValue(range.high)}.</desc>
          <rect className="sh-chart-band" x={chartLeft} y={yFor(range.high)} width={plotWidth} height={Math.max(0, yFor(range.low) - yFor(range.high))} rx="10" />
          {yTicks.map(value => <g key={value}><line className={value === 0 ? "sh-chart-zero" : "sh-chart-grid"} x1={chartLeft} x2={chartLeft + plotWidth} y1={yFor(value)} y2={yFor(value)} /><text className="sh-chart-label" x={chartLeft - 10} y={yFor(value) + 4} textAnchor="end">{displayValue(value)}</text></g>)}
          {points.length > 1 && <polyline className="sh-chart-line" points={points.map(point => `${point.x},${point.y}`).join(" ")} />}
          {points.map(point => <g key={point.block.id}><line className={`sh-chart-stem sh-stem-${point.block.status}`} x1={point.x} x2={point.x} y1={zeroY} y2={point.y} /><circle className={`sh-chart-point sh-point-${point.block.status}`} cx={point.x} cy={point.y} r="4" /></g>)}
          {points.length > 0 && <><text className="sh-chart-date" x={chartLeft} y={chartHeight - 12} textAnchor="start">{displayDate(points[0].block.start)}</text><text className="sh-chart-date" x={chartLeft + plotWidth} y={chartHeight - 12} textAnchor="end">{displayDate(points[points.length - 1].block.start)}</text></>}
        </svg><figcaption>Each point is one {range.horizonDays}-day validation return.</figcaption></figure>
        <div className="sh-block-summary"><strong>{insideCount} of {reportedCount} inside</strong>{normalized.validationNetReturn !== null && <span>Validation return {displayValue(normalized.validationNetReturn)}</span>}</div>
        <details className="sh-blocks-details"><summary>View dated validation history <ChevronDown size={15} aria-hidden="true" /></summary><ol className="sh-block-list" aria-label="Recorded validation blocks">{normalized.blocks.map(block => <li key={block.id}><span>{displayDate(block.start)}–{displayDate(block.end)}</span><strong>{displayValue(block.value)}</strong><small>{block.status}</small></li>)}</ol></details>
        <p className="sh-range-foot"><span className="sh-range-key" />supplied training range <span className="sh-point-key" />recorded validation block</p>
      </div>
    </div>
    <div className="sh-health-guardrail"><CircleHelp size={15} /><span>Range health is separate from profitability.</span></div>
    <footer className="sh-footer"><div className="sh-footer-actions">{normalized.evidenceId && onEvidence && <button type="button" className="sh-evidence-link" onClick={() => onEvidence(normalized.evidenceId!)}>Open health evidence</button>}{!onNext && !normalized.evidenceId && <span>Read the supplied blocks before drawing a conclusion.</span>}</div></footer>
  </section>;
}

export default StrategyHealth;
