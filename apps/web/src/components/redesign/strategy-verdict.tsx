"use client";

import { ArrowUpRight, CircleHelp, ShieldCheck } from "lucide-react";
import type { Experiment, Strategy } from "./types";
import "./strategy-verdict.css";

export type StrategyVerdictKey = "keep" | "restrict" | "monitor" | "kill" | "not_proven";

export type StrategyVerdict = {
  key: StrategyVerdictKey;
  label: "Keep" | "Restrict" | "Monitor" | "Kill" | "Not proven";
  reason: string;
  source: string;
  example: boolean;
  canShowEvidence: boolean;
};

const sourceLabel = (strategy: Strategy) => {
  if (strategy.source === "native_report") return "Recorded research";
  if (strategy.status === "demo") return "Example data";
  if (strategy.source === "strategy_definition" || strategy.definition) return "Rule definition";
  if (strategy.kind === "positions") return "Position history";
  if (strategy.kind === "trades") return "Trade history";
  return "Strategy source";
};

const sentence = (value: string | null | undefined) => {
  const trimmed = value?.trim();
  if (!trimmed) return "";
  return /[.!?]$/.test(trimmed) ? trimmed : `${trimmed}.`;
};

const pendingReason = (strategy: Strategy, experiment: Experiment | null) => {
  if (strategy.definition || strategy.status === "draft") {
    return "The rule is saved, but market data and the research evaluator are still missing.";
  }
  if (!experiment) {
    return "The strategy is saved, but a verified research result has not been produced yet.";
  }
  if (experiment.status === "queued") return "The request is saved, but the evaluator has not started it yet.";
  if (experiment.status === "running") return "The evaluator is still working; a verdict will wait for the completed evidence.";
  if (experiment.status === "awaiting_engine") return "The strategy is saved, but the research evaluator is not connected yet.";
  if (experiment.status === "failed") return "The evaluator stopped before it produced a complete, reviewable result.";
  return "The supplied evidence does not prove a keep-or-kill decision yet.";
};

/**
 * Convert an evaluator verdict into the short decision language used by the
 * platform shell. This function only maps an explicit API verdict; it never
 * infers a decision from returns, drawdown or a chart.
 */
export function getStrategyVerdict(strategy: Strategy | null, experiment: Experiment | null): StrategyVerdict {
  const safeStrategy = strategy ?? ({
    name: "Unselected strategy",
    symbol: "",
    status: "draft",
    source: "",
    kind: "positions",
  } as Strategy);
  const example = safeStrategy.status === "demo" || experiment?.mode === "demo";
  const source = sourceLabel(safeStrategy);
  const completed = experiment?.status === "completed" && experiment.mode !== "pending";
  const canShowEvidence = Boolean(completed && experiment?.evidence?.length);

  if (!completed || !experiment?.verdict) {
    return {
      key: "not_proven",
      label: "Not proven",
      reason: pendingReason(safeStrategy, experiment),
      source,
      example,
      canShowEvidence,
    };
  }

  const verdict = experiment.verdict;
  const mapped: Record<Exclude<Experiment["verdict"], "INCONCLUSIVE">, { key: StrategyVerdictKey; label: StrategyVerdict["label"]; reason: string }> = {
    CONDITIONAL: {
      key: "restrict",
      label: "Restrict",
      reason: "The recorded research supports use only under the conditions described in the evidence.",
    },
    KEEP: {
      key: "keep",
      label: "Keep",
      reason: "The recorded research supports keeping this strategy for human review.",
    },
    MONITOR: {
      key: "monitor",
      label: "Monitor",
      reason: "The recorded research calls for continued monitoring before the next step.",
    },
    KILL: {
      key: "kill",
      label: "Kill",
      reason: "The recorded research marks this strategy for a kill review before anyone acts.",
    },
  };
  const result = verdict === "INCONCLUSIVE"
    ? { key: "not_proven" as const, label: "Not proven" as const, reason: "The supplied evidence does not prove a keep-or-kill decision yet." }
    : mapped[verdict];
  const reportReason = sentence(experiment.recommendation);
  // Keep the verdict readable while allowing an API-provided recommendation
  // to add one precise, source-backed clause when it is available.
  const reason = reportReason && reportReason.length < 220
    ? reportReason
    : result.reason;

  return { ...result, reason, source, example, canShowEvidence };
}

type Props = {
  strategy: Strategy;
  experiment: Experiment | null;
  loading?: boolean;
  onEvidence?: () => void;
  /** Secondary surfaces use one quiet context line instead of repeating the hero. */
  compact?: boolean;
};

export default function StrategyVerdict({ strategy, experiment, loading = false, onEvidence, compact = false }: Props) {
  const result = getStrategyVerdict(strategy, experiment);
  const titleId = `strategy-verdict-${strategy.strategy_id}`;
  const label = loading ? "Checking evidence" : result.label;
  const reason = loading ? "Reading the saved research record before showing a verdict." : result.reason;
  const compactScope = experiment?.verdict_scope === "always_on" ? "Original strategy" : "Research verdict";

  if (compact) {
    return <div
      className={`svd-compact-row svd-${result.key}${result.example ? " svd-example" : ""}`}
      aria-label={`${compactScope}: ${label}. ${strategy.name}. Source: ${result.source}.`}
      data-guide-target="strategy-verdict"
    >
      <span className="svd-compact-dot" aria-hidden="true" />
      <strong className="svd-compact-label">{compactScope}: {label}</strong>
      <span className="svd-compact-name">{strategy.name}</span>
      <span className="svd-compact-source">{result.source}{result.example ? " · Illustrative example" : ""}</span>
      {result.canShowEvidence && onEvidence && <button type="button" className="svd-compact-action" onClick={onEvidence}>See evidence<ArrowUpRight size={14} aria-hidden="true" /></button>}
    </div>;
  }

  return <section
    className={`svd-banner svd-${result.key}${result.example ? " svd-example" : ""}`}
    aria-labelledby={titleId}
    aria-busy={loading}
    data-guide-target="strategy-verdict"
  >
    <div className="svd-heading">
      <div className="svd-meta">
        <span className="svd-kicker"><ShieldCheck size={14} aria-hidden="true" />{experiment?.verdict_scope === "always_on" ? "Always-on strategy verdict" : "Strategy verdict"}</span>
        <span className="svd-source">{strategy.name}{strategy.symbol ? ` · ${strategy.symbol}` : ""}{result.example ? "" : ` · ${result.source}`}</span>
      </div>
      {result.example && <span className="svd-example-tag">Illustrative example</span>}
    </div>
    <div className="svd-decision">
      <div className="svd-label-row"><span className="svd-dot" aria-hidden="true" /><h1 id={titleId}>{label}</h1></div>
      <p>{reason}</p>
    </div>
    {result.canShowEvidence && onEvidence && <button type="button" className="svd-evidence" onClick={onEvidence}>
      <CircleHelp size={15} aria-hidden="true" />See evidence<ArrowUpRight size={15} aria-hidden="true" />
    </button>}
  </section>;
}
