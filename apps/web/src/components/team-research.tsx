"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowLeft, Beaker, ChevronDown, ChevronRight, CircleCheck, CircleX, Clock3, FileSearch, FlaskConical, Info, LockKeyhole, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import { teamApi, type InvestigationSummary, type InvestigationWrapper, type TeamCandidate, type TeamEvidence, type TeamHypothesis, type TeamReport, type TeamTrial } from "@/lib/team-api";
import type { FrozenEvaluation } from "../../../../packages/contracts/research";
import { MascotCallout } from "./redesign/mascot";
import ResearchSourceBrowser from "./research-source-browser";
import "./team-research.css";

const pct = (value: number | null) => value === null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
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
  return value.frozen_evaluation || value.integration_audit?.frozen_evaluation || value.report.frozen_evaluation || value.report.integration_audit?.frozen_evaluation || null;
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

function TrialRow({ trial }: { trial: TeamTrial }) {
  const refusal = trial.status === "refused";
  return <tr className={refusal ? "tr-refused" : trial.status === "error" ? "tr-error" : ""}><td><strong>{trial.policy_id}</strong><small>{sourceLabel(trial.source)}</small></td><td><span className="tr-split" title="Training develops the rule; validation checks it before a new-data test.">{splitLabel(trial.split)}</span></td><td className={trial.delta_net_return_vs_always_on !== null && trial.delta_net_return_vs_always_on > 0 ? "tr-positive" : ""}>{pct(trial.delta_net_return_vs_always_on)}</td><td>{trial.ci_delta ? `[${pct(trial.ci_delta[0])}, ${pct(trial.ci_delta[1])}]` : "—"}</td><td><span className={`tr-trial-status ${trial.status}`}>{trial.status === "evaluated" ? <CircleCheck size={13} /> : trial.status === "refused" ? <CircleX size={13} /> : <AlertTriangle size={13} />}{trial.status}</span></td><td>{trial.note || trial.evidence_id || "—"}</td></tr>;
}

function CandidateCard({ candidate, historical = false }: { candidate: TeamCandidate; historical?: boolean }) {
  const eligible = candidate.status === "accepted_for_frozen_test";
  const competitor = candidate.status === "competitor";
  return <article className={`tr-candidate ${eligible ? "eligible" : competitor ? "competitor" : "rejected"} ${historical ? "historical" : ""}`}><div className="tr-candidate-head"><span className="tr-candidate-status">{historical ? <><CircleCheck size={14} />Selected for the sealed look</> : eligible ? <><CircleCheck size={14} />Candidate for a new-data test</> : competitor ? <><Info size={14} />Comparison rule</> : <><CircleX size={14} />Rejected</>}</span><code>{candidate.policy_id}</code></div><p className="tr-candidate-note">{historical ? "This policy was selected during development before the sealed look. The recorded result remains provisional and does not unlock a paper plan." : eligible ? "This trading rule passed the development-stage checks. It has not been validated on data it did not see during research." : competitor ? "This rule is included as a comparison point; it is not an agent-selected candidate." : "This trading rule will not proceed to the new-data test."}</p><details className="tr-candidate-reasons"><summary>Why this selection? <ChevronRight size={13} /></summary><ul>{candidate.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></details><details className="tr-policy-spec"><summary>Trading rule details <ChevronRight size={13} /></summary><code>{json(candidate.policy_spec)}</code></details></article>;
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
  const [focusedEvidence, setFocusedEvidence] = useState<string | null>(null);
  const [view, setView] = useState<"findings" | "tests" | "evidence">("findings");

  useEffect(() => { let cancelled = false; teamApi.investigations().then(items => { if (!cancelled) { const preferred = initialExperimentId && items.some(item => item.experiment_id === initialExperimentId) ? initialExperimentId : strategyId ? items.find(item => item.strategy_id === strategyId)?.experiment_id || items[0]?.experiment_id || "" : items[0]?.experiment_id || ""; setSummaries(items); setSelectedId(preferred); } }).catch(failure => { if (!cancelled) setError(failure instanceof Error ? failure.message : "Could not load investigations."); }).finally(() => { if (!cancelled) setLoading(false); }); return () => { cancelled = true; }; }, [initialExperimentId, strategyId]);
  useEffect(() => { if (!selectedId) { setWrapper(null); setError(""); setDetailLoading(false); return; } let cancelled = false; setDetailLoading(true); setWrapper(null); setError(""); teamApi.investigation(selectedId).then(item => { if (!cancelled) setWrapper(item); }).catch(failure => { if (!cancelled) { setWrapper(null); setError(failure instanceof Error ? failure.message : "Could not load this investigation."); } }).finally(() => { if (!cancelled) setDetailLoading(false); }); return () => { cancelled = true; }; }, [selectedId]);

  const report = wrapper?.report;
  const evidenceById = useMemo(() => new Map((report?.evidence || []).map(item => [item.evidence_id, item])), [report]);
  const selectedSummary = summaries.find(item => item.experiment_id === selectedId);
  const displayedTrials = showAllTrials ? report?.trial_log || [] : (report?.trial_log || []).filter(item => item.status !== "refused");
  const sealedEvaluation = frozenEvaluation?.experiment_id === report?.experiment_id && frozenEvaluation?.strategy_id === report?.strategy_id ? frozenEvaluation : frozenLook(wrapper);
  const verdict = report ? reportVerdict(report, sealedEvaluation) : null;
  useEffect(() => { if (report?.experiment_id) document.getElementById("tr-verdict-title")?.focus({ preventScroll: true }); }, [report?.experiment_id]);

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
        </div>
        <aside className="tr-findings-aside"><section className="tr-next-card"><span className="tr-next-symbol"><FlaskConical size={25} /></span><span className="eyebrow">SECONDARY DETAIL</span><h2>Rules under pressure.</h2><p>Accepted, refused, and failed trials stay in the Rules tested tab. Use it to inspect the historical selection and its alternatives.</p><span className="tr-next-foot"><LockKeyhole size={13} />{sealedEvaluation ? "Sealed look recorded · paper plan locked" : report.champion_policy_id ? "Candidate awaits a sealed look" : "No candidate earned a sealed look"}</span></section>
        <details className="tr-limits-card"><summary><Info size={16} />What to keep in mind<ChevronDown size={15} /></summary><ul>{[...report.diagnostic.limitations, ...report.limitations].map((limitation, index) => <li key={index}>{limitation}</li>)}</ul></details></aside>
      </div>}
      {view === "tests" && <div className="tr-tests-view" data-guide-target="evidence-path"><section className="tr-section panel"><div className="tr-section-head"><div><span className="eyebrow">THE CHALLENGE LOG</span><h2>Rules under pressure.</h2><p>{report.n_policies_tried} distinct policies across {report.trial_log.length} recorded trial rows.</p></div><button className="tr-toggle" onClick={() => setShowAllTrials(current => !current)}>{showAllTrials ? "Hide refusals" : "Show refusals"}<ChevronDown size={14} /></button></div><div className="tr-table-wrap"><table className="tr-table"><thead><tr><th>Trading rule</th><th><span title="Training data develops the rule; validation data is the check before a new-data test.">Research stage <Info size={12} /></span></th><th><span title="The measured return change compared with leaving the original strategy on.">Change vs always-on <Info size={12} /></span></th><th><span title="A 90% uncertainty range around the measured change; it is not a guarantee.">Likely range <Info size={12} /></span></th><th>Status</th><th>Evidence / note</th></tr></thead><tbody>{displayedTrials.map((trial, index) => <TrialRow key={`${trial.policy_id}-${trial.split}-${index}`} trial={trial} />)}</tbody></table></div><p className="tr-table-help"><strong>How to read this:</strong> Training develops the rule; validation checks it before a new-data test. Change vs always-on compares with leaving the original strategy running. The likely range shows uncertainty around that measured change.</p></section>
        <section className="tr-section panel"><div className="tr-section-head"><div><span className="eyebrow">CANDIDATES FOR FURTHER TESTING</span><h2>What can move forward?</h2><p>{sealedEvaluation ? "Historical selection is shown separately from the sealed result." : "Readiness for a new-data test does not establish profitability."}</p></div><span className="tr-count">{report.candidates.length}</span></div><div className="tr-candidates">{report.candidates.map(candidate => <CandidateCard key={candidate.policy_id} candidate={candidate} historical={Boolean(sealedEvaluation && candidate.policy_id === report.champion_policy_id)} />)}</div></section>
        <div className="tr-evidence-shortcut"><FileSearch size={18} /><p>Every result has a source. Inspect the technical tool outputs behind this comparison.</p><button className="button secondary" onClick={()=>setView("evidence")}>Open evidence <ChevronRight size={15} /></button></div>
      </div>}
      {view === "evidence" && <div className="tr-evidence-view"><ResearchSourceBrowser evidence={report.evidence} focusedEvidence={focusedEvidence} /><section className="tr-side-panel panel"><div className="tr-side-head"><div><span className="eyebrow">RECORDED REQUESTS</span><h2>What did the agents ask to check?</h2></div><Clock3 size={17} /></div><div className="tr-request-list">{report.test_requests.length > 0 ? report.test_requests.map(request => <p key={request}><ChevronRight size={14} />{request}</p>) : <p className="tr-muted">No additional tests requested.</p>}</div><div className="tr-source-record"><span>Source artifact</span><code>{wrapper?.source_path}</code><span>Experiment</span><code>{report.experiment_id}</code></div></section></div>}
      </div>
    </> : <div className="tr-empty"><FileSearch size={30} /><h2>No investigations found</h2><p>Start an investigation to bring your agents’ findings and evidence together.</p></div>}
  </div>;
}
