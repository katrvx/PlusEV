"use client";

import { API_ROUTES } from "../../../../packages/contracts/api";

import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, ArrowDownToLine, ArrowRight, ArrowUpRight, Beaker, BookOpen, Check, CheckCheck, ChevronDown, ChevronRight, CircleHelp, Clock3, Database, FileCheck2, FileInput, FileText, FlaskConical, GitBranch, Layers3, Loader2, LockKeyhole, Menu, Plus, Search, Settings2, ShieldCheck, Sparkles, SquareArrowOutUpRight, Target, TriangleAlert, X } from "lucide-react";
import type { Evidence, Experiment, Health, Metric, PaperPlan, Strategy } from "../../../../packages/contracts/types";
import { api } from "@/lib/api";
import EquityChart from "./equity-chart";
import ImportWizard from "./import-wizard";
import TeamResearch from "./team-research";
import ResearchOverview from "./research-overview";
import GettingStarted from "./getting-started";

type Page = "research" | "strategies" | "papers" | "guide" | "team";
type Tab = "overview" | "investigation" | "comparison" | "decision";
const tabs: { id: Tab; label: string }[] = [{ id: "overview", label: "Overview" }, { id: "investigation", label: "What agents found" }, { id: "comparison", label: "Compare results" }, { id: "decision", label: "Next steps" }];
const number = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 });
const pct = (value: number) => `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
const date = (value: string) => new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const errorMessage = (value: unknown) => value instanceof Error ? value.message : "Something went wrong. Please retry.";
const verdictLabel = (verdict: Experiment["verdict"]) => verdict === "CONDITIONAL" || verdict === "MODIFY" ? "Activate conditionally" : verdict === "REDUCE" || verdict === "RESTRICT" ? "Reduce" : verdict === "COMBINE" ? "Combine" : verdict === "MONITOR" ? "Monitor" : verdict === "INCONCLUSIVE" ? "Not proven" : verdict === "KEEP" ? "Keep" : verdict === "KILL" ? "Kill" : verdict;

function Modal({ title, children, onClose, wide = false }: { title: string; children: React.ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current; dialog?.showModal(); return () => dialog?.close(); }, []);
  return <dialog ref={ref} className={`modal ${wide ? "wide" : ""}`} onCancel={onClose} onClick={event => { if (event.target === event.currentTarget) onClose(); }} aria-label={title}>
    <div className="modal-head"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={20} /></button></div>{children}
  </dialog>;
}

function EvidenceModal({ evidence, onClose }: { evidence: Evidence; onClose: () => void }) {
  return <Modal title="Research evidence" onClose={onClose}>
    <div className="modal-body"><span className="eyebrow">{evidence.kind} / {evidence.id}</span><h3>{evidence.title}</h3><p>{evidence.summary}</p>
      <dl className="evidence-facts">{evidence.facts.map((fact, index) => <div key={index}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}</dl>
      <div className="source-note"><Database size={16} /><div><strong>{evidence.source}</strong><span>{evidence.window}</span></div></div>
    </div>
  </Modal>;
}

function MetricCard({ metric }: { metric: Metric }) {
  return <article className="metric-card"><span>{metric.label}</span><strong className={metric.value !== null && metric.value < 0 ? "negative" : ""}>{metric.value === null ? "—" : metric.format === "percent" ? pct(metric.value) : metric.format === "integer" ? Math.round(metric.value).toLocaleString("en-GB") : number.format(metric.value)}</strong><p>{metric.description}</p></article>;
}

function Legend() { return <div className="chart-legend"><span><i style={{ background: "#635bdf" }} />Suggested rule</span><span><i style={{ background: "#67a6b0" }} />Simple rule</span><span><i style={{ background: "#929aaa" }} />Original strategy</span><span><i style={{ background: "#c7cad3" }} />Cash</span></div>; }

function Investigation({ experiment, onEvidence }: { experiment: Experiment; onEvidence: (id: string) => void }) {
  return <div className="investigation-grid tab-content"><section className="panel"><div className="panel-heading"><div><h2>An investigation you can follow</h2><p>See what was checked, what was challenged, and why each finding matters.</p></div><span className="subtle-badge">{experiment.steps.length} research steps</span></div><div className="research-timeline">{experiment.steps.map((step, index) => <article className={`research-step ${step.status}`} key={step.id}><span className="step-marker">{step.status === "rejected" ? <X size={15} /> : step.status === "running" ? <Loader2 className="spin" size={15} /> : <Check size={15} />}</span><div className="step-content"><div className="step-meta"><span>{step.role}</span><small>{String(index + 1).padStart(2, "0")} / {step.action}</small></div><h3>{step.title}</h3><p>{step.body}</p><div className="step-tools"><details className="technical-detail"><summary>Technical detail</summary><code>{step.tool}()</code></details>{step.evidence_ids.map(id => <button key={id} className="evidence-link" onClick={() => onEvidence(id)}><FileText size={12} />View evidence<ArrowUpRight size={11} /></button>)}</div>{step.status === "rejected" && <span className="rejected-label">Rejected after testing</span>}</div></article>)}</div></section><aside className="investigation-aside"><section className="panel"><div className="panel-heading"><div><h2>The research question</h2><p>Your strategy, examined from different angles</p></div><Target size={19} className="purple" /></div><div className="panel-body"><blockquote>When does this strategy work well — and when should it sit out?</blockquote><p>Research agents look for patterns. A critic challenges their explanations. Tests check whether a proposed trading rule holds up.</p><ul className="check-list"><li><CheckCheck size={16} />Underlying strategy stays unchanged</li><li><CheckCheck size={16} />Every explanation links to evidence</li><li><CheckCheck size={16} />A critic looks for weak reasoning</li><li><CheckCheck size={16} />Trading rules are fixed before the final test</li></ul></div></section><section className="panel"><div className="panel-heading"><h2>Evidence library</h2><span className="count-badge">{experiment.evidence.length}</span></div><div className="evidence-library">{experiment.evidence.map(evidence => <button key={evidence.id} onClick={() => onEvidence(evidence.id)}><FileText size={17} /><div><strong>{evidence.title}</strong><small>{evidence.kind} · {evidence.id}</small></div><ChevronRight size={14} /></button>)}</div></section></aside></div>;
}

function Comparison({ experiment }: { experiment: Experiment }) {
  return <div className="tab-content"><div className="split-strip">{Object.entries(experiment.windows).map(([label, window]) => <div key={label}><span className="eyebrow">{label === "test" ? "New-data test" : label === "train" ? "Explore patterns" : "Check the idea"}</span><strong>{window}</strong></div>)}<div><LockKeyhole size={19} className="purple" /><span>{experiment.policy.holdout_frozen ? "Rule fixed before the final test" : "Rule not yet fixed"}</span></div></div><section className="panel"><div className="panel-heading"><div><h2>Does the research improve the decision?</h2><p>Compare the original strategy with suggested trading rules, using the same dates and trading costs. A value of 100 is the starting balance.</p></div></div><Legend /><EquityChart data={experiment.equity} /><div className="data-table-wrap"><table className="data-table"><caption className="sr-only">After-cost policy comparison</caption><thead><tr><th>Trading rule</th><th>Return after costs</th><th>Sharpe ratio</th><th>Biggest drop</th><th>Exposure</th><th>Turnover</th><th>Trades</th></tr></thead><tbody>{experiment.baselines.map(baseline => <tr key={baseline.id}><td><span className="baseline-name">{baseline.id === "always_on" ? "Original strategy" : baseline.id === "agent_gate" ? "Suggested rule" : baseline.id === "simple_rule" ? "Simple trend rule" : baseline.name}</span></td><td className={baseline.net_return >= 0 ? "green" : "negative"}>{pct(baseline.net_return)}</td><td>{baseline.sharpe == null ? "—" : number.format(baseline.sharpe)}</td><td>{baseline.max_drawdown == null ? "—" : pct(baseline.max_drawdown)}</td><td>{baseline.exposure == null ? "—" : `${(baseline.exposure * 100).toFixed(0)}%`}</td><td>{baseline.turnover == null ? "—" : `${number.format(baseline.turnover)}×`}</td><td>{baseline.trades == null ? "—" : baseline.trades}</td></tr>)}</tbody></table></div><details className="terms-guide"><summary><CircleHelp size={16} />What do these numbers mean?</summary><dl><div><dt>Return after costs</dt><dd>The gain or loss after the assumed trading fees and price differences.</dd></div><div><dt>Sharpe ratio</dt><dd>Return relative to how much it fluctuates. Higher can be better, but a short test is not reliable proof.</dd></div><div><dt>Biggest drop (drawdown)</dt><dd>The largest fall from a previous high during this test.</dd></div><div><dt>Exposure & turnover</dt><dd>Exposure shows how much capital was at risk. Turnover measures how much was traded.</dd></div><div><dt>New-data test</dt><dd>A later period that was kept aside while choosing the rule, so the rule cannot be tailored to these results.</dd></div></dl></details></section><div className="notice"><TriangleAlert size={18} /><div><strong>Read the result in context</strong><p>{experiment.limitations.join(" ")}</p></div></div></div>;
}

function Decision({ experiment, onFreeze }: { experiment: Experiment; onFreeze: () => void }) {
  const canFreeze = experiment.status === "completed" && experiment.policy.holdout_frozen && experiment.policy.test_evaluated;
  return <div className="decision-grid tab-content"><section className="panel decision-main"><div className="eyebrow"><ShieldCheck size={15} />Research decision</div><span className={`verdict-pill ${experiment.verdict.toLowerCase()}`}>{verdictLabel(experiment.verdict)}</span><h2>{experiment.verdict === "CONDITIONAL" || experiment.verdict === "MODIFY" ? "Run it where it holds up." : experiment.verdict === "KILL" ? "Kill it." : experiment.verdict === "KEEP" ? "Keep it." : "Let the evidence set the next step."}</h2><p className="decision-summary">{experiment.mode === "demo" ? "This example shows how a strategy can behave differently across market conditions. Review the suggested rule and its limitations before planning a practice test." : experiment.recommendation}</p><div className="decision-section"><h3>Suggested trading rule</h3><p>{experiment.policy.description}</p><ul className="check-list">{experiment.policy.conditions.map(condition => <li key={condition}><Check size={16} />{condition}</li>)}</ul></div><div className="decision-section"><h3>What we still don’t know</h3><ul className="limitation-list">{experiment.limitations.map(limit => <li key={limit}>{limit}</li>)}</ul></div><details className="decision-section lineage technical-record"><summary>Research record & identifiers</summary><dl><div><dt>Experiment</dt><dd>{experiment.experiment_id}</dd></div><div><dt>Policy</dt><dd>{experiment.policy_id}</dd></div><div><dt>Dataset hash</dt><dd title={experiment.dataset_hash}>{experiment.dataset_hash}</dd></div></dl></details><a className="button secondary" href={API_ROUTES.experimentReport(experiment.experiment_id)} download><ArrowDownToLine size={15} />Download research report</a></section><aside><section className="panel next-step-panel"><div className="next-icon"><FlaskConical size={24} /></div><h2>Try it without risking money.</h2><p>Plan a 14-day simulated comparison of your original strategy and the suggested rule. Keep the rules fixed so the comparison stays fair.</p><div className="plan-detail"><span>Duration</span><strong>14 days</strong></div><div className="plan-detail"><span>Execution</span><strong>Paper only</strong></div><div className="plan-detail"><span>Trading rules</span><strong>Fixed for the test</strong></div><button className="button primary full" onClick={onFreeze} disabled={!canFreeze}><LockKeyhole size={15} />Review practice plan</button><small>Saves your plan. Automatic practice trading is not connected yet.</small>{!canFreeze && <p className="negative">Finish the new-data test before planning a practice run.</p>}</section><div className="quiet-note"><ShieldCheck size={16} /><span>Your approval is required. No brokerage accounts or live orders are involved.</span></div></aside></div>;
}

export default function Workspace() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [plans, setPlans] = useState<PaperPlan[]>([]);
  const [page, setPage] = useState<Page>("research");
  const [tab, setTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);
  const [experimentLoading, setExperimentLoading] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [paperOpen, setPaperOpen] = useState(false);
  const [approved, setApproved] = useState(false);
  const [savingPlan, setSavingPlan] = useState(false);
  const [paperError, setPaperError] = useState("");
  const [query, setQuery] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const selected = strategies.find(strategy => strategy.strategy_id === selectedId);
  const active = experiment?.status === "queued" || experiment?.status === "running";
  const completed = experiment?.status === "completed";
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;

  const initialize = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [items, state, paperPlans] = await Promise.all([api.strategies(), api.health(), api.paperPlans()]);
      setStrategies(items); setHealth(state); setPlans(paperPlans); setSelectedId(current => items.some(item => item.strategy_id === current) ? current : items.find(item => item.strategy_id === localStorage.getItem("kok.selected"))?.strategy_id || items.find(item => item.status !== "demo")?.strategy_id || items.find(item => item.strategy_id.includes("trend"))?.strategy_id || items[0]?.strategy_id || "");
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void initialize(); }, [initialize]);
  useEffect(() => {
    if (!selectedId) return;
    let canceled = false; setExperimentLoading(true); setExperiment(null); setError("");
    api.experiments(selectedId).then(items => { if (!canceled) setExperiment(items[0] || null); }).catch(failure => { if (!canceled) setError(errorMessage(failure)); }).finally(() => { if (!canceled) setExperimentLoading(false); });
    return () => { canceled = true; };
  }, [selectedId]);
  useEffect(() => {
    if (!active || !experiment) return;
    let canceled = false; let inFlight = false;
    const id = experiment.experiment_id;
    const timer = setInterval(async () => {
      if (inFlight) return; inFlight = true;
      try { const latest = await api.experiment(id); if (!canceled) { setExperiment(latest); if (latest.status === "completed") setToast("Investigation complete. Review the findings and evidence."); } }
      catch (failure) { if (!canceled) setError(errorMessage(failure)); }
      finally { inFlight = false; }
    }, 1200);
    return () => { canceled = true; clearInterval(timer); };
  }, [active, experiment?.experiment_id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(""), 5500); return () => clearTimeout(timer); }, [toast]);

  function navigate(next: Page) { setPage(next); setSidebarOpen(false); }
  function choose(strategy: Strategy) { localStorage.setItem("kok.selected", strategy.strategy_id); setSelectedId(strategy.strategy_id); setTab("overview"); navigate("research"); }
  function showEvidence(id: string) { const found = experiment?.evidence.find(item => item.id === id); if (found) setEvidence(found); else setToast("This evidence record is not available in the current run."); }
  async function run() {
    if (!selected || launching || active) return;
    const id = selected.strategy_id; setLaunching(true); setError("");
    try { const result = await api.investigate(id); if (selectedIdRef.current === id) { setExperiment(result); setTab("investigation"); } }
    catch (failure) { setError(errorMessage(failure)); }
    finally { setLaunching(false); }
  }
  async function freeze() {
    if (!experiment || !approved || savingPlan) return;
    setSavingPlan(true); setPaperError("");
    try { const plan = await api.freezePaperPlan(experiment.experiment_id); setPlans(current => [plan, ...current.filter(item => item.paper_test_id !== plan.paper_test_id)]); setPaperOpen(false); setApproved(false); navigate("papers"); setToast("Paper plan recorded. No trading has started."); }
    catch (failure) { setPaperError(errorMessage(failure)); }
    finally { setSavingPlan(false); }
  }
  const filtered = strategies.filter(strategy => `${strategy.name} ${strategy.symbol}`.toLowerCase().includes(query.toLowerCase()));

  return <div className="app-shell">
    <a href="#main" className="skip-link">Skip to workspace</a>
    {sidebarOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
    <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
      <button className="brand" onClick={() => navigate("research")} aria-label="Keep or Kill home"><span className="brand-mark"><Activity size={24} strokeWidth={2.2} /></span><span>keep or kill<span className="brand-sub">RESEARCH WORKSPACE</span></span></button>
      <div className="workspace-label"><span className="workspace-avatar">K</span><span>My workspace<small>Personal research</small></span></div>
      <nav aria-label="Main navigation"><span className="nav-label">WORKSPACE</span><button className={page === "research" ? "active" : ""} onClick={() => navigate("research")}><Layers3 size={18} />Strategy overview</button><button className={page === "team" ? "active" : ""} onClick={() => navigate("team")}><Sparkles size={18} />Agent research</button><button className={page === "strategies" ? "active" : ""} onClick={() => navigate("strategies")}><GitBranch size={18} />Strategy library<span className="nav-count">{strategies.length}</span></button><button className={page === "papers" ? "active" : ""} onClick={() => navigate("papers")}><FlaskConical size={18} />Practice plans{plans.length > 0 && <span className="nav-count">{plans.length}</span>}</button></nav>
      <div className="sidebar-strategies"><div className="nav-label">YOUR STRATEGIES<button onClick={() => setImportOpen(true)} aria-label="Import a strategy"><Plus size={15} /></button></div>{strategies.map(strategy => <button key={strategy.strategy_id} className={`strategy-nav ${selectedId === strategy.strategy_id && page === "research" ? "selected" : ""}`} onClick={() => choose(strategy)}><span className={`strategy-dot ${strategy.status === "demo" ? "demo" : ""}`} /><span>{strategy.name}<small>{strategy.symbol} · {strategy.timeframe}</small></span>{strategy.status === "demo" && <span className="tiny-demo">DEMO</span>}</button>)}<button className="add-strategy" onClick={() => setImportOpen(true)}><Plus size={15} />Import a strategy</button></div>
      <div className="sidebar-bottom"><div className="sidebar-note"><ShieldCheck size={19} /><h3>Understand your edge.</h3><p>See what works. Know what’s uncertain. Test without live trades.</p></div><button className={`help-link ${page === "guide" ? "selected" : ""}`} onClick={() => navigate("guide")}><BookOpen size={17} />How it works<ArrowUpRight size={14} /></button><div className="profile"><span>U</span><div>AgentVerse workspace<small>Research workspace · Paper only</small></div></div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="Open navigation"><Menu size={20} /></button><Layers3 size={15} /><span>Workspace</span><ChevronRight size={13} /><strong>{page === "research" ? "Strategy research" : page === "strategies" ? "Strategy library" : page === "papers" ? "Practice plans" : page === "team" ? "Agent research" : "How it works"}</strong></div><div className="topbar-right"><span className="paper-indicator"><i />No live trading</span><span className="topbar-divider" /><button className="icon-button" aria-label="Read how it works" onClick={() => navigate("guide")}><CircleHelp size={18} /></button><span className="user-avatar">U</span></div></header>
      <main id="main" className="main-content">
        {error && <div className="error-banner" role="alert"><TriangleAlert size={18} /><span>{error}</span><button className="text-button" onClick={() => { if (strategies.length === 0) void initialize(); else if (selectedId) { setError(""); setExperimentLoading(true); api.experiments(selectedId).then(items => setExperiment(items[0] || null)).catch(failure => setError(errorMessage(failure))).finally(() => setExperimentLoading(false)); } }}>Retry</button><button className="icon-button" onClick={() => setError("")} aria-label="Dismiss error"><X size={15} /></button></div>}
        {loading ? <div className="loading-workspace" role="status"><Loader2 size={26} className="spin" /><h2>Opening your research workspace</h2><p>Loading strategies and saved investigations.</p></div> : <>
          {page === "team" && <TeamResearch />}
          {page === "guide" && <GettingStarted onImport={() => setImportOpen(true)} />}
          {page === "strategies" && <><div className="page-heading"><div><span className="eyebrow">YOUR RESEARCH STARTS HERE</span><h1>Strategy library</h1><p>Existing strategies. New questions worth investigating.</p></div><button className="button primary" onClick={() => setImportOpen(true)}><Plus size={16} />Import strategy</button></div><div className="library-toolbar"><label className="search-field"><Search size={17} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Find a strategy or instrument…" aria-label="Search strategies" /></label><span>{filtered.length} strategies</span></div><div className="strategy-cards">{filtered.map(strategy => <button key={strategy.strategy_id} className="panel strategy-card" onClick={() => choose(strategy)}><div className="strategy-card-top"><span className="instrument-icon">{strategy.symbol.startsWith("BTC") ? "₿" : strategy.symbol.slice(0, 1)}</span><span className={`subtle-badge ${strategy.status === "demo" ? "purple" : ""}`}>{strategy.status === "demo" ? "Example strategy" : strategy.kind === "trades" ? "Diagnosis only" : "Imported"}</span></div><h2>{strategy.name}</h2><p>{strategy.symbol} · {strategy.timeframe} · {strategy.source}</p><div className="strategy-card-meta"><span><Database size={13} />{strategy.row_count.toLocaleString("en-GB")} rows</span><span>{strategy.strategy_version}</span></div><div className="strategy-card-bottom"><span>{date(strategy.date_start)} — {date(strategy.date_end)}</span><ArrowUpRight size={16} /></div></button>)}</div>{filtered.length === 0 && <div className="empty-state"><Search size={30} /><h2>{strategies.length ? "No matching strategies" : "Start with a strategy"}</h2><p>{strategies.length ? "Try another name or instrument." : "Import a positions file or trade log to start your research."}</p></div>}</>}
          {page === "papers" && <><div className="page-heading"><div><span className="eyebrow">YOUR NEXT EXPERIMENT</span><h1>Practice plans</h1><p>Test your original strategy and a suggested rule side by side, without real money.</p></div><span className="subtle-badge"><ShieldCheck size={14} />No live orders</span></div><div className="notice"><Clock3 size={18} /><div><strong>Plans are recorded, not running</strong><p>Automatic practice trading is not connected yet. These saved plans have not started collecting results.</p></div></div>{plans.length === 0 ? <div className="empty-state panel"><FlaskConical size={34} /><h2>A considered next step.</h2><p>Start with a strategy’s research, then save a 14-day practice plan. You review the rules before the plan is recorded.</p><button className="button primary" onClick={() => { navigate("research"); setTab("decision"); }}>Review a decision <ArrowRight size={15} /></button></div> : <section className="panel data-table-wrap"><table className="data-table"><thead><tr><th>Paper plan</th><th>Research experiment</th><th>Duration</th><th>Approved</th><th>Status</th></tr></thead><tbody>{plans.map(plan => <tr key={plan.paper_test_id}><td><strong>{plan.paper_test_id}</strong><small>{plan.mode === "demo" ? "Demo policy · illustrative" : "Frozen policy"}</small></td><td>{plan.experiment_id}</td><td>{plan.duration_days} days</td><td>{date(plan.approved_at)}</td><td><span className="subtle-badge">Planned · not started</span></td></tr>)}</tbody></table></section>}</>}
          {page === "research" && (!selected ? <div className="empty-state panel"><FileInput size={34} /><h1>Give your strategy a second look.</h1><p>Import a target-position file to prepare your first investigation.</p><button className="button primary" onClick={() => setImportOpen(true)}><Plus size={16} />Import strategy</button></div> : <>
            <div className="page-heading"><div><span className="eyebrow"><span className="eyebrow-dot" />UNDERSTAND YOUR STRATEGY</span><h1>{selected.name}</h1><div className="strategy-metadata"><span className="ticker">{selected.symbol}</span><span>{selected.timeframe} timeframe</span><span className="metadata-dot">·</span><span>{selected.status === "demo" ? "Example strategy" : selected.strategy_version}</span><span className="metadata-dot">·</span><span>{selected.kind === "positions" ? "Position history" : "Trade history"}</span></div></div><div className="heading-actions">{completed && experiment && <a className="button secondary" href={API_ROUTES.experimentReport(experiment.experiment_id)} download><ArrowDownToLine size={15} />Download report</a>}<button className="button primary" disabled={launching || active || experimentLoading} onClick={() => void run()}>{launching || active ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}{active ? "Investigating…" : selected.status === "demo" ? "Replay example" : "Research my strategy"}</button></div></div>
            {selected.status === "demo" ? <div className="demo-banner"><Beaker size={16} /><span><strong>Explore an example</strong> · These results are illustrative. Your own strategy’s results will appear once the research engine is connected.</span><button onClick={() => setImportOpen(true)}>Bring your strategy <ArrowRight size={14} /></button></div> : <div className="data-banner"><Database size={16} /><span><strong>Imported dataset</strong> · {selected.row_count.toLocaleString("en-GB")} rows · {date(selected.date_start)} – {date(selected.date_end)}{selected.kind === "trades" ? " · Diagnosis only" : ""}</span><span title={selected.dataset_hash}>Version saved</span></div>}
            <div className="research-tabs" role="tablist" aria-label="Research views">{tabs.map(item => <button key={item.id} role="tab" id={`tab-${item.id}`} aria-selected={tab === item.id} aria-controls="research-panel" className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>{item.label}{item.id === "investigation" && !!experiment?.steps.length && <span>{experiment.steps.length}</span>}</button>)}<span className="tab-trailing"><LockKeyhole size={12} />Base strategy unchanged</span></div>
            <div role="tabpanel" id="research-panel" aria-labelledby={`tab-${tab}`}>
              {experimentLoading ? <div className="loading-workspace compact" role="status"><Loader2 size={25} className="spin" /><p>Loading research…</p></div> : active && experiment ? <><div className="run-status" role="status"><Loader2 size={19} className="spin" /><div><strong>{experiment.mode === "demo" ? "Replaying the example investigation" : "Research in progress"}</strong><p>{experiment.message}</p></div><span>{experiment.progress}%</span><div className="run-progress"><i style={{ width: `${experiment.progress}%` }} /></div></div>{experiment.steps.length > 0 && <Investigation experiment={experiment} onEvidence={showEvidence} />}</> : completed && experiment ? <>{tab === "overview" && <ResearchOverview experiment={experiment} setTab={setTab} onEvidence={showEvidence} />}{tab === "investigation" && <Investigation experiment={experiment} onEvidence={showEvidence} />}{tab === "comparison" && <Comparison experiment={experiment} />}{tab === "decision" && <Decision experiment={experiment} onFreeze={() => { setApproved(false); setPaperError(""); setPaperOpen(true); }} />}</> : <div className="empty-state panel research-empty"><span className="empty-illustration"><GitBranch size={36} /><span><Search size={24} /></span></span><span className="eyebrow">{experiment?.status === "failed" ? "INVESTIGATION FAILED" : selected.kind === "trades" ? "READY FOR DIAGNOSIS" : "READY FOR RESEARCH"}</span><h2>{experiment?.status === "failed" ? "The investigation could not finish." : "Your strategy is in. Let’s find its edge."}</h2><p>{experiment?.status === "failed" ? experiment.message : "Your file is checked and saved. Research is not connected yet, so your strategy has no findings or performance results."}</p><div className="readiness-checks"><span><Check size={15} />Columns checked</span><span><Check size={15} />Original file saved</span><span><Clock3 size={15} />{health?.research_engine ? "Research ready" : "Research connection pending"}</span></div><button className="button secondary" onClick={() => navigate("guide")}><BookOpen size={15} />How research works</button><small>No performance metrics or research findings have been generated for this strategy.</small></div>}
            </div>
          </>)}
        </>}
        <footer className="workspace-footer"><span><ShieldCheck size={12} />Understand it. Challenge it. Then test it.</span><span>All timestamps UTC <span>·</span> {health ? "Workspace connected" : "Connecting…"}</span></footer>
      </main>
    </div>
    {importOpen && <ImportWizard onClose={() => setImportOpen(false)} onImported={strategy => { setStrategies(current => [strategy, ...current.filter(item => item.strategy_id !== strategy.strategy_id)]); choose(strategy); setToast("Strategy imported. Your data is ready for research."); }} />}
    {evidence && <EvidenceModal evidence={evidence} onClose={() => setEvidence(null)} />}
    {paperOpen && experiment && <Modal title="Review your practice plan" onClose={() => { if (!savingPlan) setPaperOpen(false); }}><div className="modal-body"><span className="eyebrow">YOU MAKE THE CALL</span><h3>Two approaches. One fair test. 14 days.</h3><p>Save a plan to compare your original strategy with the suggested trading rule. This does not start trading or place orders.</p>{experiment.mode === "demo" && <div className="notice"><Beaker size={17} /><p>This plan uses illustrative demo research. It is a rehearsal, not a validated strategy recommendation.</p></div>}<dl className="evidence-facts"><div><dt>Policy</dt><dd>{experiment.policy_id}</dd></div><div><dt>Duration</dt><dd>14 days</dd></div><div><dt>Execution</dt><dd>Paper only · not started</dd></div></dl><label className="approval-checkbox"><input type="checkbox" checked={approved} onChange={event => setApproved(event.target.checked)} /><span>I have reviewed the evidence and limitations. Record this policy and its assumptions unchanged for the planned experiment.</span></label>{paperError && <p role="alert" className="negative">{paperError}</p>}<div className="modal-actions"><button className="button secondary" disabled={savingPlan} onClick={() => setPaperOpen(false)}>Cancel</button><button className="button primary" disabled={!approved || savingPlan} onClick={() => void freeze()}>{savingPlan ? <Loader2 size={15} className="spin" /> : <LockKeyhole size={15} />}Approve & record plan</button></div></div></Modal>}
    {toast && <div className="toast" role="status"><Check size={17} /><span>{toast}</span><button onClick={() => setToast("")} aria-label="Dismiss notification"><X size={14} /></button></div>}
  </div>;
}
