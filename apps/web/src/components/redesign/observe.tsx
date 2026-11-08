"use client";

import { FileText, FlaskConical, LockKeyhole, Plus, ShieldCheck } from "lucide-react";
import type { PaperPlan, Strategy } from "./types";
import "./observe.css";

export default function ObserveView({ plans, strategies, onReview }: { plans: PaperPlan[]; strategies: Strategy[]; onReview: () => void }) {
  const strategyFor = (plan: PaperPlan) => {
    const strategyId = plan.snapshot?.strategy_id;
    return strategyId ? strategies.find(item => item.strategy_id === strategyId) : undefined;
  };
  return <section className="ob-page" aria-labelledby="ob-title">
    <header className="ob-heading"><span className="ob-kicker">PAPER TESTS</span><h1 id="ob-title">Your paper plans.</h1></header>
    {plans.length === 0 ? <section className="ob-empty"><span className="ob-empty-mark"><FlaskConical size={24} /></span><h2>Your first paper test starts with a plan.</h2><p>Review a result and freeze its rules.</p><button className="ob-action kk-primary-button" type="button" onClick={onReview}><Plus size={16} />Review a paper plan</button></section> : <>
      <div className="ob-status"><ShieldCheck size={17} /><p><strong>Saved. The shadow log waits for the next hourly bar.</strong></p></div>
      <section className="ob-list" aria-label="Saved paper plans"><div className="ob-list-head"><span>Saved plans</span><span>{plans.length} {plans.length === 1 ? "plan" : "plans"}</span></div>{plans.map(plan => {
        const strategy = strategyFor(plan);
        const snapshot = plan.snapshot;
        const policy = snapshot?.policy;
        const assumptions = snapshot?.assumptions;
        const conditions = policy?.conditions ?? [];
        return <article className="ob-plan" key={plan.paper_test_id}>
          <div className="ob-plan-main"><h2>{strategy?.name || (snapshot ? "Frozen strategy" : "Saved plan")}</h2><p>{strategy?.symbol || (snapshot?.strategy_id ? `Strategy ${snapshot.strategy_id}` : "Frozen strategy identity unavailable")} · {plan.mode === "demo" ? "Illustrative example" : "Measured plan"}</p></div>
          <dl className="ob-plan-facts"><div><dt>Rules</dt><dd>Frozen</dd></div><div><dt>Duration</dt><dd>{plan.duration_days} days</dd></div><div><dt>Approved</dt><dd>{new Date(plan.approved_at).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: "UTC" })}</dd></div><div><dt>Status</dt><dd>{plan.shadow ? `${plan.shadow.fills_recorded} of ${plan.shadow.horizon_bars} hours logged` : "Waiting for the next hour"}</dd></div></dl>
          {plan.shadow?.message ? <p className="ob-snapshot-muted">{plan.shadow.message}</p> : null}
          <details className="ob-plan-detail"><summary><FileText size={14} />Show frozen plan</summary><div className="ob-plan-detail-body">
            <p>Plan <code>{plan.paper_test_id}</code> · Experiment <code>{plan.experiment_id}</code> · Policy <code>{plan.policy_id}</code></p>
            {snapshot ? <>
              <dl className="ob-snapshot-grid"><div><dt>Strategy ID</dt><dd><code>{snapshot.strategy_id}</code></dd></div><div><dt>Dataset</dt><dd><code>{snapshot.dataset_hash}</code></dd></div><div><dt>Frozen policy</dt><dd><code>{snapshot.policy_id}</code></dd></div><div><dt>Train window</dt><dd>{snapshot.windows.train}</dd></div><div><dt>Validation window</dt><dd>{snapshot.windows.validation}</dd></div><div><dt>Test window</dt><dd>{snapshot.windows.test}</dd></div></dl>
              <section className="ob-snapshot-section"><h3>Saved rules</h3><p>{policy?.description || "No rule description was recorded."}</p>{conditions.length > 0 ? <ul className="ob-snapshot-conditions">{conditions.map(condition => <li key={condition}>{condition}</li>)}</ul> : <p className="ob-snapshot-muted">No additional conditions were recorded.</p>}</section>
              <section className="ob-snapshot-section"><h3>Saved cost assumptions</h3><dl className="ob-assumption-grid"><div><dt>Timezone</dt><dd>{assumptions?.timezone || "Not recorded"}</dd></div><div><dt>Fees</dt><dd>{assumptions?.fee_bps == null ? "Not recorded" : `${assumptions.fee_bps} bps`}</dd></div><div><dt>Slippage</dt><dd>{assumptions?.slippage_bps == null ? "Not recorded" : `${assumptions.slippage_bps} bps`}</dd></div><div><dt>Execution</dt><dd>{assumptions?.execution || "Not recorded"}</dd></div></dl>{assumptions?.description ? <p className="ob-snapshot-muted">{assumptions.description}</p> : null}</section>
            </> : <p className="ob-snapshot-muted">This older saved plan does not include its frozen snapshot. Current strategy assumptions are not substituted.</p>}
          </div></details>
        </article>;
      })}</section>
    </>}
    <footer className="ob-footer"><LockKeyhole size={14} /> No brokerage connection · paper only · rules stay frozen</footer>
  </section>;
}
