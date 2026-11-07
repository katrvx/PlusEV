"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Beaker, ChevronDown, ChevronRight, CircleCheck, CircleX, Clock3, FileSearch, FlaskConical, Info, LockKeyhole, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import { teamApi, type InvestigationSummary, type InvestigationWrapper, type TeamCandidate, type TeamEvidence, type TeamHypothesis, type TeamTrial } from "@/lib/team-api";
import "./team-research.css";

const pct = (value: number | null) => value === null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
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

function TrialRow({ trial }: { trial: TeamTrial }) {
  const refusal = trial.status === "refused";
  return <tr className={refusal ? "tr-refused" : trial.status === "error" ? "tr-error" : ""}><td><strong>{trial.policy_id}</strong><small>{sourceLabel(trial.source)}</small></td><td><span className="tr-split" title="Training develops the rule; validation checks it before a new-data test.">{splitLabel(trial.split)}</span></td><td className={trial.delta_net_return_vs_always_on !== null && trial.delta_net_return_vs_always_on > 0 ? "tr-positive" : ""}>{pct(trial.delta_net_return_vs_always_on)}</td><td>{trial.ci_delta ? `[${pct(trial.ci_delta[0])}, ${pct(trial.ci_delta[1])}]` : "—"}</td><td><span className={`tr-trial-status ${trial.status}`}>{trial.status === "evaluated" ? <CircleCheck size={13} /> : trial.status === "refused" ? <CircleX size={13} /> : <AlertTriangle size={13} />}{trial.status}</span></td><td>{trial.note || trial.evidence_id || "—"}</td></tr>;
}

function CandidateCard({ candidate }: { candidate: TeamCandidate }) {
  const eligible = candidate.status === "accepted_for_frozen_test";
  const competitor = candidate.status === "competitor";
  return <article className={`tr-candidate ${eligible ? "eligible" : competitor ? "competitor" : "rejected"}`}><div className="tr-candidate-head"><span className="tr-candidate-status">{eligible ? <><CircleCheck size={14} />Ready for a new-data test</> : competitor ? <><Info size={14} />Comparison rule</> : <><CircleX size={14} />Rejected</>}</span><code>{candidate.policy_id}</code></div><p className="tr-candidate-note">{eligible ? "This trading rule passed the development-stage checks. It has not been validated on data it did not see during research." : competitor ? "This rule is included as a comparison point; it is not an agent-selected candidate." : "This trading rule will not proceed to the new-data test."}</p><ul>{candidate.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul><details className="tr-policy-spec"><summary>Trading rule details <ChevronRight size={13} /></summary><code>{json(candidate.policy_spec)}</code></details></article>;
}

export default function TeamResearch() {
  const [summaries, setSummaries] = useState<InvestigationSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [wrapper, setWrapper] = useState<InvestigationWrapper | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [showAllTrials, setShowAllTrials] = useState(true);
  const [focusedEvidence, setFocusedEvidence] = useState<string | null>(null);
  const [view, setView] = useState<"findings" | "tests" | "evidence">("findings");

  useEffect(() => { let cancelled = false; teamApi.investigations().then(items => { if (!cancelled) { setSummaries(items); setSelectedId(items[0]?.experiment_id || ""); } }).catch(failure => { if (!cancelled) setError(failure instanceof Error ? failure.message : "Could not load investigations."); }).finally(() => { if (!cancelled) setLoading(false); }); return () => { cancelled = true; }; }, []);
  useEffect(() => { if (!selectedId) { setWrapper(null); setError(""); setDetailLoading(false); return; } let cancelled = false; setDetailLoading(true); setWrapper(null); setError(""); teamApi.investigation(selectedId).then(item => { if (!cancelled) setWrapper(item); }).catch(failure => { if (!cancelled) { setWrapper(null); setError(failure instanceof Error ? failure.message : "Could not load this investigation."); } }).finally(() => { if (!cancelled) setDetailLoading(false); }); return () => { cancelled = true; }; }, [selectedId]);

  useEffect(() => { if (view !== "evidence" || !focusedEvidence) return; const element = document.getElementById(focusedEvidence); const details = element?.querySelector("details"); if (details) details.open = true; element?.scrollIntoView({ block: "center", behavior: "instant" }); setFocusedEvidence(null); }, [view, focusedEvidence]);
  const report = wrapper?.report;
  const evidenceById = useMemo(() => new Map((report?.evidence || []).map(item => [item.evidence_id, item])), [report]);
  const selectedSummary = summaries.find(item => item.experiment_id === selectedId);
  const displayedTrials = showAllTrials ? report?.trial_log || [] : (report?.trial_log || []).filter(item => item.status !== "refused");

  if (loading) return <div className="tr-loading"><FlaskConical size={25} /><strong>Loading agent investigations</strong><span>Reading trusted research artifacts.</span></div>;
  if (error && summaries.length === 0) return <div className="tr-empty"><TriangleAlert size={28} /><h2>Investigation artifacts unavailable</h2><p>{error}</p></div>;
  return <div className="tr-shell">
    <div className="tr-heading page-heading">
      <div><span className="eyebrow"><Sparkles size={13} />AGENT RESEARCH</span><h1>Inside the investigation.</h1><p>Discover the strengths. Challenge the weaknesses. Follow the evidence.</p></div>
      <div className="tr-heading-right">{summaries.length > 0 && <label className="tr-selector-label">Research run<select className="tr-select" value={selectedId} onChange={event => setSelectedId(event.target.value)} aria-label="Choose an investigation">{summaries.map(item => <option value={item.experiment_id} key={item.experiment_id}>{item.strategy_id}</option>)}</select></label>}</div>
    </div>
    {error && <div className="tr-inline-error" role="alert"><TriangleAlert size={16} />{error}</div>}
    {selectedSummary && <div className="tr-context-bar"><span><span className="tr-context-dot" />{selectedSummary.strategy_id}</span><ModeBadge item={selectedSummary} /><SourceBadge item={selectedSummary} /><span className="tr-context-time">{when(selectedSummary.generated_at)} UTC</span></div>}
    {detailLoading ? <div className="tr-loading tr-panel-loading"><Clock3 size={22} /><strong>Opening the investigation</strong><span>Loading hypotheses, experiments, and their evidence.</span></div> : report ? <>
      {report.holdout_accessed && <div className="tr-holdout-warning"><AlertTriangle size={18} /><div><strong>New-data test access recorded</strong><p>The research appears to have seen the data reserved for the final check. Inspect the trial log before treating this investigation as suitable for an unbiased new-data test.</p></div></div>}
      {wrapper?.synthetic && <div className="tr-synthetic-note"><Beaker size={16} /><div><strong>Recorded example</strong> · Scripted research on sample market data, with no language-model call. Trading rules still need a new-data test.</div></div>}
      <section className="tr-research-brief">
        <div className="tr-brief-content"><span className="eyebrow">THE RESEARCH QUESTION</span><h2>When does this strategy<br />deserve your confidence?</h2><p>Agents have examined the market conditions, tested competing explanations, and identified what to investigate next. The final check uses new data kept away from the research process.</p></div>
        <div className="tr-brief-numbers"><div><strong>{report.diagnostic.hypotheses.length.toString().padStart(2, "0")}</strong><span>hypotheses<br />investigated</span></div><div><strong>{report.trial_log.length.toString().padStart(2, "0")}</strong><span>policy tests<br />recorded</span></div><div><strong>{report.evidence.length.toString().padStart(2, "0")}</strong><span>evidence<br />records</span></div></div>
        <div className="tr-workflow" aria-label="Research stages"><span><CircleCheck size={15} />Observe</span><i /><span><CircleCheck size={15} />Explain</span><i /><span><CircleCheck size={15} />Challenge</span><i /><span className="tr-workflow-next"><Clock3 size={15} />New-data test <small>Next</small></span></div>
      </section>
      <div className="tr-view-tabs" role="tablist" aria-label="Investigation views">{([{id:"findings",label:"Findings",count:report.diagnostic.hypotheses.length},{id:"tests",label:"Trading rules",count:report.trial_log.length},{id:"evidence",label:"Evidence library",count:report.evidence.length}] as const).map(item=><button key={item.id} role="tab" id={`tr-tab-${item.id}`} aria-selected={view===item.id} aria-controls="tr-view-panel" onClick={()=>setView(item.id)} className={view===item.id ? "active" : ""}>{item.label}<span>{item.count}</span></button>)}</div>
      <div id="tr-view-panel" role="tabpanel" aria-labelledby={`tr-tab-${view}`}>
      {view === "findings" && <div className="tr-findings-layout">
        <div className="tr-main-column">
          <section className="tr-section panel"><div className="tr-section-head"><div><span className="eyebrow">STRENGTHS & WEAK SPOTS</span><h2>What the agents discovered</h2><p>These are testable explanations, with evidence you can inspect.</p></div><Sparkles size={18} className="purple" /></div><div className="tr-hypotheses">{report.diagnostic.hypotheses.map(hypothesis => <HypothesisCard key={hypothesis.hypothesis_id} hypothesis={hypothesis} evidenceById={evidenceById} onEvidence={id => { setView("evidence"); setFocusedEvidence(id); }} />)}</div>
          {report.diagnostic.rejected_explanations.length > 0 && <details className="tr-rejected"><summary><CircleX size={16} />Explanations that did not hold up <span>{report.diagnostic.rejected_explanations.length}</span><ChevronDown size={16} /></summary><ul>{report.diagnostic.rejected_explanations.map(item => <li key={item}>{item}</li>)}</ul></details>}</section>
          <section className="tr-summary-panel panel"><div className="tr-panel-kicker"><span className="eyebrow">RECORDED ANALYST SUMMARY</span><ModeBadge item={report} compact /></div><p>{report.diagnostic.summary}</p><p className="tr-summary-help">This is the summary recorded by the research run. Returns include the listed costs; it is evidence for review, not a promise about future performance.</p></section>
        </div>
        <aside className="tr-findings-aside"><section className="tr-next-card"><span className="tr-next-symbol"><FlaskConical size={25} /></span><span className="eyebrow">THE NEXT DECISION</span><h2>Which trading rules deserve<br />a fair test?</h2><p>Inspect how each candidate performed during development, and why it was accepted or rejected.</p><button className="button primary" onClick={()=>setView("tests")}>Review trading rules <ChevronRight size={15} /></button><span className="tr-next-foot"><LockKeyhole size={13} />New-data test still pending</span></section>
        <details className="tr-limits-card"><summary><Info size={16} />What to keep in mind<ChevronDown size={15} /></summary><ul>{[...report.diagnostic.limitations, ...report.limitations].map((limitation, index) => <li key={index}>{limitation}</li>)}</ul></details></aside>
      </div>}
      {view === "tests" && <div className="tr-tests-view"><section className="tr-section panel"><div className="tr-section-head"><div><span className="eyebrow">THE CHALLENGE LOG</span><h2>Every attempt tells you something.</h2><p>Accepted, refused, and failed tests remain part of the research record.</p></div><button className="tr-toggle" onClick={() => setShowAllTrials(current => !current)}>{showAllTrials ? "Hide refusals" : "Show refusals"}<ChevronDown size={14} /></button></div><div className="tr-table-wrap"><table className="tr-table"><thead><tr><th>Trading rule</th><th><span title="Training data develops the rule; validation data is the check before a new-data test.">Research stage <Info size={12} /></span></th><th><span title="The measured return change compared with leaving the original strategy on.">Change vs always-on <Info size={12} /></span></th><th><span title="A 90% uncertainty range around the measured change; it is not a guarantee.">Likely range <Info size={12} /></span></th><th>Status</th><th>Evidence / note</th></tr></thead><tbody>{displayedTrials.map((trial, index) => <TrialRow key={`${trial.policy_id}-${trial.split}-${index}`} trial={trial} />)}</tbody></table></div><p className="tr-table-help"><strong>How to read this:</strong> “Training” is where a rule is developed; “validation” is a check before the final new-data test. “Change vs always-on” compares with leaving the original strategy running. The likely range shows how uncertain that measured change is.</p></section>
        <section className="tr-section panel"><div className="tr-section-head"><div><span className="eyebrow">CANDIDATES FOR FURTHER TESTING</span><h2>What can move forward?</h2><p>Readiness for a new-data test does not establish profitability.</p></div><span className="tr-count">{report.candidates.length}</span></div><div className="tr-candidates">{report.candidates.map(candidate => <CandidateCard key={candidate.policy_id} candidate={candidate} />)}</div></section>
        <div className="tr-evidence-shortcut"><FileSearch size={18} /><p>Every result has a source. Inspect the technical tool outputs behind this comparison.</p><button className="button secondary" onClick={()=>setView("evidence")}>Open evidence <ChevronRight size={15} /></button></div>
      </div>}
      {view === "evidence" && <div className="tr-evidence-view"><section className="tr-side-panel panel"><div className="tr-side-head"><div><span className="eyebrow">TRACEABLE RESEARCH</span><h2>The evidence behind the findings</h2></div><span className="tr-count">{report.evidence.length}</span></div><div className="tr-evidence-list">{report.evidence.map(evidence => <div id={evidence.evidence_id} key={evidence.evidence_id}><EvidenceCard evidence={evidence} /></div>)}</div></section><section className="tr-side-panel panel"><div className="tr-side-head"><div><span className="eyebrow">NEXT STEPS</span><h2>Requested evaluation</h2></div><Clock3 size={17} /></div><div className="tr-request-list">{report.test_requests.length > 0 ? report.test_requests.map(request => <p key={request}><ChevronRight size={14} />{request}</p>) : <p className="tr-muted">No additional tests requested.</p>}</div><div className="tr-source-record"><span>Source artifact</span><code>{wrapper?.source_path}</code><span>Experiment</span><code>{report.experiment_id}</code></div></section></div>}
      </div>
    </> : <div className="tr-empty"><FileSearch size={30} /><h2>No investigations found</h2><p>Start an investigation to bring your agents’ findings and evidence together.</p></div>}
  </div>;
}
