"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowLeft, Beaker, ChevronDown, ChevronRight, CircleCheck, CircleX, Clock3, FileSearch, FlaskConical, Info, LockKeyhole, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import { teamApi, type InvestigationSummary, type InvestigationWrapper, type TeamCandidate, type TeamContext, type TeamEvidence, type TeamFrozenLook, type TeamHypothesis, type TeamReport, type TeamTrial } from "@/lib/team-api";
import "./team-research.css";

const signed = (value: number) => `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value * 100).toFixed(1)}`;
/** A policy's own return, e.g. "−28.9%". */
const pct = (value: number | null | undefined) => typeof value !== "number" ? "—" : `${signed(value)}%`;
/** A magnitude such as drawdown, e.g. "36.2%". */
const share = (value: number | null | undefined) => typeof value !== "number" ? "—" : `${Math.abs(value * 100).toFixed(1)}%`;
/** A difference between two policies' returns, in percentage points, e.g. "+27.3 pts". */
const pts = (value: number | null | undefined) => typeof value !== "number" ? "—" : `${signed(value)} pts`;
const ptsRange = (range: [number, number] | null | undefined) => range ? `[${signed(range[0])}, ${signed(range[1])}] pts` : "—";
const POLICY_LABELS: Record<string, string> = {
  "rule::half_size_constant": "Always half size (exposure baseline)",
  "rule::regime_filter": "Regime filter",
};
const policyLabel = (policyId: string) => POLICY_LABELS[policyId] || policyId;
const monthYear = (value: string) => new Date(value).toLocaleDateString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" });
const when = (value: string) => new Date(value).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" });
const json = (value: unknown) => JSON.stringify(value, null, 2);
const splitLabel = (split: TeamTrial["split"]) => split === "train" ? "Training" : split === "validation" ? "Validation" : "New-data test";
const sourceLabel = (source: TeamTrial["source"]) => source === "agent" ? "Agent-proposed rule" : source === "meta_model" ? "Model comparison" : source === "arbiter" ? "Independent review" : "Simple rule comparison";

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

function EvidenceCard({ evidence }: { evidence: TeamEvidence }) {
  return <details className="tr-evidence-card"><summary><span className="tr-evidence-icon"><FileSearch size={15} /></span><span className="tr-evidence-title"><strong>{evidence.tool}</strong><small>{evidence.evidence_id} · {when(evidence.created_at)}</small></span><ChevronDown size={15} className="tr-summary-chevron" /></summary><div className="tr-evidence-details"><div className="tr-evidence-meta"><span>Tool arguments</span><code>{json(evidence.args)}</code></div><div className="tr-evidence-meta"><span>Raw tool output</span><code>{json(evidence.payload)}</code></div></div></details>;
}

function HypothesisCard({ hypothesis, evidenceById, onEvidence }: { hypothesis: TeamHypothesis; evidenceById: Map<string, TeamEvidence>; onEvidence: (id: string) => void }) {
  return <article className={`tr-hypothesis ${hypothesis.direction === "works_better" ? "better" : "worse"}`}><div className="tr-hypothesis-top"><span className="tr-hypothesis-id">{hypothesis.hypothesis_id}</span><span className={`tr-confidence ${hypothesis.confidence}`}>{hypothesis.confidence} confidence</span></div><h3>{hypothesis.statement}</h3><div className="tr-conditions">{hypothesis.conditions.map(condition => <span key={condition}>{condition}</span>)}</div><p className="tr-suggested"><strong>Suggested test</strong>{hypothesis.suggested_test}</p>{hypothesis.caveats.length > 0 && <p className="tr-caveat"><Info size={14} />{hypothesis.caveats.join(" ")}</p>}<div className="tr-evidence-chips">{hypothesis.evidence_ids.map(id => <button type="button" key={id} onClick={() => onEvidence(id)} title={evidenceById.has(id) ? evidenceById.get(id)?.tool : "Missing evidence record"}><FileSearch size={12} />View evidence</button>)}</div></article>;
}

function TrialRow({ trial, orphanFold = false }: { trial: TeamTrial; orphanFold?: boolean }) {
  const refusal = trial.status === "refused";
  const isFold = trial.fold != null;
  const label = policyLabel(trial.policy_id);
  const className = [isFold ? "tr-fold" : "", refusal ? "tr-refused" : trial.status === "error" ? "tr-error" : ""].filter(Boolean).join(" ");
  const ruleCell = isFold
    ? <td className="tr-fold-label"><span>walk-forward fold {trial.fold}</span><small>{orphanFold ? `${label} · ` : ""}stability check on a train sub-period</small></td>
    : <td><strong>{label}</strong><small>{label !== trial.policy_id ? <><code>{trial.policy_id}</code> · </> : null}{sourceLabel(trial.source)}</small></td>;
  const note = isFold ? trial.evidence_id || "—" : trial.note || trial.evidence_id || "—";
  return <tr className={className}>{ruleCell}<td><span className="tr-split" title="Training develops the rule; validation checks it before a new-data test.">{isFold ? "Training fold" : splitLabel(trial.split)}</span></td><td className={trial.delta_net_return_vs_always_on !== null && trial.delta_net_return_vs_always_on > 0 ? "tr-positive" : ""}>{pts(trial.delta_net_return_vs_always_on)}</td><td>{ptsRange(trial.ci_delta)}</td><td><span className={`tr-trial-status ${trial.status}`}>{trial.status === "evaluated" ? <CircleCheck size={13} /> : trial.status === "refused" ? <CircleX size={13} /> : <AlertTriangle size={13} />}{trial.status}</span></td><td>{note}</td></tr>;
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
    ...orphans.map(trial => ({ trial, folds: [], orphan: true })),
  ];
}

function HealthCard({ health, alwaysOnNet }: { health: NonNullable<TeamReport["strategy_health"]>; alwaysOnNet?: number | null }) {
  const blocks = health.validation_blocks || [];
  const range = health.train_range;
  const within = health.status === "within_training_range";
  const outsideStatus = health.status === "outside_training_range";
  const status = within ? "Behaves as in training" : outsideStatus ? "Not behaving like training" : health.status.replaceAll("_", " ");
  const lostToo = within && typeof alwaysOnNet === "number" && alwaysOnNet < 0 ? " It lost money on validation too." : "";
  const statusDetail = (within ? "Validation results stay inside the range this strategy produced in training." : outsideStatus ? "Validation results left the range this strategy produced in training." : "") + lostToo;
  const horizon = range?.horizon_days ?? (range ? range.horizon_bars / 24 : null);
  const counts = { inside: blocks.filter(block => block.position === "inside").length, below: blocks.filter(block => block.position === "below").length, above: blocks.filter(block => block.position === "above").length };
  const width = 720, height = 168, left = 54, right = 10, top = 10, bottom = 24;
  const values = [0, ...blocks.map(block => block.net_return), ...(range ? [range.low, range.high] : [])];
  const rawLow = Math.min(...values), rawHigh = Math.max(...values);
  const padding = (rawHigh - rawLow || 0.01) * 0.08;
  const low = rawLow - padding, high = rawHigh + padding;
  const y = (value: number) => top + ((high - value) / (high - low)) * (height - top - bottom);
  const step = blocks.length > 0 ? (width - left - right) / blocks.length : 0;
  const barWidth = Math.max(1.5, step * 0.66);
  const zero = y(0);
  return <section className="tr-health panel" aria-labelledby="tr-health-title">
    <div className="tr-section-head"><div><span className="eyebrow">STRATEGY HEALTH</span><h2 id="tr-health-title">Unlucky or broken?</h2><p className={`tr-health-status ${within ? "within" : outsideStatus ? "outside" : ""}`}><strong>{status}.</strong> {statusDetail}</p></div></div>
    <div className="tr-health-body">
      <p className="tr-health-summary">{health.summary}</p>
      {blocks.length > 0 && <>
        <div className="tr-strip-wrap"><svg className="tr-strip" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${blocks.length} validation blocks: ${counts.inside} inside the training range, ${counts.below} below, ${counts.above} above.`}>
          {range && <rect className="tr-strip-band" x={left} width={width - left - right} y={y(range.high)} height={Math.max(1, y(range.low) - y(range.high))} />}
          <line className="tr-strip-zero" x1={left} x2={width - right} y1={zero} y2={zero} />
          {range && <><text className="tr-strip-tick" x={left - 6} y={y(range.high) + 4} textAnchor="end">{pct(range.high)}</text><text className="tr-strip-tick" x={left - 6} y={y(range.low) + 4} textAnchor="end">{pct(range.low)}</text></>}
          <text className="tr-strip-tick" x={left - 6} y={zero + 4} textAnchor="end">0</text>
          {blocks.map((block, index) => { const end = y(block.net_return); return <rect key={block.start} className={`tr-strip-bar ${block.position === "inside" ? "" : "outside"}`} x={left + index * step + (step - barWidth) / 2} width={barWidth} y={Math.min(zero, end)} height={Math.max(1, Math.abs(end - zero))}><title>{`${monthYear(block.start)} · ${pct(block.net_return)} · ${block.position} the training range`}</title></rect>; })}
          <text className="tr-strip-tick" x={left} y={height - 6}>{monthYear(blocks[0].start)}</text>
          <text className="tr-strip-tick" x={width - right} y={height - 6} textAnchor="end">{monthYear(blocks[blocks.length - 1].start)}</text>
        </svg></div>
        <div className="tr-strip-legend"><span><i className="tr-key-band" />Training range{range ? ` (${pct(range.low)} to ${pct(range.high)})` : ""}</span><span><i className="tr-key-bar" />Inside: {counts.inside}</span><span><i className="tr-key-bar outside" />Outside: {counts.below + counts.above}</span></div>
        <p className="tr-strip-caption">Each bar is the net return of one {horizon ? `${Number(horizon.toFixed(1))}-day` : ""} validation block, against the band of {horizon ? `${Number(horizon.toFixed(1))}-day` : ""} returns seen in training{range?.source ? ` (${range.source})` : ""}.</p>
      </>}
    </div>
  </section>;
}

function FrozenLookCard({ look }: { look: TeamFrozenLook }) {
  const evaluation = look.evaluation;
  const gate = evaluation.metrics || ({} as TeamFrozenLook["evaluation"]["metrics"]);
  const asIs = evaluation.always_on || ({} as TeamFrozenLook["evaluation"]["always_on"]);
  const net = typeof gate.net_return === "number" ? gate.net_return : null;
  const delta = evaluation.delta_net_return_vs_always_on;
  const smaller = typeof gate.exposure === "number" && typeof asIs.exposure === "number" && gate.exposure < asIs.exposure;
  const verdict = net !== null && net < 0
    ? delta !== null && delta > 0
      ? smaller ? "Loses less, mostly by trading smaller, but still loses money: kill." : "Loses less than as-is, but still loses money: kill."
      : "Still loses money: kill."
    : null;
  const policyId = look.champion_policy_id || evaluation.policy_id || "";
  return <section className="tr-look panel" aria-labelledby="tr-look-title">
    <div className="tr-section-head"><div><span className="eyebrow">TEST WINDOW</span><h2 id="tr-look-title">Test window, one look</h2><p>{policyId && <>Gate <code>{policyLabel(policyId)}</code> against the unchanged strategy (as-is){look.looked_at ? <> · looked at {when(look.looked_at)} UTC</> : null}.</>}</p></div><LockKeyhole size={18} /></div>
    <dl className="tr-look-stats">
      <div><dt>Gate vs as-is</dt><dd className={delta !== null && delta > 0 ? "tr-positive" : ""}>{pts(delta)}</dd><small>90% range {ptsRange(evaluation.ci_delta)}</small></div>
      <div><dt>Gate net return</dt><dd className={net !== null && net < 0 ? "tr-negative" : ""}>{pct(net)}</dd><small>as-is {pct(asIs.net_return)}</small></div>
      <div><dt>Max drawdown</dt><dd>{share(gate.max_drawdown)} <span>vs {share(asIs.max_drawdown)}</span></dd><small>gate vs always-on</small></div>
    </dl>
    {verdict && <p className="tr-look-verdict"><CircleX size={16} />{verdict}</p>}
    <p className="tr-look-caveat"><Info size={13} />This window overlaps data the team developed on; it is one pre-registered look, not unseen data.</p>
  </section>;
}

function ContextCard({ context }: { context: TeamContext }) {
  return <section className="tr-context panel" aria-labelledby="tr-context-title">
    <div className="tr-section-head"><div><span className="eyebrow">MARKET MOOD</span><h2 id="tr-context-title">Sentiment context</h2><p>Fear &amp; Greed around the best and worst training weeks. Co-occurrence in time only, not a cause.</p></div></div>
    <p className="tr-context-summary">{context.summary}</p>
    {context.findings.length > 0 && <ul className="tr-context-findings">{context.findings.map(finding => <li key={finding.finding_id}><span className={`tr-strength ${finding.strength}`}>{finding.strength === "none" ? "No signal" : `${finding.strength[0].toUpperCase()}${finding.strength.slice(1)} signal`}</span><p>{finding.statement}</p></li>)}</ul>}
  </section>;
}

function CandidateCard({ candidate }: { candidate: TeamCandidate }) {
  const eligible = candidate.status === "accepted_for_frozen_test";
  const competitor = candidate.status === "competitor";
  const label = policyLabel(candidate.policy_id);
  return <article className={`tr-candidate ${eligible ? "eligible" : competitor ? "competitor" : "rejected"}`}><div className="tr-candidate-head"><span className="tr-candidate-status">{eligible ? <><CircleCheck size={14} />Ready for a new-data test</> : competitor ? <><Info size={14} />Comparison rule</> : <><CircleX size={14} />Rejected</>}</span><code>{candidate.policy_id}</code></div>{label !== candidate.policy_id && <h3 className="tr-candidate-name">{label}</h3>}{typeof candidate.validation_delta_vs_always_on === "number" && <p className="tr-candidate-delta">Validation vs always-on: <strong>{pts(candidate.validation_delta_vs_always_on)}</strong>{candidate.validation_ci ? <> · 90% range {ptsRange(candidate.validation_ci)}</> : null}</p>}<p className="tr-candidate-note">{eligible ? "This trading rule passed the development-stage checks. It has not been validated on data it did not see during research." : competitor ? "This rule is included as a comparison point; it is not an agent-selected candidate." : "This trading rule will not proceed to the new-data test."}</p><ul>{candidate.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul><details className="tr-policy-spec"><summary>Trading rule details <ChevronRight size={13} /></summary><code>{json(candidate.policy_spec)}</code></details></article>;
}

export type TeamResearchProps = {
  /** Prefer the report that belongs to the current experiment when the native report store has it. */
  initialExperimentId?: string;
  /** The Part C strategy currently in focus; this is intentionally separate from the report identity. */
  strategyId?: string;
  /** Embedded report viewers can return to the evidence surface without adding a navigation destination. */
  onBack?: () => void;
};

export default function TeamResearch({ initialExperimentId = "", strategyId = "", onBack }: TeamResearchProps) {
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

  useEffect(() => { let cancelled = false; teamApi.investigations().then(items => { if (!cancelled) { const preferred = initialExperimentId && items.some(item => item.experiment_id === initialExperimentId) ? initialExperimentId : strategyId ? items.find(item => item.strategy_id === strategyId)?.experiment_id || items[0]?.experiment_id || "" : items[0]?.experiment_id || ""; setSummaries(items); setSelectedId(preferred); } }).catch(failure => { if (!cancelled) setError(failure instanceof Error ? failure.message : "Could not load investigations."); }).finally(() => { if (!cancelled) setLoading(false); }); return () => { cancelled = true; }; }, [initialExperimentId, strategyId]);
  useEffect(() => { if (!selectedId) { setWrapper(null); setError(""); setDetailLoading(false); return; } let cancelled = false; setDetailLoading(true); setWrapper(null); setError(""); teamApi.investigation(selectedId).then(item => { if (!cancelled) setWrapper(item); }).catch(failure => { if (!cancelled) { setWrapper(null); setError(failure instanceof Error ? failure.message : "Could not load this investigation."); } }).finally(() => { if (!cancelled) setDetailLoading(false); }); return () => { cancelled = true; }; }, [selectedId]);

  useEffect(() => { if (view !== "evidence" || !focusedEvidence) return; const element = document.getElementById(focusedEvidence); const details = element?.querySelector("details"); if (details) details.open = true; element?.scrollIntoView({ block: "center", behavior: "instant" }); setFocusedEvidence(null); }, [view, focusedEvidence]);
  const report = wrapper?.report;
  const evidenceById = useMemo(() => new Map((report?.evidence || []).map(item => [item.evidence_id, item])), [report]);
  const selectedSummary = summaries.find(item => item.experiment_id === selectedId);
  const trialGroups = useMemo(() => groupTrials(report?.trial_log || []), [report]);
  const displayedGroups = showAllTrials ? trialGroups : trialGroups.filter(group => group.trial.status !== "refused");
  const foldCount = (report?.trial_log || []).filter(item => item.fold != null).length;
  const attemptRows = (report?.trial_log.length || 0) - foldCount;
  const frozenLook = wrapper?.frozen_look || null;

  const backControl = onBack && <button className="tr-back-link" type="button" onClick={onBack}><ArrowLeft size={15} />Back to evidence</button>;
  if (loading) return <div className="tr-loading">{backControl}<FlaskConical size={25} /><strong>Loading agent investigations</strong><span>Reading trusted research artifacts.</span></div>;
  if (error && summaries.length === 0) return <div className="tr-empty">{backControl}<TriangleAlert size={28} /><h2>Investigation artifacts unavailable</h2><p>{error}</p></div>;
  return <div className="tr-shell">
      <div className="tr-heading page-heading">
      <div><span className="eyebrow"><Sparkles size={13} />AGENT RESEARCH</span><h1>Inside the investigation.</h1><p>Discover the strengths. Challenge the weaknesses. Follow the evidence.</p>{strategyId && <p className="tr-report-context">Workspace strategy: <strong>{strategyId}</strong>{report && report.strategy_id !== strategyId ? <> · Report strategy: <strong>{report.strategy_id}</strong></> : null}</p>}</div>
      <div className="tr-heading-right">{onBack && <button className="tr-back-link" type="button" onClick={onBack}><ArrowLeft size={15} />Back to evidence</button>}{summaries.length > 0 && <label className="tr-selector-label">Research run<select className="tr-select" value={selectedId} onChange={event => setSelectedId(event.target.value)} aria-label="Choose an investigation">{summaries.map(item => <option value={item.experiment_id} key={item.experiment_id}>{item.strategy_id}</option>)}</select></label>}</div>
    </div>
    {error && <div className="tr-inline-error" role="alert"><TriangleAlert size={16} />{error}</div>}
    {selectedSummary && <div className="tr-context-bar"><span><span className="tr-context-dot" />{selectedSummary.strategy_id}</span><ModeBadge item={selectedSummary} /><SourceBadge item={selectedSummary} /><span className="tr-context-time">{when(selectedSummary.generated_at)} UTC</span></div>}
    {detailLoading ? <div className="tr-loading tr-panel-loading"><Clock3 size={22} /><strong>Opening the investigation</strong><span>Loading hypotheses, experiments, and their evidence.</span></div> : report ? <>
      {report.holdout_accessed && <div className="tr-holdout-warning"><AlertTriangle size={18} /><div><strong>New-data test access recorded</strong><p>The research appears to have seen the data reserved for the final check. Inspect the trial log before treating this investigation as suitable for an unbiased new-data test.</p></div></div>}
      {wrapper?.synthetic && <div className="tr-synthetic-note"><Beaker size={16} /><div><strong>Recorded example</strong> · Scripted research on sample market data, with no language-model call. Trading rules still need a new-data test.</div></div>}
      <section className="tr-research-brief">
        <div className="tr-brief-content"><span className="eyebrow">THE RESEARCH QUESTION</span><h2>When does this strategy<br />deserve your confidence?</h2><p>Agents have examined the market conditions, tested competing explanations, and identified what to investigate next. The final check uses new data kept away from the research process.</p></div>
        <div className="tr-brief-numbers"><div><strong>{report.diagnostic.hypotheses.length.toString().padStart(2, "0")}</strong><span>hypotheses<br />investigated</span></div><div><strong>{report.n_policies_tried.toString().padStart(2, "0")}</strong><span>policy tests<br />tried</span></div><div><strong>{report.evidence.length.toString().padStart(2, "0")}</strong><span>evidence<br />records</span></div></div>
        <p className="tr-brief-note">Trial log: {attemptRows} policy runs (training, validation and refusals){foldCount > 0 ? `, plus ${foldCount} walk-forward fold checks grouped under their policy` : ""}. The count above is distinct policies tried.</p>
        <div className="tr-workflow" aria-label="Research stages"><span><CircleCheck size={15} />Observe</span><i /><span><CircleCheck size={15} />Explain</span><i /><span><CircleCheck size={15} />Challenge</span><i />{frozenLook ? <span><CircleCheck size={15} />Test window <small>One look</small></span> : <span className="tr-workflow-next"><Clock3 size={15} />New-data test <small>Next</small></span>}</div>
      </section>
      <div className="tr-view-tabs" role="tablist" aria-label="Investigation views">{([{id:"findings",label:"Findings",count:report.diagnostic.hypotheses.length},{id:"tests",label:"Trading rules",count:report.n_policies_tried},{id:"evidence",label:"Evidence library",count:report.evidence.length}] as const).map(item=><button key={item.id} role="tab" id={`tr-tab-${item.id}`} aria-selected={view===item.id} aria-controls="tr-view-panel" onClick={()=>setView(item.id)} className={view===item.id ? "active" : ""}>{item.label}<span>{item.count}</span></button>)}</div>
      <div id="tr-view-panel" role="tabpanel" aria-labelledby={`tr-tab-${view}`}>
      {view === "findings" && <div className="tr-findings-layout">
        <div className="tr-main-column">
          {report.strategy_health && <HealthCard health={report.strategy_health} alwaysOnNet={report.validation_always_on?.net_return} />}
          {frozenLook && <FrozenLookCard look={frozenLook} />}
          <section className="tr-section panel"><div className="tr-section-head"><div><span className="eyebrow">STRENGTHS & WEAK SPOTS</span><h2>What the agents discovered</h2><p>These are testable explanations, with evidence you can inspect.</p></div><Sparkles size={18} className="purple" /></div><div className="tr-hypotheses">{report.diagnostic.hypotheses.map(hypothesis => <HypothesisCard key={hypothesis.hypothesis_id} hypothesis={hypothesis} evidenceById={evidenceById} onEvidence={id => { setView("evidence"); setFocusedEvidence(id); }} />)}</div>
          {report.diagnostic.rejected_explanations.length > 0 && <details className="tr-rejected"><summary><CircleX size={16} />Explanations that did not hold up <span>{report.diagnostic.rejected_explanations.length}</span><ChevronDown size={16} /></summary><ul>{report.diagnostic.rejected_explanations.map(item => <li key={item}>{item}</li>)}</ul></details>}</section>
          <section className="tr-summary-panel panel"><div className="tr-panel-kicker"><span className="eyebrow">RECORDED ANALYST SUMMARY</span><ModeBadge item={report} compact /></div><p>{report.diagnostic.summary}</p><p className="tr-summary-help">This is the summary recorded by the research run. Returns include the listed costs; it is evidence for review, not a promise about future performance.</p></section>
          {report.context && <ContextCard context={report.context} />}
        </div>
        <aside className="tr-findings-aside"><section className="tr-next-card"><span className="tr-next-symbol"><FlaskConical size={25} /></span><span className="eyebrow">THE NEXT DECISION</span><h2>Which trading rules deserve<br />a fair test?</h2><p>Inspect how each candidate performed during development, and why it was accepted or rejected.</p><button className="button primary" onClick={()=>setView("tests")}>Review trading rules <ChevronRight size={15} /></button><span className="tr-next-foot"><LockKeyhole size={13} />{frozenLook ? "Test window looked at once; result above" : "New-data test still pending"}</span></section>
        <details className="tr-limits-card"><summary><Info size={16} />What to keep in mind<ChevronDown size={15} /></summary><ul>{[...report.diagnostic.limitations, ...report.limitations].map((limitation, index) => <li key={index}>{limitation}</li>)}</ul></details></aside>
      </div>}
      {view === "tests" && <div className="tr-tests-view"><section className="tr-section panel"><div className="tr-section-head"><div><span className="eyebrow">THE CHALLENGE LOG</span><h2>Every attempt tells you something.</h2><p>{report.n_policies_tried} policies tried. Accepted, refused, and failed tests remain part of the research record{foldCount > 0 ? "; walk-forward folds sit under their policy and are stability checks, not extra attempts" : ""}.</p></div><div className="tr-toggles">{foldCount > 0 && <button className="tr-toggle" onClick={() => setShowFolds(current => !current)}>{showFolds ? "Hide folds" : "Show folds"}<ChevronDown size={14} /></button>}<button className="tr-toggle" onClick={() => setShowAllTrials(current => !current)}>{showAllTrials ? "Hide refusals" : "Show refusals"}<ChevronDown size={14} /></button></div></div><div className="tr-table-wrap"><table className="tr-table"><thead><tr><th>Trading rule</th><th><span title="Training data develops the rule; validation data is the check before a new-data test.">Research stage <Info size={12} /></span></th><th><span title="The measured return change compared with leaving the original strategy on, in percentage points.">Change vs always-on <Info size={12} /></span></th><th><span title="A 90% uncertainty range around the measured change, in percentage points; it is not a guarantee.">Likely range <Info size={12} /></span></th><th>Status</th><th>Evidence / note</th></tr></thead><tbody>{displayedGroups.filter(group => showFolds || !group.orphan).flatMap((group, index) => [<TrialRow key={`${group.trial.policy_id}-${group.trial.split}-${group.trial.fold ?? "run"}-${index}`} trial={group.trial} orphanFold={group.orphan} />, ...(showFolds ? group.folds.map(fold => <TrialRow key={`${fold.policy_id}-fold-${fold.fold}-${index}`} trial={fold} />) : [])])}</tbody></table></div><p className="tr-table-help"><strong>How to read this:</strong> “Training” is where a rule is developed; “validation” is a check before the final new-data test. “Change vs always-on” compares with leaving the original strategy running, in percentage points. A walk-forward fold re-checks a policy on one slice of the training period; it is a stability check, not another attempt. The likely range shows how uncertain that measured change is.</p></section>
        <section className="tr-section panel"><div className="tr-section-head"><div><span className="eyebrow">CANDIDATES FOR FURTHER TESTING</span><h2>What can move forward?</h2><p>Readiness for a new-data test does not establish profitability.</p></div><span className="tr-count">{report.candidates.length}</span></div><div className="tr-candidates">{report.candidates.map(candidate => <CandidateCard key={candidate.policy_id} candidate={candidate} />)}</div></section>
        <div className="tr-evidence-shortcut"><FileSearch size={18} /><p>Every result has a source. Inspect the technical tool outputs behind this comparison.</p><button className="button secondary" onClick={()=>setView("evidence")}>Open evidence <ChevronRight size={15} /></button></div>
      </div>}
      {view === "evidence" && <div className="tr-evidence-view"><section className="tr-side-panel panel"><div className="tr-side-head"><div><span className="eyebrow">TRACEABLE RESEARCH</span><h2>The evidence behind the findings</h2></div><span className="tr-count">{report.evidence.length}</span></div><div className="tr-evidence-list">{report.evidence.map(evidence => <div id={evidence.evidence_id} key={evidence.evidence_id}><EvidenceCard evidence={evidence} /></div>)}</div></section><section className="tr-side-panel panel"><div className="tr-side-head"><div><span className="eyebrow">NEXT STEPS</span><h2>Requested evaluation</h2></div><Clock3 size={17} /></div><div className="tr-request-list">{report.test_requests.length > 0 ? report.test_requests.map(request => <p key={request}><ChevronRight size={14} />{request}</p>) : <p className="tr-muted">No additional tests requested.</p>}</div><div className="tr-source-record"><span>Source artifact</span><code>{wrapper?.source_path}</code><span>Experiment</span><code>{report.experiment_id}</code></div></section></div>}
      </div>
    </> : <div className="tr-empty"><FileSearch size={30} /><h2>No investigations found</h2><p>Start an investigation to bring your agents’ findings and evidence together.</p></div>}
  </div>;
}
