"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, ChevronDown, ExternalLink, FileSearch, Info, X } from "lucide-react";
import type { Evidence, Experiment, Strategy } from "./types";
import TeamResearch from "../team-research";
import "./evidence.css";

export type EvidenceViewProps = {
  experiment: Experiment;
  strategy: Strategy;
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
  onEvidence: (id: string) => void;
  onCompare: () => void;
};

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
    <div className="ev-dialog-body"><h2 id="ev-dialog-title">{evidence.title}</h2><p>{evidence.summary}</p><dl className="ev-facts">{evidence.facts.map(fact => <div key={fact.label}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}</dl><div className="ev-source"><span>Source</span><strong>{evidence.source}</strong><span>Window</span><strong>{evidence.window}</strong></div></div>
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

function ResearchPath({ experiment, onEvidence }: { experiment: Experiment; onEvidence: (id: string) => void }) {
  return <details className="ev-path" aria-labelledby="ev-path-title"><summary><span><span className="ev-kicker">RESEARCH PATH</span><strong id="ev-path-title">Show the checks behind this report</strong></span><ChevronDown size={16} /></summary><p className="ev-path-note">A compact record of the work performed, not hidden reasoning.</p><ol className="ev-path-list">{experiment.steps.map(step => <li key={step.id} className={`ev-path-step ev-step-${step.status}`}><div className="ev-path-marker" aria-hidden="true" /><div className="ev-path-copy"><div className="ev-path-meta"><span>{step.role}</span><span>{step.status}</span><span>{step.tool}</span></div><h3>{step.title}</h3><p>{step.action}</p>{step.evidence_ids.length > 0 && <div className="ev-links">{step.evidence_ids.map(id => <button key={id} type="button" onClick={() => onEvidence(id)}><FileSearch size={14} />Open evidence <ArrowUpRight size={13} /></button>)}</div>}</div></li>)}</ol></details>;
}

export default function EvidenceView({ experiment, strategy, onEvidence, onCompare }: EvidenceViewProps) {
  const [showTechnical, setShowTechnical] = useState(false);
  const [showTeamReport, setShowTeamReport] = useState(false);
  const openEvidence = (id: string) => onEvidence(id);
  if (showTeamReport) return <section className="ev-view ev-team-view" aria-labelledby="ev-team-title"><div className="ev-team-head"><div><span className="ev-kicker">NATIVE AGENT REPORT</span><h1 id="ev-team-title">The report behind this evidence</h1><p>Open the recorded agent report, with its research mode, source trail, trials and comparison rules intact.</p></div></div><TeamResearch initialExperimentId={experiment.experiment_id} strategyId={strategy.strategy_id} onBack={() => setShowTeamReport(false)} /></section>;
  return <section className="ev-view" aria-labelledby="ev-title">
    <header className="ev-header"><div><span className="ev-kicker">EXPLORE · EVIDENCE</span><h1 id="ev-title">Why did the result change?</h1><p>{strategy.name}</p></div><div className="ev-header-actions"><button type="button" className="ev-action" onClick={() => setShowTeamReport(true)}>Open agent report <ArrowUpRight size={15} /></button><button type="button" className="ev-action kk-primary-button" onClick={onCompare}>Compare the rule <ArrowUpRight size={15} /></button></div></header>
    <section className="ev-findings" aria-labelledby="ev-findings-title"><div className="ev-section-head"><div><span className="ev-kicker">STRUCTURED FINDINGS</span><h2 id="ev-findings-title">What the research can say</h2><p>Every statement keeps its status and its source.</p></div></div><div className="ev-hypothesis-list">{experiment.hypotheses.map(item => <Hypothesis key={item.id} item={item} onEvidence={openEvidence} />)}</div></section>
    {experiment.steps.length > 0 && <ResearchPath experiment={experiment} onEvidence={openEvidence} />}
    <section className="ev-library" aria-labelledby="ev-library-title"><div className="ev-section-head"><div><span className="ev-kicker">EVIDENCE LIBRARY</span><h2 id="ev-library-title">Recorded sources</h2><p>Open a source for its arguments and raw output. Technical details stay here when you need them.</p></div><span className="ev-count">{experiment.evidence.length}</span></div><div className="ev-source-list">{experiment.evidence.map(item => <details className="ev-source-row" key={item.id}><summary><span><FileSearch size={15} /><strong>{item.title}</strong><small>{item.kind} · {item.window}</small></span><ChevronDown size={16} /></summary><div className="ev-source-summary"><p>{item.summary}</p><button type="button" className="ev-action" onClick={() => openEvidence(item.id)}>Open source detail <ExternalLink size={14} /></button></div></details>)}</div></section>
    <section className="ev-technical"><button type="button" onClick={() => setShowTechnical(current => !current)} aria-expanded={showTechnical}><span><Info size={15} />Technical report details</span><ChevronDown size={15} /></button>{showTechnical && <div className="ev-technical-body"><p>Experiment <code>{experiment.experiment_id}</code> · policy <code>{experiment.policy_id}</code></p><p>Dataset <code>{experiment.dataset_hash}</code></p><p>{experiment.limitations.join(" ")}</p></div>}</section>
  </section>;
}
