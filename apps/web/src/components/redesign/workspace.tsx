"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, ChevronDown, Menu, Plus, Settings2, X } from "lucide-react";
import type { Evidence, Experiment, Health, PaperPlan, Strategy } from "../../../../../packages/contracts/types";
import { api } from "@/lib/api";
import ImportWizard from "../import-wizard";
import StrategyView from "./strategy-view";
import ResearchOverview from "./overview";
import ConditionsView from "./conditions";
import EvidenceView, { EvidenceDialog } from "./evidence";
import ComparisonView from "./comparison";
import PaperReview from "./paper-review";
import ObserveView from "./observe";
import StrategyEntry from "./strategy-entry";
import { ActiveIndicator, InterfaceMotion, Reveal } from "./ui-motion";
import { verdictHeadline, verdictLabel } from "./decision";
import type { ExploreTab, MainView, MotionPreference, SharedResearchProps } from "./types";
import "./workspace.css";

function recordedExample(items: Strategy[]) {
  return items.find(item => item.strategy_id === "btc-trend-24-72-demo") || items.find(item => item.status === "demo");
}

const PORTFOLIO = [
  { id: "btc-trend-24-72-demo", name: "BTC trend 24/72", verdict: "Not proven", detail: "Sealed intervals contain zero. The critic vetoed every gate." },
  { id: "btc-meanrev-48-demo", name: "BTC mean reversion 48", verdict: "Kill", detail: "Always-on is a kill. The accepted gate beat it on the sealed look and still lost money." },
];

const topViews: { id: MainView; label: string; hint: string }[] = [
  { id: "strategy", label: "Strategy", hint: "Add, check and test your strategy" },
  { id: "explore", label: "Explore", hint: "Read patterns and evidence" },
  { id: "compare", label: "Compare", hint: "Test a proposed filter" },
  { id: "observe", label: "Plans", hint: "Review saved paper plans" },
];

const exploreTabs: { id: ExploreTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "conditions", label: "Conditions" },
  { id: "evidence", label: "Evidence" },
];

const errorText = (value: unknown) => value instanceof Error ? value.message : "Something went wrong. Please retry.";
type UrlState = { view: MainView; tab: ExploreTab; strategy: string; experiment: string; date: string; compare: boolean; viewExplicit: boolean };

const EMPTY_URL_STATE: UrlState = { view: "strategy", tab: "overview", strategy: "", experiment: "", date: "", compare: false, viewExplicit: false };

function readUrl(): UrlState {
  if (typeof window === "undefined") return EMPTY_URL_STATE;
  const params = new URLSearchParams(window.location.search);
  const view = params.get("view");
  const tab = params.get("tab");
  const resolvedView = topViews.some(item => item.id === view) ? view as MainView : "strategy";
  return {
    view: resolvedView,
    tab: exploreTabs.some(item => item.id === tab) ? tab as ExploreTab : "overview",
    strategy: params.get("strategy") || "",
    experiment: params.get("experiment") || "",
    date: params.get("date") || "",
    // `tab=review` keeps the complete navigation state in the documented
    // view/tab/strategy/experiment/date query contract. Accept the old
    // compare key too so existing bookmarks continue to work.
    compare: (resolvedView === "compare" && tab === "review") || params.get("compare") === "review",
    viewExplicit: topViews.some(item => item.id === view),
  };
}

function writeUrl(state: Partial<UrlState>, replace = false) {
  if (typeof window === "undefined") return;
  const current = readUrl();
  const next = { ...current, ...state };
  // Keep unrelated query parameters intact. Other parts of the app may use
  // the URL for a share token or an experiment filter that this shell does not
  // own.
  const params = new URLSearchParams(window.location.search);
  ["view", "tab", "strategy", "experiment", "date", "compare"].forEach(key => params.delete(key));
  // Keep an explicit Strategy view when a strategy is selected. The bare
  // root remains the cinematic entry route, while ?strategy=... should reload
  // the setup screen rather than silently defaulting to Explore.
  if (next.view !== "strategy" || next.strategy) params.set("view", next.view);
  if (next.compare) params.set("tab", "review");
  else if (next.tab !== "overview") params.set("tab", next.tab);
  if (next.strategy) params.set("strategy", next.strategy);
  if (next.experiment) params.set("experiment", next.experiment);
  if (next.date) params.set("date", next.date);
  const url = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}${window.location.hash}`;
  if (replace) window.history.replaceState(null, "", url);
  else window.history.pushState(null, "", url);
}

function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const started = useRef(0);
  const remaining = useRef(5000);
  const schedule = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    started.current = Date.now();
    timer.current = setTimeout(onClose, remaining.current);
  }, [onClose]);
  useEffect(() => { remaining.current = 5000; schedule(); return () => { if (timer.current) clearTimeout(timer.current); }; }, [message, schedule]);
  const pause = () => { if (!timer.current) return; clearTimeout(timer.current); remaining.current = Math.max(0, remaining.current - (Date.now() - started.current)); timer.current = null; };
  const resume = () => { if (!timer.current) schedule(); };
  return <div className="kk-toast" role="status" aria-live="polite" onMouseEnter={pause} onMouseLeave={resume} onFocus={pause} onBlur={resume}>
    <span>{message}</span><button type="button" onClick={onClose} aria-label="Dismiss message"><X size={16} /></button>
  </div>;
}

function EmptyStage({ title, body, action, onAction }: { title: string; body: string; action?: string; onAction?: () => void }) {
  return <section className="kk-empty-stage" aria-live="polite"><p className="kk-kicker">KEEP OR KILL</p><h1>{title}</h1><p>{body}</p>{action && onAction && <button type="button" className="kk-action kk-action-primary" onClick={onAction}>{action} <ArrowUpRight size={15} /></button>}</section>;
}

function ResearchLoading({ strategy }: { strategy: Strategy }) {
  return <section className="kk-empty-stage kk-research-loading" role="status" aria-live="polite">
    <p className="kk-kicker">CHECKING THE RESEARCH RECORD</p>
    <h1>Opening {strategy.name}.</h1>
    <p>Checking the latest saved run before showing results. Nothing is being recalculated.</p>
    <div className="kk-status-rule" aria-hidden="true"><span /></div>
  </section>;
}

function ExperimentStatus({ experiment }: { experiment: Experiment }) {
  const activeStep = experiment.steps.find(step => step.status === "running");
  const statusLabel = experiment.status === "queued"
    ? "Waiting for the research engine"
    : experiment.status === "running"
      ? "Research in progress"
      : experiment.status === "awaiting_engine"
        ? "Research engine unavailable"
        : "Research run stopped";
  const fallbackMessage = experiment.status === "queued"
    ? "Your request is saved. The evaluator has not started it yet."
    : experiment.status === "running"
      ? "The research agents are working through the saved strategy."
      : experiment.status === "awaiting_engine"
        ? "The uploaded strategy is saved, but the research engine is not connected yet."
        : "The evaluator stopped before it produced a complete report.";
  const visibleSteps = experiment.steps.filter(step => step.status === "complete" || step.status === "running" || step.status === "rejected");
  return <section className={`kk-run-status kk-run-${experiment.status}`} role="status" aria-live="polite">
    <div className="kk-run-status-head"><span className="kk-run-dot" aria-hidden="true" /><div><p className="kk-kicker">RESEARCH STATUS</p><h2>{statusLabel}</h2></div></div>
    <p className="kk-run-message">{experiment.message || fallbackMessage}</p>
    {activeStep && <p className="kk-run-stage"><span>Current step</span>{activeStep.title}</p>}
    {visibleSteps.length > 0 && <ul className="kk-run-steps" aria-label="Research steps">{visibleSteps.map(step => <li key={step.id} className={`kk-run-step-${step.status}`}><span aria-hidden="true" />{step.title}</li>)}</ul>}
  </section>;
}

function ConnectionNotice({ strategy, health, onExample }: { strategy: Strategy | null; health: Health | null; onExample?: () => void }) {
  if (!strategy || strategy.status === "demo" || !health || health.research_engine) return null;
  return <aside className="kk-connection-note" role="note">
    <div><p className="kk-kicker">RESEARCH ENGINE NOT CONNECTED</p><p>Your imported data is saved and ready. A measured backtest cannot run until the research service is online.</p></div>
    {onExample && <button type="button" className="kk-action" onClick={onExample}>Replay the example <ArrowUpRight size={15} /></button>}
  </aside>;
}

export default function Workspace() {
  // Keep the first render identical on the server and client. The URL and
  // local preferences are applied in effects immediately after hydration.
  const initial = EMPTY_URL_STATE;
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedId, setSelectedId] = useState(initial.strategy);
  const [urlExperimentId, setUrlExperimentId] = useState(initial.experiment);
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [exampleExperiment, setExampleExperiment] = useState<Experiment | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [plans, setPlans] = useState<PaperPlan[]>([]);
  const [view, setView] = useState<MainView>(initial.view);
  const [tab, setTab] = useState<ExploreTab>(initial.tab);
  const [selectedDate, setSelectedDate] = useState<string | null>(initial.date || null);
  const [compareReview, setCompareReview] = useState(initial.compare);
  const [entryOpen, setEntryOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [experimentLoading, setExperimentLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [initialImportFile, setInitialImportFile] = useState<File | null>(null);
  const [strategyMenu, setStrategyMenu] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [displayMenu, setDisplayMenu] = useState(false);
  const [strategyQuery, setStrategyQuery] = useState("");
  const [motion, setMotion] = useState<MotionPreference>("system");
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const navRefs = useRef<Record<MainView, HTMLButtonElement | null>>({ strategy: null, explore: null, compare: null, observe: null });
  const strategyTriggerRef = useRef<HTMLButtonElement | null>(null);
  const strategyPanelRef = useRef<HTMLDivElement | null>(null);
  const displayTriggerRef = useRef<HTMLButtonElement | null>(null);
  const navDisplayRef = useRef<HTMLButtonElement | null>(null);
  const displayFocusRef = useRef<HTMLElement | null>(null);
  const displayPanelRef = useRef<HTMLDivElement | null>(null);
  const mobileMenuRef = useRef<HTMLButtonElement | null>(null);
  const runInFlightRef = useRef(false);
  const entryOpenRef = useRef(entryOpen);
  entryOpenRef.current = entryOpen;
  const selected = strategies.find(item => item.strategy_id === selectedId) || null;
  const filteredStrategies = strategies.filter(strategy => `${strategy.name} ${strategy.symbol} ${strategy.timeframe}`.toLowerCase().includes(strategyQuery.trim().toLowerCase()));
  const exampleStrategy = recordedExample(strategies);
  const portfolio = PORTFOLIO.filter(item => strategies.some(strategy => strategy.strategy_id === item.id));
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;
  const dismissToast = useCallback(() => setToast(""), []);

  const setMotionPreference = (next: MotionPreference) => { setMotion(next); localStorage.setItem("kok.motion", next); };

  useEffect(() => {
    const state = readUrl();
    setView(state.view); setTab(state.tab); setSelectedDate(state.date || null); setCompareReview(state.compare); setUrlExperimentId(state.experiment);
    setEntryOpen(!state.viewExplicit && !state.strategy);
    if (state.strategy) setSelectedId(state.strategy);
    const stored = localStorage.getItem("kok.motion") as MotionPreference | null;
    if (stored === "system" || stored === "reduced" || stored === "full") setMotion(stored);
  }, []);

  const applyUrl = useCallback((state: UrlState, focus = false) => {
    setView(state.view); setTab(state.tab); setSelectedDate(state.date || null); setCompareReview(state.compare); setUrlExperimentId(state.experiment); setEntryOpen(!state.viewExplicit && !state.strategy);
    if (state.strategy && strategies.some(item => item.strategy_id === state.strategy)) setSelectedId(state.strategy);
    if (focus) requestAnimationFrame(() => navRefs.current[state.view]?.focus());
  }, [strategies]);

  useEffect(() => {
    const onPop = () => applyUrl(readUrl(), true);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [applyUrl]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([api.strategies(), api.health(), api.paperPlans()]).then(([items, state, savedPlans]) => {
      if (cancelled) return;
      setStrategies(items); setHealth(state); setPlans(savedPlans);
      const currentUrl = readUrl();
      const remembered = currentUrl.strategy || localStorage.getItem("kok.selected") || "";
      const fallback = items.find(item => item.strategy_id === remembered)?.strategy_id || items.find(item => item.status !== "demo")?.strategy_id || items.find(item => item.strategy_id.includes("trend"))?.strategy_id || items[0]?.strategy_id || "";
      setSelectedId(fallback);
      setUrlExperimentId(currentUrl.experiment);
      const atEntry = !currentUrl.viewExplicit && !currentUrl.strategy;
      // A saved strategy opens on Explore by default. An explicit view in a
      // bookmark still wins, including the setup view for a new strategy.
      const nextView = currentUrl.viewExplicit ? currentUrl.view : (fallback ? "explore" : "strategy");
      setEntryOpen(atEntry);
      if (!atEntry) setView(nextView);
      if (fallback && !atEntry && (!currentUrl.strategy || !currentUrl.viewExplicit)) writeUrl({ strategy: fallback, view: nextView }, true);
    }).catch(failure => { if (!cancelled) setError(errorText(failure)); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [initial.strategy]);

  useEffect(() => {
    const example = recordedExample(strategies);
    if (!example) { setExampleExperiment(null); return; }
    let cancelled = false;
    api.experiments(example.strategy_id).then(items => { if (!cancelled) setExampleExperiment(items[0] || null); }).catch(() => { if (!cancelled) setExampleExperiment(null); });
    return () => { cancelled = true; };
  }, [strategies]);

  useEffect(() => {
    if (!selectedId) { setExperiment(null); return; }
    let cancelled = false;
    setExperimentLoading(true); setExperiment(null);
    api.experiments(selectedId).then(items => {
      if (cancelled || selectedIdRef.current !== selectedId) return;
      const found = (urlExperimentId ? items.find(item => item.experiment_id === urlExperimentId) : undefined) || items[0] || null; setExperiment(found);
      if (found?.experiment_id && !entryOpenRef.current) writeUrl({ strategy: selectedId, experiment: found.experiment_id }, true);
    }).catch(failure => { if (!cancelled) setError(errorText(failure)); }).finally(() => { if (!cancelled) setExperimentLoading(false); });
    return () => { cancelled = true; };
  }, [selectedId, urlExperimentId]);

  const active = experiment?.status === "queued" || experiment?.status === "running";
  const incompleteResearch = !!experiment && (experiment.status === "queued" || experiment.status === "running" || experiment.status === "awaiting_engine" || experiment.status === "failed");
  useEffect(() => {
    if (!active || !experiment) return;
    let cancelled = false; let requestInFlight = false;
    const experimentId = experiment.experiment_id;
    const poll = async () => {
      if (requestInFlight) return; requestInFlight = true;
      try { const latest = await api.experiment(experimentId); if (!cancelled && selectedIdRef.current === latest.strategy_id && latest.experiment_id === experimentId) { setExperiment(latest); if (latest.status === "completed") setToast("Research is ready. Review the result and evidence."); } }
      catch (failure) { if (!cancelled) setError(errorText(failure)); }
      finally { requestInFlight = false; }
    };
    const timer = setInterval(poll, 1200);
    return () => { cancelled = true; clearInterval(timer); };
  }, [active, experiment?.experiment_id]);

  const openImport = (file?: File) => { setInitialImportFile(file || null); setImportOpen(true); setStrategyMenu(false); };
  const closeImport = () => { setImportOpen(false); setInitialImportFile(null); };
  const scrollTop = () => { if (typeof window !== "undefined") window.scrollTo(0, 0); };
  const selectView = (next: MainView) => { scrollTop(); setEntryOpen(false); setView(next); setTab(next === "explore" ? tab : "overview"); setMobileNav(false); setStrategyMenu(false); setDisplayMenu(false); writeUrl({ view: next, tab: next === "explore" ? tab : "overview", compare: false }); setCompareReview(false); };
  const selectStrategy = (strategy: Strategy) => { scrollTop(); localStorage.setItem("kok.selected", strategy.strategy_id); setEntryOpen(false); setSelectedId(strategy.strategy_id); setUrlExperimentId(""); setSelectedDate(null); setTab("overview"); setCompareReview(false); setView("explore"); setStrategyMenu(false); setStrategyQuery(""); writeUrl({ strategy: strategy.strategy_id, view: "explore", tab: "overview", experiment: "", date: "", compare: false }); };
  const onSelectDate = (date: string | null) => { setSelectedDate(date); writeUrl({ date: date || "" }, true); };
  const onExploreTab = (next: ExploreTab) => { scrollTop(); setTab(next); writeUrl({ view: "explore", tab: next }); };
  const shared: SharedResearchProps | null = experiment && selected ? { experiment, strategy: selected, selectedDate, onSelectDate, onEvidence: setEvidenceById } : null;
  function setEvidenceById(id: string) { const item = experiment?.evidence.find(candidate => candidate.id === id); if (item) setEvidence(item); else setToast("That evidence is not available in this run."); }
  const onRun = async () => {
    if (!selected || running || active || runInFlightRef.current) return;
    if (selected.status !== "demo" && !health?.research_engine) { setToast("The research engine is not connected for uploaded strategies yet."); return; }
    runInFlightRef.current = true; setEntryOpen(false); setRunning(true); setError("");
    try { const result = await api.investigate(selected.strategy_id); if (selectedIdRef.current === selected.strategy_id) { setUrlExperimentId(result.experiment_id); setExperiment(result); setView("explore"); setTab("overview"); writeUrl({ strategy: selected.strategy_id, view: "explore", tab: "overview", experiment: result.experiment_id }); } }
    catch (failure) { setError(errorText(failure)); }
    finally { runInFlightRef.current = false; setRunning(false); }
  };
  const onImported = (strategy: Strategy) => { setStrategies(current => [strategy, ...current.filter(item => item.strategy_id !== strategy.strategy_id)]); selectStrategy(strategy); setView("strategy"); setTab("overview"); writeUrl({ strategy: strategy.strategy_id, view: "strategy", tab: "overview", experiment: "", date: "", compare: false }); setToast("Strategy added. Check the data before running a test."); };
  const onSavedPlan = (plan: PaperPlan) => { setPlans(current => [plan, ...current.filter(item => item.paper_test_id !== plan.paper_test_id)]); setCompareReview(false); setView("observe"); setTab("overview"); writeUrl({ view: "observe", tab: "overview", compare: false }); setToast("Paper test plan saved. No live orders were started."); };
  const showReview = () => { scrollTop(); setView("compare"); setTab("overview"); setCompareReview(true); writeUrl({ view: "compare", tab: "overview", compare: true }); };

  useEffect(() => {
    if (!strategyMenu && !displayMenu && !mobileNav) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      const focusTarget = strategyMenu ? strategyTriggerRef.current : displayMenu ? (displayFocusRef.current || displayTriggerRef.current) : mobileMenuRef.current;
      setStrategyMenu(false); setDisplayMenu(false); setMobileNav(false); setStrategyQuery("");
      requestAnimationFrame(() => focusTarget?.focus());
    };
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (strategyMenu && !strategyPanelRef.current?.contains(target) && !strategyTriggerRef.current?.contains(target)) setStrategyMenu(false);
      if (displayMenu && !displayPanelRef.current?.contains(target) && !displayTriggerRef.current?.contains(target) && !navDisplayRef.current?.contains(target)) setDisplayMenu(false);
      if (mobileNav && !mobileMenuRef.current?.contains(target) && !document.querySelector(".kk-nav")?.contains(target)) setMobileNav(false);
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => { document.removeEventListener("keydown", onKeyDown); document.removeEventListener("pointerdown", onPointerDown); };
  }, [strategyMenu, displayMenu, mobileNav]);

  return <InterfaceMotion preference={motion}><div className="kk-app" data-motion={motion} data-view={view}>
    <a className="kk-skip" href="#kk-main">Skip to main content</a>
    <header className="kk-header">
      <button className="kk-wordmark" type="button" onClick={() => { scrollTop(); setEntryOpen(true); setMobileNav(false); setStrategyMenu(false); setDisplayMenu(false); writeUrl({ view: "strategy", tab: "overview", strategy: "", experiment: "", date: "", compare: false }); }} aria-label="Keep or Kill home"><span>keep<span className="kk-slash">/</span>kill</span></button>
      <div className="kk-header-context">
        {selected ? <button ref={strategyTriggerRef} type="button" className="kk-strategy-trigger" title={selected.name} aria-label={`Switch strategy: ${selected.name}`} aria-expanded={strategyMenu} aria-haspopup="dialog" onClick={() => setStrategyMenu(value => !value)}>Your strategies<ChevronDown size={15} /></button> : <span className="kk-context-quiet">No strategy selected</span>}
        {strategyMenu && <div ref={strategyPanelRef} className="kk-switcher" role="dialog" aria-label="Switch strategy"><div className="kk-switcher-head"><span>Switch strategy</span><button type="button" onClick={() => { setStrategyMenu(false); strategyTriggerRef.current?.focus(); }} aria-label="Close strategy switcher"><X size={15} /></button></div><label className="kk-switcher-search"><span className="kk-sr-only">Find a strategy</span><input value={strategyQuery} onChange={event => setStrategyQuery(event.target.value)} placeholder="Find a strategy" aria-label="Find a strategy" /></label><div className="kk-switcher-list">{filteredStrategies.map(strategy => <button type="button" key={strategy.strategy_id} className={strategy.strategy_id === selectedId ? "selected" : ""} onClick={() => selectStrategy(strategy)}><span><strong>{strategy.name}</strong><small>{strategy.symbol} · {strategy.timeframe} · {strategy.source === "recorded_investigation" ? "Recorded" : strategy.status === "demo" ? "Example" : "Imported"}</small></span><ArrowUpRight size={14} /></button>)}{filteredStrategies.length === 0 && <p className="kk-switcher-empty">No matching strategy.</p>}<button type="button" className="kk-switcher-add" onClick={() => openImport()}><Plus size={15} />Add strategy</button></div></div>}
      </div>
      <nav className={`kk-nav ${mobileNav ? "open" : ""}`} aria-label="Primary navigation">{topViews.map(item => <button type="button" key={item.id} ref={node => { navRefs.current[item.id] = node; }} className={view === item.id ? "active" : ""} aria-current={view === item.id ? "page" : undefined} onClick={() => selectView(item.id)} title={item.hint}>{view === item.id && <ActiveIndicator group="primary" />}<span className="kk-nav-label">{item.label}</span></button>)}<button ref={navDisplayRef} className="kk-nav-display" type="button" aria-label="Display settings" title="Display settings" aria-expanded={displayMenu} aria-haspopup="dialog" onClick={() => { displayFocusRef.current = navDisplayRef.current; setDisplayMenu(value => !value); setMobileNav(false); }}><Settings2 size={17} /></button></nav>
      <div className="kk-header-actions"><button ref={displayTriggerRef} className="kk-display" type="button" aria-expanded={displayMenu} aria-haspopup="dialog" onClick={() => { displayFocusRef.current = displayTriggerRef.current; setDisplayMenu(value => !value); }}><Settings2 size={16} /><span>Display</span></button><button ref={mobileMenuRef} className="kk-mobile-menu" type="button" aria-expanded={mobileNav} aria-haspopup="menu" onClick={() => setMobileNav(value => !value)} aria-label="Navigate"><Menu size={21} /><span>Navigate</span></button></div>
      {displayMenu && <div ref={displayPanelRef} className="kk-display-menu" role="dialog" aria-label="Display settings"><span>Motion</span>{(["system", "reduced", "full"] as MotionPreference[]).map(option => <button type="button" key={option} className={motion === option ? "selected" : ""} onClick={() => { setMotionPreference(option); setDisplayMenu(false); displayFocusRef.current?.focus(); }}>{option[0].toUpperCase() + option.slice(1)}</button>)}</div>}
    </header>
    <main id="kk-main" className="kk-main">
      {error && <div className="kk-error" role="alert"><span>{error}</span><button type="button" onClick={() => setError("")}>Dismiss</button></div>}
      {entryOpen ? <StrategyEntry example={exampleExperiment} triage={portfolio} onOpen={id => { const strategy = strategies.find(item => item.strategy_id === id); if (strategy) selectStrategy(strategy); }} onImport={openImport} onExample={() => { if (exampleStrategy) selectStrategy(exampleStrategy); }} onResume={selected ? () => selectStrategy(selected) : undefined} /> : loading ? <div className="kk-loading" role="status"><span className="kk-loading-line" />Preparing your research workspace</div> : <>
        <ConnectionNotice strategy={selected} health={health} onExample={exampleStrategy ? () => selectStrategy(exampleStrategy) : undefined} />
        {view !== "observe" && selected && experimentLoading ? <ResearchLoading strategy={selected} /> : <>
          {view === "strategy" && <Reveal key={selectedId}><StrategyView strategy={selected} experiment={experiment} health={health} onImport={openImport} onExample={() => { if (exampleStrategy) selectStrategy(exampleStrategy); }} onRun={onRun} running={running || !!active} />{incompleteResearch && experiment && <ExperimentStatus experiment={experiment} />}</Reveal>}
          {view === "explore" && !shared && <EmptyStage title="Start with your strategy." body="Upload your signals or positions to begin the research." action="Add your strategy" onAction={() => openImport()} />}
          {view === "explore" && shared && <>
            <section className="kk-verdict-lead" aria-label="Decision">
              <p className="kk-verdict-kicker">{verdictLabel(shared.experiment.verdict)}</p>
              <h2>{shared.experiment.mode === "pending" ? "Research is pending." : verdictHeadline(shared.experiment.verdict)}</h2>
              {shared.experiment.recommendation && <p>{shared.experiment.recommendation}</p>}
            </section>
            <div className="kk-local-nav" role="tablist" aria-label="Explore views">{exploreTabs.map(item => <button type="button" key={item.id} role="tab" aria-selected={tab === item.id} className={tab === item.id ? "active" : ""} onClick={() => onExploreTab(item.id)}>{tab === item.id && <ActiveIndicator group="explore" />}<span className="kk-nav-label">{item.label}</span></button>)}</div>
            {incompleteResearch && <ExperimentStatus experiment={shared.experiment} />}
            {!incompleteResearch && tab === "overview" && <Reveal key="overview"><ResearchOverview {...shared} onConditions={() => onExploreTab("conditions")} onCompare={() => selectView("compare")} /></Reveal>}
            {!incompleteResearch && tab === "conditions" && <Reveal key="conditions"><ConditionsView {...shared} /></Reveal>}
            {!incompleteResearch && tab === "evidence" && <Reveal key="evidence"><EvidenceView {...shared} onCompare={() => selectView("compare")} /></Reveal>}
          </>}
          {view === "compare" && !shared && <EmptyStage title="There is nothing to compare yet." body="Run a backtest and find a candidate rule before comparing it on unseen history." action="Go to Strategy" onAction={() => selectView("strategy")} />}
          {view === "compare" && shared && (incompleteResearch ? <ExperimentStatus experiment={shared.experiment} /> : compareReview ? <PaperReview experiment={shared.experiment} strategy={shared.strategy} onSaved={onSavedPlan} onBack={() => { setCompareReview(false); writeUrl({ compare: false }, true); }} /> : <Reveal key="comparison"><ComparisonView {...shared} onReview={showReview} /></Reveal>)}
          {view === "observe" && <Reveal key="plans"><ObserveView plans={plans} strategies={strategies} onReview={() => { if (shared) showReview(); else selectView("strategy"); }} /></Reveal>}
        </>}
      </>}
      {!entryOpen && !(view === "explore" && tab === "overview") && <footer className="kk-footer"><span>Research only · no live trading</span></footer>}
    </main>
    {importOpen && <ImportWizard initialFile={initialImportFile} onClose={closeImport} onImported={onImported} />}
    {evidence && <EvidenceDialog evidence={evidence} onClose={() => setEvidence(null)} />}
    {toast && <Toast message={toast} onClose={dismissToast} />}
  </div></InterfaceMotion>;
}
