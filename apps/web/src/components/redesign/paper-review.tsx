"use client";

import { useRef, useState } from "react";
import { ArrowLeft, Check, CircleHelp, FileText, Loader2, LockKeyhole, ShieldCheck, TriangleAlert } from "lucide-react";
import { API_ROUTES } from "../../../../../packages/contracts/api";
import type { Experiment, PaperPlan, Strategy } from "./types";
import { api } from "../../lib/api";
import { canReviewPlan } from "./decision";
import KineticText from "./kinetic-text";
import { MascotCallout } from "./mascot";
import "./paper-review.css";

const money = (value: number | null | undefined) => value == null || !Number.isFinite(value)
  ? "Not recorded"
  : value.toLocaleString("en-GB", { maximumFractionDigits: 2 });
const isNativeReportSource = (source?: string) => source === "native_report" || source === "native_report_example";

export default function PaperReview({ experiment, strategy, onSaved, onBack }: { experiment: Experiment; strategy: Strategy; onSaved: (plan: PaperPlan) => void; onBack: () => void }) {
  const [approved, setApproved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const submitRef = useRef(false);
  const nativeReport = isNativeReportSource(strategy.source) || isNativeReportSource(experiment.source);
  const reportNotEligible = nativeReport || experiment.paper_eligible === false;
  const publishedKill = reportNotEligible && experiment.verdict === "KILL";
  const eligible = !reportNotEligible && canReviewPlan(experiment);
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
    <header className="pr-heading" data-guide-target="review-conclusion"><span className="pr-kicker">{reportNotEligible ? "READ-ONLY REPORT · NO PAPER PLAN" : "PROPOSAL · HUMAN APPROVAL"}</span><h1 id="pr-title"><KineticText trigger="mount">{reportNotEligible ? "Approval stays locked." : "Review the plan."}</KineticText></h1><p>{reportNotEligible ? "The proposed rule needs an eligible decision before a paper plan can be saved." : "Proposed 14-day comparison of original and filtered rules."}</p></header>
    {!reportNotEligible && example && <div className="pr-notice"><TriangleAlert size={17} /><p><strong>Illustrative example.</strong> Measure the rule before using it.</p></div>}
    {!eligible && !example && !reportNotEligible && <div className="pr-notice"><CircleHelp size={17} /><p><strong>Not ready yet.</strong> Finish the new-data test first.</p></div>}
    <MascotCallout pose={eligible ? "bear-folded-arms" : "bear-chin-rest"} title={reportNotEligible ? "Evidence before approval." : eligible ? "Review before you save." : "Finish the new-data check."} className="pr-mascot-callout">
      {reportNotEligible ? (experiment.frozen_evaluation ? "A smaller loss is still a loss. This filter needs a new decision before a paper plan." : "No proposed rule earned the next test. Keep researching before planning a paper test.") : eligible ? "Human approval keeps this proposal paper-only; saving does not start a test." : "The save action stays locked until the new-data test is complete."}
    </MascotCallout>
    <div className="pr-document">
      <section className="pr-section"><div className="pr-section-label">STRATEGY</div><h2>{strategy.name}</h2><p className="pr-meta">{strategy.symbol} · {strategy.timeframe} · {strategy.status === "demo" ? "Example strategy" : strategy.strategy_version}</p></section>
      <section className="pr-section"><div className="pr-section-label">{reportNotEligible ? "PUBLISHED REPORT" : "THE RULE TO TEST"}</div><h2>{reportNotEligible ? "No paper proposal is available." : "Original strategy and suggested rule"}</h2><p>{reportNotEligible ? publishedKill ? "The published KILL verdict is for the always-on strategy. The sealed look is evidence, not a new arbiter review." : "The published verdict stays read-only. This screen does not create a new arbiter review." : experiment.policy.description}</p>{!reportNotEligible && experiment.policy.conditions.length > 0 && <ul className="pr-rule-list">{experiment.policy.conditions.map(condition => <li key={condition}><Check size={15} />{condition}</li>)}</ul>}{!reportNotEligible && <p className="pr-muted">Original unchanged; suggested rule affects activation or allocation only.</p>}</section>
      {reportNotEligible ? <section className="pr-section"><div className="pr-section-label">APPROVAL STATUS</div><h2>Paper plan unavailable.</h2><p>This proposal has no approved candidate verdict. No paper test has been saved or started for it.</p></section> : <section className="pr-section"><div className="pr-section-label">TEST SETUP</div><dl className="pr-facts"><div><dt>Duration</dt><dd>14 days</dd></div><div><dt>Execution</dt><dd>Simulated trades only</dd></div><div><dt>Strategy timezone</dt><dd>{strategy.assumptions.timezone}</dd></div><div><dt>Trading fee</dt><dd>{money(strategy.assumptions.fee_bps)} bps</dd></div><div><dt>Slippage assumption</dt><dd>{money(strategy.assumptions.slippage_bps)} bps</dd></div><div><dt>Fill assumption</dt><dd>{strategy.assumptions.execution}</dd></div></dl></section>}
      <section className="pr-section"><div className="pr-section-label">WHAT THIS RECORDS</div><p>{reportNotEligible ? "Published report, evidence and limitations. Read-only: no new test, order or observation." : "Frozen strategy, rule, dataset, costs and experiment. Planned only: no brokerage, orders or observations."}</p><details className="pr-details"><summary><FileText size={15} />Show research identifiers</summary><dl className="pr-identifiers"><div><dt>Experiment</dt><dd>{experiment.experiment_id}</dd></div><div><dt>Policy</dt><dd>{experiment.policy_id}</dd></div><div><dt>Dataset</dt><dd title={experiment.dataset_hash}>{experiment.dataset_hash}</dd></div></dl></details></section>
    </div>
    <section className="pr-approval" data-guide-target="review-approval"><div><ShieldCheck size={19} /><div><strong>{reportNotEligible ? "Approval unavailable." : "Human approval is required."}</strong><p>{reportNotEligible ? "A new candidate decision is required before approval." : "Approve this proposal only after reviewing the assumptions."}</p></div></div><label><input type="checkbox" checked={approved} onChange={event => setApproved(event.target.checked)} disabled={saving || !eligible} /><span>{reportNotEligible ? "I understand this report cannot be approved as a paper plan." : "I have reviewed the proposed rule, costs and limitations."}</span></label>{error && <p className="pr-error" role="alert">{error}</p>}<div className="pr-actions"><button className="pr-secondary" type="button" onClick={onBack} disabled={saving}>Keep reviewing</button><button className="pr-primary kk-primary-button" type="button" onClick={() => void save()} disabled={!approved || saving || !eligible}>{saving ? <Loader2 size={16} className="pr-spin" /> : <LockKeyhole size={16} />}{saving ? "Saving plan…" : reportNotEligible ? "Paper plan unavailable" : "Freeze rules and save plan"}</button></div><p className="pr-footnote">{reportNotEligible ? "Read-only report · no paper test · no live orders" : "Planned only · not running · no live orders"}</p></section>
    <a className="pr-download" href={API_ROUTES.experimentReport(experiment.experiment_id)} download><FileText size={14} />Download the research record</a>
  </section>;
}
