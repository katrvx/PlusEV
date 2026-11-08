"use client";

import { useRef, useState } from "react";
import { ArrowLeft, Check, CircleHelp, FileText, Loader2, LockKeyhole, ShieldCheck, TriangleAlert } from "lucide-react";
import { API_ROUTES } from "../../../../../packages/contracts/api";
import type { Experiment, PaperPlan, Strategy } from "./types";
import { api } from "../../lib/api";
import "./paper-review.css";

const money = (value: number) => value.toLocaleString("en-GB", { maximumFractionDigits: 2 });

export default function PaperReview({ experiment, strategy, onSaved, onBack }: { experiment: Experiment; strategy: Strategy; onSaved: (plan: PaperPlan) => void; onBack: () => void }) {
  const [approved, setApproved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const submitRef = useRef(false);
  const eligible = experiment.status === "completed" && experiment.policy.holdout_frozen && experiment.policy.test_evaluated;
  const example = experiment.mode === "demo";
  async function save() {
    if (!approved || saving || submitRef.current || !eligible) return;
    submitRef.current = true; setSaving(true); setError("");
    try { onSaved(await api.freezePaperPlan(experiment.experiment_id)); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "The plan could not be saved. Your settings are unchanged."); submitRef.current = false; }
    finally { setSaving(false); }
  }
  return <section className="pr-page" aria-labelledby="pr-title">
    <button className="pr-back" type="button" onClick={onBack}><ArrowLeft size={16} />Back to comparison</button>
    <header className="pr-heading"><span className="pr-kicker">COMPARE WITHOUT LIVE TRADES</span><h1 id="pr-title">Review the paper test.</h1><p>Original and filtered rules, side by side, for 14 days.</p></header>
    {example && <div className="pr-notice"><TriangleAlert size={17} /><p><strong>Illustrative example.</strong> Measure the rule before using it.</p></div>}
    {!eligible && !example && <div className="pr-notice"><CircleHelp size={17} /><p><strong>Not ready yet.</strong> Finish the new-data test first.</p></div>}
    <div className="pr-document">
      <section className="pr-section"><div className="pr-section-label">STRATEGY</div><h2>{strategy.name}</h2><p className="pr-meta">{strategy.symbol} · {strategy.timeframe} · {strategy.status === "demo" ? "Example strategy" : strategy.strategy_version}</p></section>
      <section className="pr-section"><div className="pr-section-label">THE RULE TO TEST</div><h2>Original strategy and suggested rule</h2><p>{experiment.policy.description}</p>{experiment.policy.conditions.length > 0 && <ul className="pr-rule-list">{experiment.policy.conditions.map(condition => <li key={condition}><Check size={15} />{condition}</li>)}</ul>}<p className="pr-muted">Original unchanged; suggested rule affects activation or allocation only.</p></section>
      <section className="pr-section"><div className="pr-section-label">TEST SETUP</div><dl className="pr-facts"><div><dt>Duration</dt><dd>14 days</dd></div><div><dt>Execution</dt><dd>Simulated trades only</dd></div><div><dt>Strategy timezone</dt><dd>{strategy.assumptions.timezone}</dd></div><div><dt>Trading fee</dt><dd>{money(strategy.assumptions.fee_bps)} bps</dd></div><div><dt>Slippage assumption</dt><dd>{money(strategy.assumptions.slippage_bps)} bps</dd></div><div><dt>Fill assumption</dt><dd>{strategy.assumptions.execution}</dd></div></dl></section>
      <section className="pr-section"><div className="pr-section-label">WHAT THIS RECORDS</div><p>Frozen strategy, rule, dataset, costs and experiment. Planned only: no brokerage, orders or observations.</p><details className="pr-details"><summary><FileText size={15} />Show research identifiers</summary><dl className="pr-identifiers"><div><dt>Experiment</dt><dd>{experiment.experiment_id}</dd></div><div><dt>Policy</dt><dd>{experiment.policy_id}</dd></div><div><dt>Dataset</dt><dd title={experiment.dataset_hash}>{experiment.dataset_hash}</dd></div></dl></details></section>
    </div>
    <section className="pr-approval"><div><ShieldCheck size={19} /><div><strong>Your approval is required.</strong><p>Review the assumptions before saving.</p></div></div><label><input type="checkbox" checked={approved} onChange={event => setApproved(event.target.checked)} disabled={saving || !eligible} /><span>I have reviewed the rule, costs and limitations.</span></label>{error && <p className="pr-error" role="alert">{error}</p>}<div className="pr-actions"><button className="pr-secondary" type="button" onClick={onBack} disabled={saving}>Keep reviewing</button><button className="pr-primary kk-primary-button" type="button" onClick={() => void save()} disabled={!approved || saving || !eligible}>{saving ? <Loader2 size={16} className="pr-spin" /> : <LockKeyhole size={16} />}{saving ? "Saving plan…" : "Freeze rules and save plan"}</button></div><p className="pr-footnote">Planned only · not running · no live orders</p></section>
    <a className="pr-download" href={API_ROUTES.experimentReport(experiment.experiment_id)} download><FileText size={14} />Download the research record</a>
  </section>;
}
