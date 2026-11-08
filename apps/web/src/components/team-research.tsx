"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, Beaker, BookOpen, Bot, ChevronDown, ChevronRight, CircleCheck, CircleX, Clock3, Cpu, Download, FileSearch, FlaskConical, Info, LockKeyhole, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import { teamApi, type InvestigationSummary, type InvestigationWrapper, type PresentationFilter, type PresentationOutcome, type PresentationStage, type PresentationTiming, type PresentationTraceItem, type ReportPresentation, type TeamCandidate, type TeamEvidence, type TeamHypothesis, type TeamReport, type TeamTrial } from "@/lib/team-api";
import type { FrozenEvaluation, TeamContext } from "../../../../packages/contracts/research";
import { MascotCallout } from "./redesign/mascot";
import ResearchSourceBrowser from "./research-source-browser";
import "./team-research.css";

/** A difference between two policies' returns, in percentage points (matches the sealed card's "p.p."). */
const pts = (value: number | null) => value === null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)} p.p.`;
const when = (value: string) => new Date(value).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" });
const json = (value: unknown) => JSON.stringify(value, null, 2);
const splitLabel = (split: TeamTrial["split"]) => split === "train" ? "Training" : split === "validation" ? "Validation" : "New-data test";
const sourceLabel = (source: TeamTrial["source"]) => source === "agent" ? "Agent-proposed rule" : source === "meta_model" ? "Model comparison" : source === "arbiter" ? "Independent review" : "Simple rule comparison";

function reportVerdict(report: TeamReport, sealedEvaluation?: FrozenEvaluation | null) {
  if (sealedEvaluation) {
    return {
      label: "Sealed look · not proven",
      title: "Better than original. Still a loss.",
      body: "The filter reduced losses in the held-out test. Its own return range still includes zero. Kill applies to the original strategy; the filter has no new decision.",
    };
  }
  const candidate = report.verdict === "candidate_for_frozen_test" && !report.holdout_accessed;
  if (candidate) {
    return {
      label: "Candidate for a frozen test",
      title: "One rule can move to a fair test.",
      body: "An agent proposed the rule; code checked it on the recorded development splits. Human approval and a clean new-data test still stand.",
    };
  }
  return {
    label: "Not proven",
    title: "The evidence has not earned a verdict yet.",
    body: report.holdout_accessed
      ? "A holdout-access warning keeps this report from a clean verdict. Review the trial log before treating a rule as ready."
      : "Agents can propose a rule; code checks it against the recorded splits. This report does not prove a winner yet.",
  };
}

function ModeBadge({ item, compact = false }: { item: { agent_mode: string; model_id?: string | null; synthetic?: boolean }; compact?: boolean }) {
  const fallback = item.agent_mode === "deterministic_fallback";
  const mixed = item.agent_mode === "llm_with_fallback";
  const label = fallback ? "Scripted research" : mixed ? item.model_id ? `Model + scripted fallback · ${item.model_id}` : "Model + scripted fallback" : item.model_id ? `Model-assisted · ${item.model_id}` : "Model-assisted";
  const compactLabel = fallback ? "Scripted research" : mixed ? "Model + scripted fallback" : "Model-assisted";
  const title = fallback ? "Scripted research: fixed research steps and no language-model call." : mixed ? "A language model was configured, and one or more stages used scripted fallback." : item.model_id || "Model-assisted research report";
  return <span className={`tr-mode ${fallback ? "fallback" : mixed ? "mixed" : "model"}`} title={title}><span className="tr-mode-dot" />{compact ? compactLabel : label}</span>;
}

function SourceBadge({ item }: { item: { source: string; synthetic: boolean } }) {
  return <span className={`tr-source ${item.synthetic ? "synthetic" : ""}`}>{item.synthetic ? <Beaker size={12} /> : <ShieldCheck size={12} />}{item.synthetic ? "Sample market data" : "Recorded agent report"}</span>;
}

type NativeWrapperWithFrozen = InvestigationWrapper & {
  frozen_evaluation?: FrozenEvaluation | null;
  integration_audit?: { frozen_evaluation?: FrozenEvaluation | null } | null;
  report: TeamReport & {
    frozen_evaluation?: FrozenEvaluation | null;
    integration_audit?: { frozen_evaluation?: FrozenEvaluation | null } | null;
  };
};

function frozenLook(wrapper: InvestigationWrapper | null): FrozenEvaluation | null {
  if (!wrapper) return null;
  const value = wrapper as NativeWrapperWithFrozen;
  const look = value.frozen_evaluation || value.integration_audit?.frozen_evaluation || value.report.frozen_evaluation || value.report.integration_audit?.frozen_evaluation || null;
  return look && look.strategy_id === value.report.strategy_id
    && look.experiment_id === value.report.experiment_id
    && look.evaluation.policy_id === value.report.champion_policy_id ? look : null;
}

function SealedLook({ evaluation }: { evaluation: FrozenEvaluation }) {
  const look = evaluation.evaluation;
  const pctValue = (value: number) => `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
  const drawdownValue = (value: number) => `${(value * 100).toFixed(1)}%`;
  const pointsValue = (value: number) => `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)} p.p.`;
  const range = (values: [number, number], formatter: (value: number) => string) => `[${formatter(values[0])}, ${formatter(values[1])}]`;
  return <section className="tr-sealed-look" aria-labelledby="tr-sealed-title" data-guide-target="evidence-sealed">
    <div className="tr-sealed-heading"><div><span className="eyebrow">SEALED METRICS</span><h2 id="tr-sealed-title">Recorded result</h2><p>Supplied metrics from the sealed look. No equity curve or new arbiter verdict was attached.</p></div><span className="tr-sealed-split">{look.split}</span></div>
    <div className="tr-sealed-grid"><div><span>Gate vs strategy as-is</span><strong>{pointsValue(look.delta_net_return_vs_always_on)}</strong><small>90% range {range(look.ci_delta, pointsValue)}</small></div><div><span>Gate net return</span><strong>{pctValue(look.metrics.net_return)}</strong><small>90% range {range(look.metrics.ci_net_return, pctValue)}</small></div><div><span>Largest fall</span><strong>{drawdownValue(look.metrics.max_drawdown)}</strong><small>Strategy as-is: {drawdownValue(look.always_on.max_drawdown)}</small></div></div>
    <p className="tr-sealed-note"><TriangleAlert size={15} />The published KILL applies to strategy as-is only. The arbiter was not rerun on this gate, so keep the proposal provisional until an approved test on unseen data.</p>
  </section>;
}

function conditionLabel(condition: string) {
  const [axis, rawValue] = condition.split("=");
  const value = (rawValue || "").replaceAll("_", " ");
  if (axis === "vol_regime") return `${value} volatility`;
  if (axis === "trend_regime") return `${value} trend`;
  if (axis === "liquidity_regime") return `${value} liquidity`;
  if (axis === "sentiment_regime") return `${value} sentiment`;
  return condition.replaceAll("_", " ");
}

function findingSummary(hypothesis: TeamHypothesis) {
  const conditions = hypothesis.conditions.map(conditionLabel);
  const context = conditions.length > 1 ? `${conditions.slice(0, -1).join(", ")} and ${conditions[conditions.length - 1]}` : conditions[0] || "the recorded conditions";
  return hypothesis.direction === "works_better" ? `The strategy looks stronger in ${context}.` : `The strategy looks weaker in ${context}.`;
}

function HypothesisCard({ hypothesis, evidenceById, onEvidence }: { hypothesis: TeamHypothesis; evidenceById: Map<string, TeamEvidence>; onEvidence: (id: string) => void }) {
  return <article className={`tr-hypothesis ${hypothesis.direction === "works_better" ? "better" : "worse"}`}><div className="tr-hypothesis-top"><span className="tr-hypothesis-id">{hypothesis.hypothesis_id}</span><span className={`tr-confidence ${hypothesis.confidence}`}>{hypothesis.confidence} confidence</span></div><h3>{findingSummary(hypothesis)}</h3><div className="tr-conditions">{hypothesis.conditions.map(condition => <span key={condition}>{conditionLabel(condition)}</span>)}</div><details className="tr-finding-details"><summary>Recorded details <ChevronRight size={13} /></summary><div><p><strong>Recorded statement</strong>{hypothesis.statement}</p><p><strong>Suggested test</strong>{hypothesis.suggested_test}</p>{hypothesis.caveats.length > 0 && <p className="tr-caveat"><Info size={14} />{hypothesis.caveats.join(" ")}</p>}<p className="tr-raw-conditions"><strong>Condition codes</strong>{hypothesis.conditions.map(condition => <code key={condition}>{condition}</code>)}</p></div></details><div className="tr-evidence-chips">{hypothesis.evidence_ids.map(id => <button type="button" key={id} onClick={() => onEvidence(id)} title={evidenceById.has(id) ? evidenceById.get(id)?.tool : "Missing evidence record"}><FileSearch size={12} />View evidence</button>)}</div></article>;
}

function TrialRow({ trial, orphanFold = false }: { trial: TeamTrial; orphanFold?: boolean }) {
  const refusal = trial.status === "refused";
  const isFold = trial.fold != null;
  const className = [isFold ? "tr-fold" : "", refusal ? "tr-refused" : trial.status === "error" ? "tr-error" : ""].filter(Boolean).join(" ");
  const ruleCell = isFold
    ? <td className="tr-fold-label"><span>Walk-forward fold {trial.fold}</span><small>{orphanFold ? <><code>{trial.policy_id}</code> · </> : null}stability check on one slice of training</small></td>
    : <td><strong>{trial.policy_id}</strong><small>{sourceLabel(trial.source)}</small></td>;
  return <tr className={className}>{ruleCell}<td><span className="tr-split" title="Training develops the rule; validation checks it before a new-data test.">{isFold ? "Training fold" : splitLabel(trial.split)}</span></td><td className={trial.delta_net_return_vs_always_on !== null && trial.delta_net_return_vs_always_on > 0 ? "tr-positive" : ""}>{pts(trial.delta_net_return_vs_always_on)}</td><td>{trial.ci_delta ? `[${pts(trial.ci_delta[0])}, ${pts(trial.ci_delta[1])}]` : "—"}</td><td><span className={`tr-trial-status ${trial.status}`}>{trial.status === "evaluated" ? <CircleCheck size={13} /> : trial.status === "refused" ? <CircleX size={13} /> : <AlertTriangle size={13} />}{trial.status}</span></td><td>{isFold ? trial.evidence_id || "—" : trial.note || trial.evidence_id || "—"}</td></tr>;
}

type TrialGroup = { trial: TeamTrial; folds: TeamTrial[]; orphan?: boolean };

/** Policy attempts (fold null) in log order, each followed by its walk-forward fold checks. */
function groupTrials(trials: TeamTrial[]): TrialGroup[] {
  const attempts = trials.filter(trial => trial.fold == null);
  const lastAttempt = new Map<string, number>();
  attempts.forEach((trial, index) => lastAttempt.set(trial.policy_id, index));
  const foldsByAttempt = new Map<number, TeamTrial[]>();
  const orphans: TeamTrial[] = [];
  for (const trial of trials) {
    if (trial.fold == null) continue;
    const parent = lastAttempt.get(trial.policy_id);
    if (parent === undefined) orphans.push(trial);
    else foldsByAttempt.set(parent, [...(foldsByAttempt.get(parent) || []), trial]);
  }
  const byFold = (a: TeamTrial, b: TeamTrial) => (a.fold ?? 0) - (b.fold ?? 0);
  return [
    ...attempts.map((trial, index) => ({ trial, folds: (foldsByAttempt.get(index) || []).sort(byFold) })),
    ...orphans.sort(byFold).map(trial => ({ trial, folds: [], orphan: true })),
  ];
}

/** Display only: shorten long floats in recorded agent text (0.323252674893775 → 0.323); the recorded statement is unchanged. */
const tidyNumbers = (text: string) => text.replace(/\d+\.\d{4,}/g, match => { const value = Number(match); return Math.abs(value) >= 10 ? value.toFixed(1) : value.toFixed(3); });

function ContextCard({ context }: { context: TeamContext }) {
  return <section className="tr-mood panel" aria-labelledby="tr-mood-title">
    <div className="tr-section-head"><div><span className="eyebrow">MARKET MOOD</span><h2 id="tr-mood-title">Sentiment context</h2><p>Fear &amp; Greed around the best and worst training weeks. Co-occurrence in time only, not a cause.</p></div></div>
    <p className="tr-mood-summary">{tidyNumbers(context.summary)}</p>
    {context.findings.length > 0 && <ul className="tr-mood-findings">{context.findings.map(finding => <li key={finding.finding_id}><span className={`tr-strength ${finding.strength}`}>{finding.strength === "none" ? "No signal" : `${finding.strength[0].toUpperCase()}${finding.strength.slice(1)} signal`}</span><p>{tidyNumbers(finding.statement)}</p></li>)}</ul>}
  </section>;
}

function CandidateCard({ candidate, historical = false }: { candidate: TeamCandidate; historical?: boolean }) {
  const eligible = candidate.status === "accepted_for_frozen_test";
  const competitor = candidate.status === "competitor";
  return <article className={`tr-candidate ${eligible ? "eligible" : competitor ? "competitor" : "rejected"} ${historical ? "historical" : ""}`}><div className="tr-candidate-head"><span className="tr-candidate-status">{historical ? <><CircleCheck size={14} />Selected for the sealed look</> : eligible ? <><CircleCheck size={14} />Candidate for a new-data test</> : competitor ? <><Info size={14} />Comparison rule</> : <><CircleX size={14} />Rejected</>}</span><code>{candidate.policy_id}</code></div><p className="tr-candidate-note">{historical ? "This policy was selected during development before the sealed look. The recorded result remains provisional and does not unlock a paper plan." : eligible ? "This trading rule passed the development-stage checks. It has not been validated on data it did not see during research." : competitor ? "This rule is included as a comparison point; it is not an agent-selected candidate." : "This trading rule will not proceed to the new-data test."}</p><details className="tr-candidate-reasons"><summary>Why this selection? <ChevronRight size={13} /></summary><ul>{candidate.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></details><details className="tr-policy-spec"><summary>Trading rule details <ChevronRight size={13} /></summary><code>{json(candidate.policy_spec)}</code></details></article>;
}

/* ------------------------------------------------------------------------------------------------
 * Readable report: the plain-language presentation (packages/research_agents/presentation.py).
 * Every sentence and number below comes from that presentation; this component only lays it out.
 * `_pp` fields and returns are fractions: 0.273 renders as "+27.3 pp", -0.289 as "-28.9%".
 * ---------------------------------------------------------------------------------------------- */
const signedPlain = (value: number) => `${value > 0 ? "+" : value < 0 ? "-" : ""}${Math.abs(value * 100).toFixed(1)}`;
const ppText = (value: number | null | undefined) => typeof value !== "number" ? "—" : `${signedPlain(value)} pp`;
const pctText = (value: number | null | undefined) => typeof value !== "number" ? "—" : `${signedPlain(value)}%`;
const ppRangeText = (range: [number, number] | null | undefined) => range ? `90% interval ${signedPlain(range[0])} to ${signedPlain(range[1])} pp` : "";
const toolLabel = (tool: string) => tool.replaceAll("_", " ");
const signClass = (value: number | null | undefined) => typeof value !== "number" ? "" : value > 0 ? "pos" : value < 0 ? "neg" : "";
const STAGE_NAMES = ["Training", "Validation", "Held-out test"] as const;
const OUTCOME_ORDER: Record<PresentationOutcome, number> = { selected_for_further_testing: 0, approved: 1, rejected: 2, reference: 3, not_run: 4 };
const OUTCOME_CLASS: Record<PresentationOutcome, string> = { selected_for_further_testing: "selected", approved: "approved", rejected: "rejected", reference: "reference", not_run: "not-run" };
const COUNT_WORDS: [PresentationOutcome, string][] = [["selected_for_further_testing", "selected for further testing"], ["approved", "approved"], ["rejected", "rejected"], ["reference", "comparison only"], ["not_run", "tried on Training only"]];
const verdictTone = (verdict: string | null | undefined) => {
  const value = (verdict || "").toUpperCase();
  return value === "KILL" ? "kill" : value === "KEEP" ? "keep" : value ? "unproven" : "muted";
};

type EvidenceHandlers = { evidenceById: Map<string, TeamEvidence>; onEvidence: (id: string) => void; onLibrary: () => void };

function EvidenceLinks({ ids, evidenceById, onEvidence, onLibrary, max = 3 }: EvidenceHandlers & { ids: string[]; max?: number }) {
  const unique = [...new Set(ids)].filter(id => evidenceById.has(id));
  if (unique.length === 0) return null;
  const shown = unique.slice(0, max);
  const tools = unique.map(id => evidenceById.get(id)?.tool || id);
  // Several records from one tool get a number, so each link reads differently.
  const label = (id: string, index: number) => {
    const tool = tools[index];
    const same = tools.filter(item => item === tool).length;
    return same > 1 ? `${toolLabel(tool)} ${tools.slice(0, index + 1).filter(item => item === tool).length}` : toolLabel(tool);
  };
  return <div className="rr-evidence-links">
    <span>Open evidence</span>
    {shown.map((id, index) => <button type="button" key={id} onClick={() => onEvidence(id)} title={id}><FileSearch size={12} />{label(id, index)}</button>)}
    {unique.length > max && <button type="button" onClick={onLibrary}>+{unique.length - max} more</button>}
  </div>;
}

function SectionHead({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return <div className="rr-head"><span className="rr-eyebrow">{eyebrow}</span><h2>{title}</h2>{children && <p>{children}</p>}</div>;
}

function FindingCard({ presentation }: { presentation: ReportPresentation }) {
  const { headline } = presentation;
  const tone = verdictTone(headline.verdict);
  return <section className={`rr-finding ${tone}`} aria-labelledby="rr-finding-title">
    <div className="rr-verdict-row">
      <span className={`rr-verdict ${tone}`}>{headline.verdict_label}</span>
      {headline.verdict_scope && <span className="rr-verdict-meta">Applies to: <strong>{headline.verdict_scope}</strong></span>}
      {headline.verdict_source && <span className="rr-verdict-meta">Source: {headline.verdict_source}</span>}
    </div>
    <h2 id="rr-finding-title" className="rr-finding-text" tabIndex={-1}>{headline.finding}</h2>
    <p className="rr-meaning">{headline.meaning}</p>
    <p className="rr-next-step"><ArrowRight size={16} /><span><strong>Next step:</strong> {headline.next_action}</span></p>
  </section>;
}

function StagesSection({ stages, ...handlers }: EvidenceHandlers & { stages: PresentationStage[] }) {
  const byName = new Map(stages.map(stage => [stage.stage, stage]));
  const ordered: PresentationStage[] = STAGE_NAMES.map(name => byName.get(name) || { stage: name, window: null, what_happened: "Not recorded.", result: "Not recorded.", evidence_ids: [] });
  return <section className="rr-section" aria-labelledby="rr-stages-title">
    <SectionHead eyebrow="HOW IT WAS TESTED" title="Research stages">Each stage uses later data than the one before. The agents worked on Training only.</SectionHead>
    <ol className="rr-stages" id="rr-stages-title">{ordered.map((stage, index) => <li key={stage.stage} className="rr-stage">
      <div className="rr-stage-top"><span className="rr-stage-num">{index + 1}</span><h3>{stage.stage}</h3></div>
      <p className="rr-stage-window">{stage.window || "Dates not recorded"}</p>
      <dl><dt>What happened</dt><dd>{stage.what_happened}</dd><dt>Result</dt><dd className="rr-stage-result">{stage.result}</dd></dl>
      <EvidenceLinks ids={stage.evidence_ids} {...handlers} max={2} />
    </li>)}</ol>
  </section>;
}

function ExactSettings({ filter, ...handlers }: EvidenceHandlers & { filter: PresentationFilter }) {
  return <details className="rr-settings"><summary>Exact settings<ChevronDown size={13} /></summary>
    <code className="rr-code">{json(filter.spec)}</code>
    {filter.details.length > 0 && <ul className="rr-details-list">{filter.details.map((item, index) => <li key={index}>{item}</li>)}</ul>}
    <p className="rr-policy-id">Rule id <code>{filter.policy_id}</code></p>
    <EvidenceLinks ids={filter.evidence_ids} {...handlers} max={4} />
  </details>;
}

/** "Did the filter choose when, or just hold less?" — a Validation diagnostic, not the selection rule. */
function TimingLine({ timing }: { timing: PresentationTiming }) {
  const parts = [
    typeof timing.vs_half_size_pp === "number" ? `vs half size ${ppText(timing.vs_half_size_pp)}` : null,
    typeof timing.vs_same_average_size_pp === "number" ? `vs same average size ${ppText(timing.vs_same_average_size_pp)}` : null,
  ].filter(Boolean);
  return <p className="rr-timing" title={timing.size_note || undefined}>
    <strong>Timing or just less risk?</strong> {timing.read}
    {parts.length > 0 && <span className="rr-timing-nums">{parts.join(" · ")}</span>}
  </p>;
}

function FilterRow({ filter, ...handlers }: EvidenceHandlers & { filter: PresentationFilter }) {
  const outcomeClass = OUTCOME_CLASS[filter.outcome] || "";
  return <li className={`rr-filter ${outcomeClass}`}>
    <div className="rr-filter-grid">
      <div className="rr-cell rr-cell-rule">
        <strong className="rr-filter-label">{filter.label}</strong>
        <p>{filter.plain_rule}</p>
        <p className="rr-sub"><span>Changes size:</span> {filter.exposure_change}</p>
        <p className="rr-sub"><span>Proposed by:</span> {filter.proposed_by}</p>
      </div>
      <div className="rr-cell"><span className="rr-cell-label">Checked in</span><div className="rr-chips">{filter.stages_checked.map(stage => <span key={stage} className="rr-chip">{stage}</span>)}</div></div>
      <div className="rr-cell"><span className="rr-cell-label">Outcome</span><span className={`rr-outcome ${outcomeClass}`}>{filter.outcome_label}</span><p className="rr-reason">{filter.reason}</p></div>
      <div className="rr-cell rr-num"><span className="rr-cell-label">Validation vs original</span><strong className={signClass(filter.validation_vs_original_pp)}>{ppText(filter.validation_vs_original_pp)}</strong>{filter.validation_vs_original_ci_pp && <small>{ppRangeText(filter.validation_vs_original_ci_pp)}</small>}</div>
      <div className="rr-cell rr-num"><span className="rr-cell-label">Own return on Validation</span><strong className={signClass(filter.validation_own_return)}>{pctText(filter.validation_own_return)}</strong>{typeof filter.average_size_on_validation === "number" && <small>average size {Math.round(filter.average_size_on_validation * 100)}%</small>}</div>
    </div>
    {filter.timing && <TimingLine timing={filter.timing} />}
    {filter.held_out && <p className="rr-held-out"><LockKeyhole size={14} /><span><strong>Held-out test:</strong> {filter.held_out.summary}</span></p>}
    <ExactSettings filter={filter} {...handlers} />
  </li>;
}

function FiltersSection({ presentation, ...handlers }: EvidenceHandlers & { presentation: ReportPresentation }) {
  const main = presentation.filters.filter(filter => filter.outcome !== "not_run").sort((a, b) => (OUTCOME_ORDER[a.outcome] ?? 9) - (OUTCOME_ORDER[b.outcome] ?? 9));
  const notRun = presentation.filters.filter(filter => filter.outcome === "not_run");
  const refused = notRun.filter(filter => filter.reason.toLowerCase().startsWith("refused"));
  const counts = COUNT_WORDS.map(([key, words]) => [presentation.filter_counts?.[key] ?? 0, words] as const).filter(([count]) => count > 0);
  return <section className="rr-section" aria-labelledby="rr-filters-title">
    <SectionHead eyebrow="WHAT WAS CHECKED" title="Checked filters">A filter only changes position size; the strategy&apos;s own signals are never changed.{counts.length > 0 ? ` ${counts.map(([count, words]) => `${count} ${words}`).join(" · ")}.` : ""}</SectionHead>
    {main.length > 0 && <>
      <div className="rr-filter-header" aria-hidden="true"><span>Filter</span><span>Checked in</span><span>Outcome</span><span>Validation vs original</span><span>Own return on Validation</span></div>
      <ul className="rr-filters" id="rr-filters-title">{main.map(filter => <FilterRow key={filter.policy_id} filter={filter} {...handlers} />)}</ul>
    </>}
    {notRun.length > 0 && <details className="rr-not-run">
      <summary><ChevronRight size={14} />Also tried on Training only ({notRun.length - refused.length}){refused.length > 0 ? ` · refused before running (${refused.length})` : ""}</summary>
      <p className="rr-not-run-note">These were never scored on Validation, so they say nothing about unseen data.</p>
      <ul>{notRun.map(filter => <li key={filter.policy_id}><strong>{filter.label}</strong><p>{filter.reason}</p><ExactSettings filter={filter} {...handlers} /></li>)}</ul>
    </details>}
  </section>;
}

function TraceSection({ trace, ...handlers }: EvidenceHandlers & { trace: PresentationTraceItem[] }) {
  return <section className="rr-section" aria-labelledby="rr-trace-title">
    <SectionHead eyebrow="THE RESEARCH PATH" title="How the agents got there">AI agents proposed and challenged. Code scored, selected and decided.</SectionHead>
    <ol className="rr-trace" id="rr-trace-title">{trace.map(item => <li key={item.step} className="rr-trace-step">
      <span className="rr-trace-num">{item.step}</span>
      <div className="rr-trace-body">
        <div className="rr-trace-meta"><strong>{item.actor}</strong><span className={`rr-kind ${item.actor_kind === "Code" ? "code" : "agent"}`}>{item.actor_kind === "Code" ? <Cpu size={12} /> : <Bot size={12} />}{item.actor_kind}</span><span className="rr-action">{item.action}</span></div>
        <h3>{item.title}</h3>
        <p>{item.summary}</p>
        {item.items.length > 0 && <ul>{item.items.slice(0, 4).map((line, index) => <li key={index}>{line}</li>)}{item.items.length > 4 && <li className="rr-more">and {item.items.length - 4} more</li>}</ul>}
        {item.changed_conclusion && <p className="rr-changed"><strong>Changed the conclusion:</strong> {item.changed_conclusion}</p>}
        <EvidenceLinks ids={item.evidence_ids} {...handlers} />
      </div>
    </li>)}</ol>
  </section>;
}

function downloadTakeaway(presentation: ReportPresentation) {
  const filters = presentation.filters.map(filter => Object.fromEntries(Object.entries(filter).filter(([key]) => key !== "details")));
  const body = { strategy: presentation.takeaway.strategy, selected_filter: presentation.takeaway.selected_filter ?? null, evidence: presentation.takeaway.evidence, headline: presentation.headline, filters };
  const url = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${presentation.takeaway.strategy.strategy_id || "strategy"}-takeaway.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function TakeawaySection({ presentation, ...handlers }: EvidenceHandlers & { presentation: ReportPresentation }) {
  const { strategy, selected_filter: selected, selected_filter_note: selectedNote, plans } = presentation.takeaway;
  const seen = new Set<string>();
  const evidence = presentation.takeaway.evidence.filter(item => { const key = item.path || item.evidence_id || item.label; if (seen.has(key)) return false; seen.add(key); return true; });
  const parameters = Object.entries(strategy.parameters || {});
  return <section className="rr-section" aria-labelledby="rr-take-title">
    <SectionHead eyebrow="TAKE AWAY" title="The strategy and the evidence">What was tested, the exact settings of any selected filter, and where every number comes from.</SectionHead>
    <div className="rr-take-grid" id="rr-take-title">
      <article className="rr-take-card">
        <span className="rr-card-kicker">Original strategy</span>
        <h3>{strategy.name || strategy.strategy_id}</h3>
        {strategy.rule && <p>{strategy.rule}</p>}
        {parameters.length > 0 && <dl className="rr-params">{parameters.map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{typeof value === "string" ? value : json(value)}</dd></div>)}</dl>}
        {strategy.source && <p className="rr-sub"><span>Source:</span> <code>{strategy.source}</code></p>}
        <p className="rr-take-note"><Info size={14} />{strategy.note}</p>
      </article>
      <article className="rr-take-card">
        <span className="rr-card-kicker">Selected filter</span>
        {selected ? <>
          <h3>{selected.label}</h3>
          <span className="rr-outcome selected">{selected.status}</span>
          <p>{selected.plain_rule}</p>
          <code className="rr-code">{json(selected.spec)}</code>
        </> : <h3>None selected</h3>}
        {selectedNote && <p className="rr-take-note"><Info size={14} />{selectedNote}</p>}
      </article>
    </div>
    <div className="rr-take-evidence">
      <h3>Evidence</h3>
      <ul>{evidence.map((item, index) => {
        const id = item.evidence_id || "";
        const record = id ? handlers.evidenceById.get(id) : undefined;
        return <li key={index}><span>{item.label}</span>{item.path ? <code>{item.path}</code> : record ? <button type="button" onClick={() => handlers.onEvidence(id)}><FileSearch size={12} />Open evidence · {toolLabel(record.tool)}</button> : id ? <code>{id}</code> : null}</li>;
      })}</ul>
    </div>
    <p className="rr-plans"><LockKeyhole size={14} />{plans}</p>
    <button type="button" className="button secondary rr-download" onClick={() => downloadTakeaway(presentation)}><Download size={15} />Download takeaway (JSON)</button>
  </section>;
}

function ReadableReport({ presentation, ...handlers }: EvidenceHandlers & { presentation: ReportPresentation }) {
  return <div className="rr-report">
    <FindingCard presentation={presentation} />
    <StagesSection stages={presentation.stages || []} {...handlers} />
    <FiltersSection presentation={presentation} {...handlers} />
    <TraceSection trace={presentation.trace || []} {...handlers} />
    <TakeawaySection presentation={presentation} {...handlers} />
    {(presentation.glossary || []).length > 0 && <details className="rr-glossary"><summary><BookOpen size={14} />Terms used<ChevronDown size={14} /></summary><dl>{presentation.glossary.map(item => <div key={item.term}><dt>{item.term}</dt><dd>{item.meaning}</dd></div>)}</dl></details>}
  </div>;
}

/** With a readable report above, the technical report folds into one disclosure; without one it renders as before. */
function FullReport({ collapsible, open, onToggle, children }: { collapsible: boolean; open: boolean; onToggle: (open: boolean) => void; children: ReactNode }) {
  if (!collapsible) return <>{children}</>;
  return <details id="tr-full-report" className="rr-full" open={open} onToggle={event => onToggle(event.currentTarget.open)}>
    <summary><FileSearch size={17} /><span><strong>Full report details (IDs, logs, provenance)</strong><small>The trial log, raw tool outputs, candidates and source files behind everything above.</small></span><ChevronDown size={17} className="rr-full-chevron" /></summary>
    <div className="rr-full-body">{children}</div>
  </details>;
}

export type TeamResearchProps = {
  /** Prefer the report that belongs to the current experiment when the native report store has it. */
  initialExperimentId?: string;
  /** The Part C strategy currently in focus; this is intentionally separate from the report identity. */
  strategyId?: string;
  /** Embedded report viewers can return to the evidence surface without adding a navigation destination. */
  onBack?: () => void;
  frozenEvaluation?: FrozenEvaluation;
};

export default function TeamResearch({ initialExperimentId = "", strategyId = "", onBack, frozenEvaluation }: TeamResearchProps) {
  const [summaries, setSummaries] = useState<InvestigationSummary[]>([]);
  const [selectedId, setSelectedId] = useState(initialExperimentId);
  const [wrapper, setWrapper] = useState<InvestigationWrapper | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [showAllTrials, setShowAllTrials] = useState(true);
  const [showFolds, setShowFolds] = useState(true);
  const [focusedEvidence, setFocusedEvidence] = useState<string | null>(null);
  const [view, setView] = useState<"findings" | "tests" | "evidence">("findings");
  /** With a readable report, the full technical report sits in one disclosure below it. */
  const [fullOpen, setFullOpen] = useState(false);
  useEffect(() => { setFullOpen(false); }, [selectedId]);

  useEffect(() => { let cancelled = false; teamApi.investigations().then(items => { if (!cancelled) { const preferred = initialExperimentId && items.some(item => item.experiment_id === initialExperimentId) ? initialExperimentId : strategyId ? items.find(item => item.strategy_id === strategyId)?.experiment_id || items[0]?.experiment_id || "" : items[0]?.experiment_id || ""; setSummaries(items); setSelectedId(preferred); } }).catch(failure => { if (!cancelled) setError(failure instanceof Error ? failure.message : "Could not load investigations."); }).finally(() => { if (!cancelled) setLoading(false); }); return () => { cancelled = true; }; }, [initialExperimentId, strategyId]);
  useEffect(() => { if (!selectedId) { setWrapper(null); setError(""); setDetailLoading(false); return; } let cancelled = false; setDetailLoading(true); setWrapper(null); setError(""); teamApi.investigation(selectedId).then(item => { if (!cancelled) setWrapper(item); }).catch(failure => { if (!cancelled) { setWrapper(null); setError(failure instanceof Error ? failure.message : "Could not load this investigation."); } }).finally(() => { if (!cancelled) setDetailLoading(false); }); return () => { cancelled = true; }; }, [selectedId]);

  const report = wrapper?.report;
  const evidenceById = useMemo(() => new Map((report?.evidence || []).map(item => [item.evidence_id, item])), [report]);
  const selectedSummary = summaries.find(item => item.experiment_id === selectedId);
  const trialGroups = useMemo(() => groupTrials(report?.trial_log || []), [report]);
  const displayedGroups = trialGroups.filter(group => (showAllTrials || group.trial.status !== "refused") && (showFolds || !group.orphan));
  const foldCount = (report?.trial_log || []).filter(item => item.fold != null).length;
  const runCount = (report?.trial_log.length || 0) - foldCount;
  const sealedEvaluation = frozenEvaluation?.experiment_id === report?.experiment_id && frozenEvaluation?.strategy_id === report?.strategy_id ? frozenEvaluation : frozenLook(wrapper);
  const verdict = report ? reportVerdict(report, sealedEvaluation) : null;
  const presentation = wrapper?.presentation || null;
  const openEvidence = (id: string) => { setFullOpen(true); setView("evidence"); setFocusedEvidence(id); window.setTimeout(() => document.getElementById("tr-view-panel")?.scrollIntoView({ block: "start", behavior: "instant" }), 0); };
  const openLibrary = () => { setFullOpen(true); setView("evidence"); window.setTimeout(() => document.getElementById("tr-full-report")?.scrollIntoView({ block: "start", behavior: "instant" }), 0); };
  useEffect(() => { if (report?.experiment_id) document.getElementById(presentation ? "rr-finding-title" : "tr-verdict-title")?.focus({ preventScroll: true }); }, [report?.experiment_id, presentation]);

  const backControl = onBack && <button className="tr-back-link" type="button" onClick={onBack}><ArrowLeft size={15} />Back to evidence</button>;
  if (loading) return <div className="tr-loading">{backControl}<FlaskConical size={25} /><strong>Loading agent investigations</strong><span>Reading trusted research artifacts.</span></div>;
  if (error && summaries.length === 0) return <div className="tr-empty">{backControl}<TriangleAlert size={28} /><h2>Investigation artifacts unavailable</h2><p>{error}</p></div>;
  return <div className="tr-shell tr-judge-report">
      <div className="tr-heading page-heading">
      <div><span className="eyebrow"><Sparkles size={13} />AGENT RESEARCH</span><span className="tr-internal-title">Agent research</span><p>See what held up, what broke, and what still needs a fair test.</p></div>
      <div className="tr-heading-right">{strategyId && report && report.strategy_id !== strategyId && <details className={`tr-report-identity${report && report.strategy_id !== strategyId ? " is-mismatch" : ""}`} open={Boolean(report && report.strategy_id !== strategyId)}><summary>{report && report.strategy_id !== strategyId ? "This report uses a different strategy" : "Report identity"}<ChevronDown size={14} /></summary><div><span>Workspace strategy <strong>{strategyId}</strong></span><span>Report strategy <strong>{report?.strategy_id ?? "Loading…"}</strong></span></div></details>}{onBack && <button className="tr-back-link" type="button" onClick={onBack}><ArrowLeft size={15} />Back to evidence</button>}{summaries.length > 0 && <label className="tr-selector-label">Research record<select className="tr-select" value={selectedId} onChange={event => setSelectedId(event.target.value)} aria-label="Choose a research record">{summaries.map(item => <option value={item.experiment_id} key={item.experiment_id}>{item.strategy_id === "btc-meanrev-48-demo" ? "BTC mean reversion" : item.strategy_id === "btc-trend-24-72-demo" ? "BTC trend" : item.strategy_id}{item.synthetic ? " · synthetic example" : ""}</option>)}</select></label>}</div>
    </div>
    {error && <div className="tr-inline-error" role="alert"><TriangleAlert size={16} />{error}</div>}
    {detailLoading ? <div className="tr-loading tr-panel-loading"><Clock3 size={22} /><strong>Opening the investigation</strong><span>Loading hypotheses, experiments, and their evidence.</span></div> : report ? <>
      {report.holdout_accessed && <div className="tr-holdout-warning"><AlertTriangle size={18} /><div><strong>New-data test access recorded</strong><p>The research appears to have seen the data reserved for the final check. Inspect the trial log before treating this investigation as suitable for an unbiased new-data test.</p></div></div>}
      {wrapper?.synthetic && <div className="tr-synthetic-note"><Beaker size={16} /><div><strong>Recorded example</strong> · Scripted research on sample market data, with no language-model call. Trading rules still need a new-data test.</div></div>}
      {presentation && <ReadableReport presentation={presentation} evidenceById={evidenceById} onEvidence={openEvidence} onLibrary={openLibrary} />}
      <FullReport collapsible={Boolean(presentation)} open={fullOpen} onToggle={setFullOpen}>
      {verdict && <section className="tr-verdict-lead" aria-labelledby="tr-verdict-title" data-guide-target="evidence-verdict">
        <div className="tr-verdict-copy"><div className="tr-verdict-kicker"><span className="eyebrow">{sealedEvaluation ? "LATEST RECORDED RESULT" : "RESEARCH VERDICT"}</span><span className="tr-verdict-pill neutral">{verdict.label}</span></div><h1 id="tr-verdict-title" tabIndex={-1}>{verdict.title}</h1><p>{verdict.body}</p><div className="tr-verdict-steps" aria-label="How the decision is checked"><span>Agent proposes</span><i aria-hidden="true" /><span>Critic challenges</span><i aria-hidden="true" /><span>Code records</span></div><button type="button" className="tr-inline-action tr-primary-next" onClick={() => { setView("tests"); requestAnimationFrame(() => { const panel = document.getElementById("tr-view-panel"); panel?.scrollIntoView({ block: "start", behavior: "instant" }); panel?.focus({ preventScroll: true }); }); }}>Inspect rules tested <ChevronRight size={14} /></button></div>
        <MascotCallout pose="bear-magnifier" title={sealedEvaluation ? "A useful clue. No approval yet." : "Every claim needs a check."} className="tr-hero-mascot">{sealedEvaluation ? "The filter reduced losses. It still needs its own decision before a paper plan." : "Agents suggest explanations. The recorded tests show what actually held up."}</MascotCallout>
      </section>}
      {sealedEvaluation && <SealedLook evaluation={sealedEvaluation} />}
      <details className="tr-research-summary">
        <summary>Report provenance &amp; research counts <ChevronDown size={15} /></summary>
          {selectedSummary && <div className="tr-context-bar"><span>{selectedSummary.strategy_id}</span><ModeBadge item={selectedSummary} /><SourceBadge item={selectedSummary} /><span className="tr-context-time">{when(selectedSummary.generated_at)} UTC</span></div>}
          <p className="tr-provenance-path">Source: <code>{wrapper?.source_path}</code> · Experiment: <code>{report.experiment_id}</code></p>
        <section className="tr-research-brief">
          <div className="tr-brief-content"><span className="eyebrow">THE QUESTION</span><h2>When should this strategy<br />be active?</h2><p>Agents grouped the evidence, challenged competing explanations, and recorded what deserves a new-data test.</p></div>
          <div className="tr-brief-numbers"><div><strong>{report.diagnostic.hypotheses.length.toString().padStart(2, "0")}</strong><span>hypotheses<br />investigated</span></div><div><strong>{report.n_policies_tried.toString().padStart(2, "0")}</strong><span>distinct policies<br />tried</span></div><div><strong>{report.trial_log.length.toString().padStart(2, "0")}</strong><span>trial rows<br />recorded</span></div><div><strong>{report.evidence.length.toString().padStart(2, "0")}</strong><span>evidence<br />records</span></div></div>
          <div className="tr-workflow" aria-label="Research stages"><span><CircleCheck size={15} />Agent proposes</span><i /><span><CircleCheck size={15} />Critic challenges</span><i /><span><CircleCheck size={15} />Code records</span><i /><span className="tr-workflow-next"><Clock3 size={15} />Human approval <small>{sealedEvaluation ? "Still locked" : "Not reached"}</small></span></div>
        </section>
      </details>
      <div className="tr-view-tabs" data-guide-target="evidence-path" role="tablist" aria-label="Investigation views">{([{id:"findings",label:"What we found",count:report.diagnostic.hypotheses.length},{id:"tests",label:"Rules tested",count:report.n_policies_tried},{id:"evidence",label:"Source evidence",count:report.evidence.length}] as const).map(item=><button key={item.id} role="tab" id={`tr-tab-${item.id}`} aria-selected={view===item.id} aria-controls="tr-view-panel" onClick={()=>setView(item.id)} className={view===item.id ? "active" : ""}>{item.label}<span>{item.count}</span></button>)}</div>
      <div id="tr-view-panel" tabIndex={-1} role="tabpanel" aria-labelledby={`tr-tab-${view}`}>
      {view === "findings" && <div className="tr-findings-layout">
        <div className="tr-main-column">
          <section className="tr-section panel" data-guide-target="evidence-finding"><div className="tr-section-head"><div><span className="eyebrow">STRENGTHS & WEAK SPOTS</span><h2>What held up?</h2><p>Each finding is a question you can inspect, not a promise.</p></div><Sparkles size={18} className="purple" /></div><div className="tr-hypotheses">{report.diagnostic.hypotheses.map(hypothesis => <HypothesisCard key={hypothesis.hypothesis_id} hypothesis={hypothesis} evidenceById={evidenceById} onEvidence={id => { setView("evidence"); setFocusedEvidence(id); }} />)}</div>
          {report.diagnostic.rejected_explanations.length > 0 && <details className="tr-rejected"><summary><CircleX size={16} />Explanations that did not hold up <span>{report.diagnostic.rejected_explanations.length}</span><ChevronDown size={16} /></summary><ul>{report.diagnostic.rejected_explanations.map(item => <li key={item}>{item}</li>)}</ul></details>}</section>
          <section className="tr-summary-panel panel"><div className="tr-panel-kicker"><span className="eyebrow">RECORDED ANALYST SUMMARY</span><ModeBadge item={report} compact /></div><p>{report.diagnostic.summary}</p><p className="tr-summary-help">This is the summary recorded by the research run. Returns include the listed costs; it is evidence for review, not a promise about future performance.</p></section>
          {report.context && <ContextCard context={report.context} />}
        </div>
        <aside className="tr-findings-aside"><section className="tr-next-card"><span className="tr-next-symbol"><FlaskConical size={25} /></span><span className="eyebrow">SECONDARY DETAIL</span><h2>Rules under pressure.</h2><p>Accepted, refused, and failed trials stay in the Rules tested tab. Use it to inspect the historical selection and its alternatives.</p><span className="tr-next-foot"><LockKeyhole size={13} />{sealedEvaluation ? "Sealed look recorded · paper plan locked" : report.champion_policy_id ? "Candidate awaits a sealed look" : "No candidate earned a sealed look"}</span></section>
        <details className="tr-limits-card"><summary><Info size={16} />What to keep in mind<ChevronDown size={15} /></summary><ul>{[...report.diagnostic.limitations, ...report.limitations].map((limitation, index) => <li key={index}>{limitation}</li>)}</ul></details></aside>
      </div>}
      {view === "tests" && <div className="tr-tests-view" data-guide-target="evidence-path"><section className="tr-section panel"><div className="tr-section-head"><div><span className="eyebrow">THE CHALLENGE LOG</span><h2>Rules under pressure.</h2><p>{report.n_policies_tried} distinct policies across {runCount} recorded runs{foldCount > 0 ? `, plus ${foldCount} walk-forward fold checks listed under their policy. Folds are stability checks, not extra attempts` : ""}.</p></div><div className="tr-toggles">{foldCount > 0 && <button className="tr-toggle" onClick={() => setShowFolds(current => !current)}>{showFolds ? "Hide folds" : "Show folds"}<ChevronDown size={14} /></button>}<button className="tr-toggle" onClick={() => setShowAllTrials(current => !current)}>{showAllTrials ? "Hide refusals" : "Show refusals"}<ChevronDown size={14} /></button></div></div><div className="tr-table-wrap"><table className="tr-table"><thead><tr><th>Trading rule</th><th><span title="Training data develops the rule; validation data is the check before a new-data test.">Research stage <Info size={12} /></span></th><th><span title="The measured return change compared with leaving the original strategy on, in percentage points.">Change vs always-on <Info size={12} /></span></th><th><span title="A 90% uncertainty range around the measured change, in percentage points; it is not a guarantee.">Likely range <Info size={12} /></span></th><th>Status</th><th>Evidence / note</th></tr></thead><tbody>{displayedGroups.flatMap((group, index) => [<TrialRow key={`${group.trial.policy_id}-${group.trial.split}-${group.trial.fold ?? "run"}-${index}`} trial={group.trial} orphanFold={group.orphan} />, ...(showFolds ? group.folds.map(fold => <TrialRow key={`${fold.policy_id}-fold-${fold.fold}-${index}`} trial={fold} />) : [])])}</tbody></table></div><p className="tr-table-help"><strong>How to read this:</strong> Training develops the rule; validation checks it before a new-data test. Change vs always-on compares with leaving the original strategy running, in percentage points. A walk-forward fold re-checks a policy on one slice of training; it is a stability check, not another attempt. The likely range shows uncertainty around that measured change.</p></section>
        <section className="tr-section panel"><div className="tr-section-head"><div><span className="eyebrow">CANDIDATES FOR FURTHER TESTING</span><h2>What can move forward?</h2><p>{sealedEvaluation ? "Historical selection is shown separately from the sealed result." : "Readiness for a new-data test does not establish profitability."}</p></div><span className="tr-count">{report.candidates.length}</span></div><div className="tr-candidates">{report.candidates.map(candidate => <CandidateCard key={candidate.policy_id} candidate={candidate} historical={Boolean(sealedEvaluation && candidate.policy_id === report.champion_policy_id)} />)}</div></section>
        <div className="tr-evidence-shortcut"><FileSearch size={18} /><p>Every result has a source. Inspect the technical tool outputs behind this comparison.</p><button className="button secondary" onClick={()=>setView("evidence")}>Open evidence <ChevronRight size={15} /></button></div>
      </div>}
      {view === "evidence" && <div className="tr-evidence-view"><ResearchSourceBrowser evidence={report.evidence} focusedEvidence={focusedEvidence} /><section className="tr-side-panel panel"><div className="tr-side-head"><div><span className="eyebrow">RECORDED REQUESTS</span><h2>What did the agents ask to check?</h2></div><Clock3 size={17} /></div><div className="tr-request-list">{report.test_requests.length > 0 ? report.test_requests.map(request => <p key={request}><ChevronRight size={14} />{request}</p>) : <p className="tr-muted">No additional tests requested.</p>}</div><div className="tr-source-record"><span>Source artifact</span><code>{wrapper?.source_path}</code><span>Experiment</span><code>{report.experiment_id}</code></div></section></div>}
      </div>
      </FullReport>
    </> : <div className="tr-empty"><FileSearch size={30} /><h2>No investigations found</h2><p>Start an investigation to bring your agents’ findings and evidence together.</p></div>}
  </div>;
}
