"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, ChevronDown, ExternalLink, FileSearch, Info, X } from "lucide-react";
import type { Evidence, Experiment, Strategy } from "./types";
import TeamResearch from "../team-research";
import KineticText from "./kinetic-text";
import { MascotCallout } from "./mascot";
import ResearchTrace, { buildNativeTraceSteps, humanAction, humanRole, statusCopy } from "./research-trace";
import "./evidence.css";

export type EvidenceViewProps = {
  experiment: Experiment;
  strategy: Strategy;
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
  onEvidence: (id: string) => void;
  onCompare: () => void;
};

function formatRecord(value: Record<string, unknown>) {
  try {
    return JSON.stringify(value, null, 2) || "{}";
  } catch {
    return "This recorded value could not be rendered here.";
  }
}

function researchStageLabel(value?: string | null) {
  const cleaned = value?.trim() || "";
  if (!cleaned || /^(?:window\s+)?not\s+supplied$/i.test(cleaned) || /^not\s+recorded$/i.test(cleaned)) return "Not recorded";
  const exact: Record<string, string> = {
    train: "Training",
    training: "Training",
    validation: "Validation",
    test: "Held-out test",
    holdout: "Held-out test",
    "held-out": "Held-out test",
    "held-out test": "Held-out test",
    "new-data test": "Held-out test",
  };
  const direct = exact[cleaned.toLowerCase()];
  if (direct) return direct;
  const prefixed = cleaned.match(/^(train(?:ing)?|validation|test|hold[- ]?out(?:\s+test)?|new[- ]data\s+test)\s*:\s*(.+)$/i);
  if (!prefixed) return cleaned;
  const label = exact[prefixed[1].toLowerCase()] || prefixed[1];
  return `${label} · ${prefixed[2].trim()}`;
}

function EvidenceDialog({ evidence, onClose }: { evidence: Evidence; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const closeRef = useRef(onClose);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  closeRef.current = onClose;
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialog.showModal();
    const close = () => {
      // React StrictMode can replay the effect: the cleanup closes the first
      // dialog instance, and that native close event may be delivered after
      // the second effect has registered its listener. If a fresh modal is
      // already open, this is that stale event; do not dismiss the new one.
      if (dialog.open) return;
      returnFocusRef.current?.focus();
      closeRef.current();
    };
    dialog.addEventListener("close", close);
    return () => {
      dialog.removeEventListener("close", close);
      if (dialog.open) dialog.close();
      returnFocusRef.current?.focus();
    };
  }, []);
  return <dialog ref={ref} className="ev-dialog" aria-labelledby="ev-dialog-title" onCancel={event => { event.preventDefault(); onClose(); }} onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="ev-dialog-head"><span className="ev-kicker">SOURCE DETAIL</span><button className="ev-icon-button" type="button" aria-label="Close evidence" onClick={onClose}><X size={18} /></button></div>
    <div className="ev-dialog-body"><h2 id="ev-dialog-title">{evidence.title}</h2><p>{evidence.summary}</p><dl className="ev-facts">{evidence.facts.map(fact => <div key={fact.label}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}</dl><div className="ev-source"><span>Source</span><strong>{evidence.source}</strong><span>Research stage</span><strong>{researchStageLabel(evidence.window)}</strong></div><details className="ev-raw-detail"><summary><span><span className="ev-raw-kicker">RECORDED TOOL DATA</span><strong>Show tool arguments and output</strong></span><ChevronDown size={16} aria-hidden="true" /></summary><div className="ev-raw-body"><div className="ev-raw-block"><span>Tool arguments</span>{evidence.args ? <pre tabIndex={0} aria-label="Recorded tool arguments">{formatRecord(evidence.args)}</pre> : <p>No tool arguments were attached to this source summary.</p>}</div><div className="ev-raw-block"><span>Recorded output</span>{evidence.output ? <pre tabIndex={0} aria-label="Recorded tool output">{formatRecord(evidence.output)}</pre> : <p>No raw output was attached to this source summary.</p>}</div></div></details></div>
  </dialog>;
}

export { EvidenceDialog };

function Hypothesis({ item, onEvidence }: { item: Experiment["hypotheses"][number]; onEvidence: (id: string) => void }) {
  const label = item.status === "supported" ? "Pattern worth testing" : item.status === "rejected" ? "Explanation rejected" : "Still uncertain";
  return <article className={`ev-hypothesis ev-${item.status}`}>
    <div className="ev-row-top"><span className="ev-index">{item.id}</span><span className="ev-status">{label}</span></div>
    <h3>{item.title}</h3><p>{item.finding}</p>
    {item.evidence_ids.length > 0 ? <div className="ev-links">{item.evidence_ids.map(id => <button key={id} type="button" onClick={() => onEvidence(id)}><FileSearch size={14} />Open evidence <ArrowUpRight size={13} /></button>)}</div> : <span className="ev-no-source"><Info size={14} />No linked source was recorded for this explanation.</span>}
  </article>;
}

function conciseLeadFinding(item: Experiment["hypotheses"][number] | undefined, mode: Experiment["mode"], synthetic?: boolean) {
  if (!item) return "No finding has been recorded for this run yet. Open the agent report for the source trail.";
  const isSyntheticExample = synthetic === true || (synthetic === undefined && mode === "demo");
  if (!isSyntheticExample) return item.finding;
  const title = item.title.toLowerCase();
  if (item.id === "hyp_01" || title.includes("falling volatility")) return "The example was stronger when price swings eased. A pattern to test, not proof.";
  if (item.id === "hyp_02" || title.includes("rising volatility")) return "The example was weaker in these conditions, but it does not prove why the losses happened.";
  if (item.id === "hyp_03" || title.includes("news caused")) return "No dated news records were available in this run, so that explanation was rejected.";
  return item.finding;
}

function nativeLeadCopy(experiment: Experiment) {
  const report = experiment.native_report;
  if (!report) return null;
  const nativeFinding = report.diagnostic.hypotheses.find(item => item.confidence === "high" && item.direction === "works_worse") ?? report.diagnostic.hypotheses[0];
  if (!nativeFinding) return null;
  const conditions = nativeFinding.conditions || [];
  const lowVolatility = conditions.includes("vol_regime=low");
  const bullTrend = conditions.includes("trend_regime=bull");
  const sidewaysTrend = conditions.includes("trend_regime=sideways");
  const weak = nativeFinding.direction === "works_worse";
  if (report.strategy_id === "btc-meanrev-48-demo" && lowVolatility && weak) {
    return {
      title: "Calm markets were a weak spot.",
      body: "Small price swings were a weak spot in the training data. That pattern is a reason to test a filter, not proof it will work.",
    };
  }
  if (report.strategy_id === "btc-trend-24-72-demo" && bullTrend && !weak) {
    return {
      title: "Bull markets were a brighter spot.",
      body: "The recorded training data was stronger when the trend was bullish. That is a lead to test, not proof it will persist.",
    };
  }
  if (report.strategy_id === "btc-trend-24-72-demo" && sidewaysTrend && weak) {
    return {
      title: "Sideways markets were harder.",
      body: "The recorded training data was weaker when the trend was sideways. That is a guardrail to test, not proof it will work.",
    };
  }
  const condition = conditions[0]?.split("=")[1]?.replace(/[_-]+/g, " ") || "this recorded condition";
  const phrase = condition === "low" ? "Calmer markets" : condition === "high" ? "More volatile markets" : condition.charAt(0).toUpperCase() + condition.slice(1);
  return {
    title: `${phrase} looked ${weak ? "weaker" : "stronger"}.`,
    body: `The report found a ${weak ? "weaker" : "stronger"} pattern in this condition in the recorded training data. That is a reason to test it, not proof it will work.`,
  };
}

function ResearchPath({ experiment, onEvidence }: { experiment: Experiment; onEvidence: (id: string) => void }) {
  return <details className="ev-path" aria-labelledby="ev-path-title"><summary><span><span className="ev-kicker">FULL RESEARCH LOG</span><strong id="ev-path-title">Open the detailed record</strong></span><ChevronDown size={16} /></summary><p className="ev-path-note">The trail above highlights the key checks. This log keeps every recorded action and source link available.</p><ol className="ev-path-list">{experiment.steps.map(step => <li key={step.id} className={`ev-path-step ev-step-${step.status}`}><div className="ev-path-marker" aria-hidden="true" /><div className="ev-path-copy"><div className="ev-path-meta"><span>{humanRole(step.role)}</span><span>{statusCopy[step.status]}</span><span>{humanRole(step.tool)}</span></div><h3>{step.title}</h3><p>{humanAction(step.action)}</p>{step.body?.trim() && step.body.trim().toLowerCase() !== step.action.trim().toLowerCase() && <p className="ev-path-context">{step.body}</p>}{step.evidence_ids.length > 0 && <div className="ev-links">{step.evidence_ids.map(id => <button key={id} type="button" onClick={() => onEvidence(id)}><FileSearch size={14} />Open evidence <ArrowUpRight size={13} /></button>)}</div>}</div></li>)}</ol></details>;
}

export default function EvidenceView({ experiment, strategy, onEvidence, onCompare }: EvidenceViewProps) {
  const [showTechnical, setShowTechnical] = useState(false);
  const [showTeamReport, setShowTeamReport] = useState(false);
  const reportLinkRef = useRef<HTMLButtonElement>(null);
  const openReport = () => { setShowTeamReport(true); window.scrollTo({ top: 0, behavior: "instant" }); };
  const closeReport = () => { setShowTeamReport(false); requestAnimationFrame(() => reportLinkRef.current?.focus()); };
  const openEvidence = (id: string) => onEvidence(id);
  const leadFinding = experiment.hypotheses.find(item => item.status === "supported") ?? experiment.hypotheses.find(item => item.status === "inconclusive") ?? experiment.hypotheses[0];
  const leadPose = leadFinding?.status === "supported" ? "bull-acknowledge" : "bear-pause";
  const nativeLead = nativeLeadCopy(experiment);
  const leadTitle = nativeLead?.title ?? (leadFinding?.status === "supported" ? "A pattern worth testing." : leadFinding?.status === "rejected" ? "One explanation was rejected." : "The evidence is still mixed.");
  const traceSteps = experiment.native_report ? buildNativeTraceSteps(experiment.native_report) : experiment.steps;
  if (showTeamReport) return <section className="ev-view ev-team-view" aria-label="Detailed agent report"><TeamResearch initialExperimentId={experiment.experiment_id} strategyId={strategy.strategy_id} frozenEvaluation={experiment.frozen_evaluation} onBack={closeReport} /></section>;
  return <section className="ev-view" aria-labelledby="ev-title">
    <header className="ev-header"><div><span className="ev-kicker">3 · AGENT TRAIL</span><h1 id="ev-title"><KineticText trigger="mount">Evidence behind the call.</KineticText></h1><p>{strategy.name} · every claim stays linked to the recorded work.</p></div><div className="ev-header-actions"><button type="button" className="ev-action kk-primary-button" onClick={onCompare}>Compare the rule <ArrowUpRight size={15} /></button></div></header>
    <section className="ev-agent-story" aria-label="Recorded agent work and finding">
      <div className="ev-agent-trace"><ResearchTrace steps={traceSteps} mode={experiment.mode} synthetic={experiment.synthetic} onEvidence={openEvidence} /><button type="button" ref={reportLinkRef} className="ev-detail-link" onClick={openReport}>Open detailed report <ArrowUpRight size={15} /></button></div>
      <div className="ev-leading-note" data-guide-target="evidence-finding"><MascotCallout pose={leadPose} title={leadTitle} className="ev-scene-callout">{nativeLead?.body ?? conciseLeadFinding(leadFinding, experiment.mode, experiment.synthetic)}</MascotCallout></div>
    </section>
    <section className="ev-findings" aria-labelledby="ev-findings-title"><div className="ev-section-head"><div><span className="ev-kicker">STRUCTURED FINDINGS</span><h2 id="ev-findings-title"><KineticText trigger="scroll">What the research can say</KineticText></h2><p>Every statement keeps its status and its source.</p></div></div><div className="ev-hypothesis-list">{experiment.hypotheses.map(item => <Hypothesis key={item.id} item={item} onEvidence={openEvidence} />)}</div></section>
    {experiment.steps.length > 0 && <ResearchPath experiment={experiment} onEvidence={openEvidence} />}
    <section className="ev-library" aria-labelledby="ev-library-title"><div className="ev-section-head"><div><span className="ev-kicker">EVIDENCE LIBRARY</span><h2 id="ev-library-title">Recorded sources</h2><p>Open a source for its arguments and raw output. Technical details stay here when you need them.</p></div><span className="ev-count">{experiment.evidence.length}</span></div><div className="ev-source-list">{experiment.evidence.map(item => <details className="ev-source-row" key={item.id}><summary><span><FileSearch size={15} /><strong>{item.title}</strong><small>{item.kind} · {researchStageLabel(item.window)}</small></span><ChevronDown size={16} /></summary><div className="ev-source-summary"><p>{item.summary}</p><button type="button" className="ev-action" onClick={() => openEvidence(item.id)}>Open source detail <ExternalLink size={14} /></button></div></details>)}</div></section>
    <section className="ev-technical"><button type="button" onClick={() => setShowTechnical(current => !current)} aria-expanded={showTechnical}><span><Info size={15} />Technical report details</span><ChevronDown size={15} /></button>{showTechnical && <div className="ev-technical-body"><p>Experiment <code>{experiment.experiment_id}</code> · policy <code>{experiment.policy_id}</code></p><p>Dataset <code>{experiment.dataset_hash}</code></p><p>{experiment.limitations.join(" ")}</p></div>}</section>
  </section>;
}
