"use client";

import { useEffect, useId, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { ArrowLeft, ArrowRight, Check, ChevronDown, CircleHelp, FileUp, Gauge, Upload, X } from "lucide-react";
import type { Strategy, StrategyDefinition } from "../../../../packages/contracts/types";
import { Mascot } from "./redesign/mascot";
import "./strategy-intake.css";

/**
 * A bounded, inspectable strategy definition. This is intentionally a data
 * shape rather than executable Python/Pine: the evaluator can validate and
 * materialise the same rule later without running arbitrary uploaded code.
 */
const MAX_DEFINITION_BYTES = 64 * 1024;
const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"] as const;
type Timeframe = typeof TIMEFRAMES[number];
type Family = "ema_crossover" | "rsi_mean_reversion";
export type StrategyDefinitionRequest = StrategyDefinition;

type Props = {
  open: boolean;
  onClose: () => void;
  onSave: (definition: StrategyDefinitionRequest) => Promise<Strategy>;
  onCreated: (strategy: Strategy) => void;
  onHistoryImport?: () => void;
  initialFile?: File | null;
};

const familyCopy: Record<Family, { label: string; hint: string; pose: "bull-thoughtful" | "bear-question"; title: string; body: string }> = {
  ema_crossover: {
    label: "Momentum crossover",
    hint: "Follow a move when a fast average crosses a slower one.",
    pose: "bull-thoughtful",
    title: "What counts as a move?",
    body: "Set the two windows. Keep the rule legible before you test where it holds up.",
  },
  rsi_mean_reversion: {
    label: "Mean reversion",
    hint: "Look for a move back after an unusually stretched reading.",
    pose: "bear-question",
    title: "A useful question",
    body: "Choose the bounds that define stretched. The market decides whether that idea travels.",
  },
};

type DefinitionInput = Record<string, unknown>;
const isRecord = (value: unknown): value is DefinitionInput => !!value && typeof value === "object" && !Array.isArray(value);
const finite = (value: unknown) => typeof value === "number" && Number.isFinite(value);
const ownOnly = (value: DefinitionInput, allowed: readonly string[]) => Object.keys(value).every(key => allowed.includes(key));
const isoFromInput = (value: string) => value ? new Date(`${value}Z`).toISOString() : null;
const inputFromIso = (value: unknown) => typeof value === "string" && value ? new Date(value).toISOString().slice(0, 16) : "";

function parseDefinition(payload: unknown): { definition?: StrategyDefinitionRequest; error?: string } {
  if (!isRecord(payload)) return { error: "The JSON file must contain one strategy object." };
  if (!ownOnly(payload, ["schema_version", "name", "symbol", "timeframe", "strategy_version", "rule", "period", "market_data", "costs", "description"])) return { error: "This definition contains a field +EV does not support." };
  if (payload.schema_version !== "1") return { error: "Use strategy definition schema version 1." };
  if (typeof payload.name !== "string" || !payload.name.trim() || payload.name.length > 120) return { error: "Add a strategy name up to 120 characters." };
  if (typeof payload.symbol !== "string" || !payload.symbol.trim() || payload.symbol.length > 40) return { error: "Add a market symbol up to 40 characters." };
  if (typeof payload.strategy_version !== "string" || !payload.strategy_version.trim() || payload.strategy_version.length > 100) return { error: "Add a strategy version up to 100 characters." };
  if (typeof payload.timeframe !== "string" || !(TIMEFRAMES as readonly string[]).includes(payload.timeframe)) return { error: "Choose one of the supported timeframes." };
  if (!isRecord(payload.rule) || !ownOnly(payload.rule, ["family", "fast_period", "slow_period", "period", "entry_below", "exit_above", "long_position", "flat_position"])) return { error: "The rule is incomplete or has an unsupported field." };
  const rule = payload.rule;
  const longPosition = rule.long_position === undefined ? 1 : rule.long_position;
  const flatPosition = rule.flat_position === undefined ? 0 : rule.flat_position;
  if (!finite(longPosition) || Number(longPosition) !== 1 || !finite(flatPosition) || Number(flatPosition) !== 0) return { error: "This version supports long 1 and flat 0 positions only." };
  let normalizedRule: StrategyDefinitionRequest["rule"];
  if (rule.family === "ema_crossover") {
    if (!ownOnly(rule, ["family", "fast_period", "slow_period", "long_position", "flat_position"])) return { error: "This EMA rule contains an unsupported field." };
    if (!Number.isInteger(rule.fast_period) || !Number.isInteger(rule.slow_period) || Number(rule.fast_period) < 2 || Number(rule.fast_period) > 1000 || Number(rule.fast_period) >= Number(rule.slow_period) || Number(rule.slow_period) > 2000) return { error: "EMA windows must be whole numbers, with the fast window below the slow window." };
    normalizedRule = { family: "ema_crossover", fast_period: Number(rule.fast_period), slow_period: Number(rule.slow_period), long_position: Number(longPosition), flat_position: Number(flatPosition) };
  } else if (rule.family === "rsi_mean_reversion") {
    if (!ownOnly(rule, ["family", "period", "entry_below", "exit_above", "long_position", "flat_position"])) return { error: "This RSI rule contains an unsupported field." };
    if (!Number.isInteger(rule.period) || Number(rule.period) < 2 || Number(rule.period) > 1000 || !finite(rule.entry_below) || !finite(rule.exit_above) || Number(rule.entry_below) < 0 || Number(rule.exit_above) > 100 || Number(rule.entry_below) >= Number(rule.exit_above)) return { error: "RSI window and bounds must be ordered finite values." };
    normalizedRule = { family: "rsi_mean_reversion", period: Number(rule.period), entry_below: Number(rule.entry_below), exit_above: Number(rule.exit_above), long_position: Number(longPosition), flat_position: Number(flatPosition) };
  } else return { error: "Choose a supported rule family." };
  const period = payload.period === undefined ? {} : payload.period;
  if (!isRecord(period) || !ownOnly(period, ["start", "end"])) return { error: "The date period has an unsupported field." };
  if ((period.start == null) !== (period.end == null)) return { error: "Add both dates or leave the date period empty." };
  let start: string | null = null; let end: string | null = null;
  if (period.start != null && period.end != null) {
    if (typeof period.start !== "string" || typeof period.end !== "string") return { error: "The date period must use ISO timestamps." };
    if (!/(Z|[+-]\d{2}:\d{2})$/i.test(period.start) || !/(Z|[+-]\d{2}:\d{2})$/i.test(period.end)) return { error: "Include a timezone in both period timestamps." };
    const startDate = new Date(period.start); const endDate = new Date(period.end);
    if (!Number.isFinite(startDate.getTime()) || !Number.isFinite(endDate.getTime()) || endDate <= startDate) return { error: "The end date must be after the start date." };
    start = period.start; end = period.end;
  }
  const marketData = payload.market_data === undefined ? {} : payload.market_data;
  if (!isRecord(marketData) || !ownOnly(marketData, ["source", "upload_id"]) || (marketData.source !== undefined && marketData.source !== "awaiting_upload") || (marketData.upload_id !== undefined && marketData.upload_id !== null)) return { error: "This definition must wait for market data. Import history separately after saving the rule." };
  const costs = payload.costs === undefined ? {} : payload.costs;
  if (!isRecord(costs) || !ownOnly(costs, ["timezone", "fee_bps", "slippage_bps", "execution"])) return { error: "The cost assumptions contain an unsupported field." };
  const timezone = typeof costs.timezone === "string" && costs.timezone.trim() ? costs.timezone.trim() : "UTC";
  const fee = costs.fee_bps === undefined ? 5 : costs.fee_bps; const slippage = costs.slippage_bps === undefined ? 2 : costs.slippage_bps;
  if (!finite(fee) || !finite(slippage) || Number(fee) < 0 || Number(slippage) < 0 || Number(fee) > 10000 || Number(slippage) > 10000 || (costs.execution !== undefined && costs.execution !== "next_bar_open")) return { error: "Fees and slippage must be finite values between 0 and 10,000 bps." };
  if (payload.description !== undefined && (typeof payload.description !== "string" || payload.description.length > 1000)) return { error: "Notes must be 1,000 characters or fewer." };
  return { definition: { schema_version: "1", name: payload.name.trim(), symbol: payload.symbol.trim().toUpperCase(), timeframe: payload.timeframe as Timeframe, strategy_version: payload.strategy_version.trim(), rule: normalizedRule, period: { start, end }, market_data: { source: "awaiting_upload", upload_id: null }, costs: { timezone, fee_bps: Number(fee), slippage_bps: Number(slippage), execution: "next_bar_open" }, description: typeof payload.description === "string" ? payload.description.trim() : "" } };
}

function Field({ id, label, hint, error, children }: { id: string; label: string; hint?: string; error?: string; children: ReactNode }) {
  return <label className="si-field" htmlFor={id}><span className="si-field-label">{label}</span>{children}{error && <span id={`${id}-error`} className="si-error" role="alert">{error}</span>}{hint && <small>{hint}</small>}</label>;
}

export default function StrategyIntake({ open, onClose, onSave, onCreated, onHistoryImport, initialFile }: Props) {
  const titleId = useId();
  const firstField = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  const onSaveRef = useRef(onSave);
  const onHistoryImportRef = useRef(onHistoryImport);
  onCloseRef.current = onClose; onSaveRef.current = onSave; onHistoryImportRef.current = onHistoryImport;
  const [step, setStep] = useState<1 | 2>(1);
  const [family, setFamily] = useState<Family>("ema_crossover");
  const [name, setName] = useState("");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [timeframe, setTimeframe] = useState<Timeframe>("1h");
  const [strategyVersion, setStrategyVersion] = useState("v1");
  const [fastPeriod, setFastPeriod] = useState("20");
  const [slowPeriod, setSlowPeriod] = useState("50");
  const [rsiPeriod, setRsiPeriod] = useState("14");
  const [buyBelow, setBuyBelow] = useState("30");
  const [sellAbove, setSellAbove] = useState("70");
  const [timezone, setTimezone] = useState("UTC");
  const [feeBps, setFeeBps] = useState("5");
  const [slippageBps, setSlippageBps] = useState("2");
  const [description, setDescription] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [marketDataSource, setMarketDataSource] = useState<"awaiting_upload" | "user_upload">("awaiting_upload");
  const [marketDataUploadId, setMarketDataUploadId] = useState<string | undefined>();
  const [definitionFileName, setDefinitionFileName] = useState("");
  const [submitted, setSubmitted] = useState<Strategy | null>(null);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [fileError, setFileError] = useState("");
  const rawPeriod = useRef<{ start: string | null; end: string | null }>({ start: null, end: null });
  const familyId = `${titleId}-family`;
  const rule = familyCopy[family];

  const applyDefinition = (definition: StrategyDefinitionRequest) => {
    setName(definition.name); setSymbol(definition.symbol); setTimeframe(definition.timeframe); setStrategyVersion(definition.strategy_version);
    setFamily(definition.rule.family);
    if (definition.rule.family === "ema_crossover") { setFastPeriod(String(definition.rule.fast_period)); setSlowPeriod(String(definition.rule.slow_period)); }
    else { setRsiPeriod(String(definition.rule.period)); setBuyBelow(String(definition.rule.entry_below)); setSellAbove(String(definition.rule.exit_above)); }
    rawPeriod.current = { start: definition.period.start, end: definition.period.end };
    setPeriodStart(inputFromIso(definition.period.start)); setPeriodEnd(inputFromIso(definition.period.end)); setTimezone(definition.costs.timezone); setFeeBps(String(definition.costs.fee_bps)); setSlippageBps(String(definition.costs.slippage_bps)); setDescription(definition.description); setMarketDataSource("awaiting_upload"); setMarketDataUploadId(undefined); setErrors({}); setFileError(""); setFormError(""); setStep(1); setSubmitted(null);
  };
  const readDefinitionFile = async (file: File) => {
    setDefinitionFileName(file.name); setFileError("");
    if (file.size > MAX_DEFINITION_BYTES) { setFileError("Keep the JSON definition under 64 KB."); return; }
    if (!file.name.toLowerCase().endsWith(".json") && file.type !== "application/json") { setFileError("Choose a strategy-definition JSON file."); return; }
    try { const parsed = parseDefinition(JSON.parse(await file.text())); if (!parsed.definition) { setFileError(parsed.error || "This strategy definition could not be read."); return; } applyDefinition(parsed.definition); }
    catch { setFileError("The JSON file could not be read. Keep the original file and try again."); }
  };

  useEffect(() => {
    if (!open) return;
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setStep(1);
    setSubmitted(null);
    setSaving(false);
    setErrors({});
    setFormError(""); setFileError("");
    requestAnimationFrame(() => dialogRef.current?.querySelector<HTMLButtonElement>(".si-close")?.focus({ preventScroll: true }));
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); if (!savingRef.current) onCloseRef.current(); return; }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusables = [...dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex='0']")].filter(element => element.getClientRects().length > 0 && !element.hidden);
      if (!focusables.length) return;
      const current = document.activeElement;
      const index = focusables.indexOf(current as HTMLElement);
      const next = event.shiftKey ? (index <= 0 ? focusables.length - 1 : index - 1) : (index === focusables.length - 1 ? 0 : index + 1);
      if (index < 0 || next !== index) { event.preventDefault(); focusables[next]?.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      requestAnimationFrame(() => opener.current?.isConnected && opener.current.focus());
    };
  }, [open]);

  useEffect(() => { if (open && initialFile) void readDefinitionFile(initialFile); }, [open, initialFile]);

  useEffect(() => {
    if (!open || !dialogRef.current) return;
    const dialog = dialogRef.current;
    const app = dialog.closest(".kk-app");
    const background = Array.from(app?.children || []).filter((node): node is HTMLElement => node instanceof HTMLElement && !node.contains(dialog));
    const prior = background.map(element => ({ element, inert: element.inert }));
    const overflow = document.body.style.overflow;
    prior.forEach(({ element }) => { element.inert = true; });
    document.body.style.overflow = "hidden";
    return () => { prior.forEach(({ element, inert }) => { element.inert = inert; }); document.body.style.overflow = overflow; };
  }, [open]);

  const numeric = (value: string) => Number(value);
  const definition = useMemo<StrategyDefinitionRequest>(() => ({
    schema_version: "1", name: name.trim(), symbol: symbol.trim().toUpperCase(), timeframe, strategy_version: strategyVersion.trim() || "v1",
    rule: family === "ema_crossover" ? { family, fast_period: numeric(fastPeriod), slow_period: numeric(slowPeriod), long_position: 1, flat_position: 0 } : { family, period: numeric(rsiPeriod), entry_below: numeric(buyBelow), exit_above: numeric(sellAbove), long_position: 1, flat_position: 0 },
    period: { start: rawPeriod.current.start ?? isoFromInput(periodStart), end: rawPeriod.current.end ?? isoFromInput(periodEnd) }, market_data: { source: "awaiting_upload", upload_id: null }, costs: { timezone: timezone.trim() || "UTC", fee_bps: numeric(feeBps), slippage_bps: numeric(slippageBps), execution: "next_bar_open" }, description: description.trim(),
  }), [name, symbol, timeframe, strategyVersion, family, fastPeriod, slowPeriod, rsiPeriod, buyBelow, sellAbove, periodStart, periodEnd, marketDataSource, marketDataUploadId, timezone, feeBps, slippageBps, description]);

  const validate = () => {
    const next: Record<string, string> = {};
    if (!name.trim() || name.length > 120) next.name = "Add a name up to 120 characters.";
    if (!symbol.trim() || symbol.length > 40) next.symbol = "Add a market symbol up to 40 characters.";
    if (!strategyVersion.trim() || strategyVersion.length > 100) next.version = "Add a version up to 100 characters.";
    if (family === "ema_crossover") {
      if (!Number.isInteger(numeric(fastPeriod)) || numeric(fastPeriod) < 2 || numeric(fastPeriod) > 1000) next.fast = "Use a whole number from 2 to 1,000.";
      if (!Number.isInteger(numeric(slowPeriod)) || numeric(slowPeriod) <= numeric(fastPeriod) || numeric(slowPeriod) > 2000) next.slow = "Use a slow window above the fast window, up to 2,000.";
    } else {
      if (!Number.isInteger(numeric(rsiPeriod)) || numeric(rsiPeriod) < 2 || numeric(rsiPeriod) > 1000) next.rsi = "Use a whole number from 2 to 1,000.";
      if (!finite(numeric(buyBelow)) || numeric(buyBelow) < 0 || numeric(buyBelow) > 100) next.buy = "Use a value from 0 to 100.";
      if (!finite(numeric(sellAbove)) || numeric(sellAbove) < 0 || numeric(sellAbove) > 100 || numeric(sellAbove) <= numeric(buyBelow)) next.sell = "Keep the exit above the entry, up to 100.";
    }
    if ((periodStart && !periodEnd) || (!periodStart && periodEnd)) next.period = "Add both dates or leave the period empty.";
    if (periodStart && periodEnd && new Date(periodEnd) <= new Date(periodStart)) next.period = "The end date must be after the start date.";
    if (!feeBps.trim() || !finite(numeric(feeBps)) || numeric(feeBps) < 0 || numeric(feeBps) > 10000) next.fee = "Use 0 to 10,000 bps.";
    if (!slippageBps.trim() || !finite(numeric(slippageBps)) || numeric(slippageBps) < 0 || numeric(slippageBps) > 10000) next.slippage = "Use 0 to 10,000 bps.";
    if (description.length > 1000) next.description = "Keep notes under 1,000 characters.";
    setErrors(next);
    if (Object.keys(next).length) requestAnimationFrame(() => {
      const field = dialogRef.current?.querySelector<HTMLElement>("[aria-invalid='true']");
      const disclosure = field?.closest("details");
      if (disclosure) disclosure.open = true;
      field?.focus();
    });
    return Object.keys(next).length === 0;
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (savingRef.current) return;
    if (!validate()) { setStep(1); return; }
    savingRef.current = true; setSaving(true); setFormError("");
    try { const saved = await onSaveRef.current(definition); onCreated(saved); setSubmitted(saved); }
    catch (error) { setFormError(error instanceof Error ? error.message : "The strategy could not be saved. Your definition is still here."); }
    finally { savingRef.current = false; setSaving(false); }
  };

  if (!open) return null;
  return <div className="si-backdrop" role="presentation" onMouseDown={event => { if (!saving && event.target === event.currentTarget) onCloseRef.current(); }}>
    <div ref={dialogRef} className="si-dialog" role="dialog" aria-modal="true" aria-labelledby={`${titleId}-heading`} aria-describedby={`${titleId}-intro`}>
      <header className="si-header"><div><span className="si-eyebrow">STRATEGY FIRST · {submitted ? "SAVED" : step === 1 ? "DEFINE" : "REVIEW"}</span><h2 id={`${titleId}-heading`}>{submitted ? "Strategy definition saved." : step === 1 ? "Start with the rule." : "Read it back before testing."}</h2><p id={`${titleId}-intro`}>{submitted ? "Your source rule is saved. Market data and research evaluation remain separate next steps." : "Define your trading rules or upload a saved strategy file."}</p></div><button type="button" className="si-close" onClick={() => onCloseRef.current()} aria-label="Close strategy intake" disabled={saving}><X size={19} /></button></header>
      <div className="si-progress" aria-label="Strategy definition steps"><span className={step >= 1 ? "is-active" : ""}><b>1</b> Define the rule</span><i aria-hidden="true" /><span className={step >= 2 || !!submitted ? "is-active" : ""}><b>2</b> Review inputs</span></div>
      {submitted ? <section className="si-success" aria-live="polite"><div className="si-success-art"><Mascot pose="bull-acknowledge" className="si-mascot" /><div className="si-speech si-speech-success"><strong>Your rules are saved.</strong><span>No test has started. Review the definition before connecting data.</span></div></div><div className="si-definition-summary"><span className="si-summary-label">RULE DEFINITION</span><strong>{submitted.name}</strong><p>{submitted.symbol} · {submitted.timeframe} · {familyCopy[definition.rule.family].label}</p></div><div className="si-actions"><button type="button" className="si-button si-button-secondary" onClick={() => { setSubmitted(null); setStep(1); setName(""); }}>Create another strategy</button><button type="button" className="si-button si-button-primary kk-primary-button" onClick={() => onCloseRef.current()}>Continue to workspace <ArrowRight size={16} /></button></div></section> : <form onSubmit={submit}>
        {step === 1 ? <div className="si-body"><div className="si-json-link"><label className="si-upload-json"><Upload size={15} />Upload JSON definition<input type="file" accept=".json,application/json" onChange={event => { const file = event.target.files?.[0]; if (file) void readDefinitionFile(file); event.target.value = ""; }} /></label><a href="/api/templates/strategy-definition.json" download>Download JSON template</a>{definitionFileName && <span>{definitionFileName}</span>}{fileError && <p role="alert">{fileError}</p>}</div><div className="si-rule-hero"><div><p className="si-kicker">YOUR STRATEGY</p><h3>What is the rule?</h3><p>Choose a starting point, then make its settings yours.</p></div><div className="si-art"><Mascot pose={rule.pose} className="si-mascot" /><div className={`si-speech si-speech-${family === "ema_crossover" ? "bull" : "bear"}`}><strong>{rule.title}</strong><span>{rule.body}</span></div></div></div>
          <div className="si-fields"><Field id="si-name" label="Strategy name" hint="A name you will recognise later." error={errors.name}><input id="si-name" ref={firstField} value={name} onChange={event => setName(event.target.value)} placeholder="e.g. Slow trend filter" aria-invalid={!!errors.name} aria-describedby={errors.name ? "si-name-error" : undefined} /></Field><Field id="si-symbol" label="Market symbol" hint="The symbol used by your data source." error={errors.symbol}><input id="si-symbol" value={symbol} onChange={event => setSymbol(event.target.value.toUpperCase())} placeholder="BTCUSDT" aria-invalid={!!errors.symbol} aria-describedby={errors.symbol ? "si-symbol-error" : undefined} /></Field><Field id="si-timeframe" label="Timeframe"><select id="si-timeframe" value={timeframe} onChange={event => setTimeframe(event.target.value as Timeframe)}><option value="1m">1 minute</option><option value="5m">5 minutes</option><option value="15m">15 minutes</option><option value="1h">1 hour</option><option value="4h">4 hours</option><option value="1d">1 day</option></select></Field></div>
          <fieldset className="si-family"><legend id={familyId}>Rule family</legend><div className="si-family-grid">{(Object.keys(familyCopy) as Family[]).map(value => <button type="button" key={value} className={family === value ? "is-selected" : ""} aria-pressed={family === value} onClick={() => { setFamily(value); setErrors({}); }}><span className="si-family-title">{familyCopy[value].label}</span><small>{familyCopy[value].hint}</small></button>)}</div></fieldset>
          <div className="si-rule-fields">{family === "ema_crossover" ? <><Field id="si-fast" label="Fast EMA window" hint="Bars used for the faster average." error={errors.fast}><input id="si-fast" inputMode="numeric" type="number" min="2" max="1000" value={fastPeriod} onChange={event => setFastPeriod(event.target.value)} aria-invalid={!!errors.fast} aria-describedby={errors.fast ? "si-fast-error" : undefined} /></Field><Field id="si-slow" label="Slow EMA window" hint="Bars used for the slower average." error={errors.slow}><input id="si-slow" inputMode="numeric" type="number" min="3" max="2000" value={slowPeriod} onChange={event => setSlowPeriod(event.target.value)} aria-invalid={!!errors.slow} aria-describedby={errors.slow ? "si-slow-error" : undefined} /></Field></> : <><Field id="si-rsi" label="RSI window" hint="Bars used to calculate RSI." error={errors.rsi}><input id="si-rsi" inputMode="numeric" type="number" min="2" max="1000" value={rsiPeriod} onChange={event => setRsiPeriod(event.target.value)} aria-invalid={!!errors.rsi} aria-describedby={errors.rsi ? "si-rsi-error" : undefined} /></Field><Field id="si-buy" label="Enter below" hint="Enter when RSI is below this value." error={errors.buy}><input id="si-buy" inputMode="numeric" type="number" min="0" max="100" value={buyBelow} onChange={event => setBuyBelow(event.target.value)} aria-invalid={!!errors.buy} aria-describedby={errors.buy ? "si-buy-error" : undefined} /></Field><Field id="si-sell" label="Exit above" hint="Exit when RSI is above this value." error={errors.sell}><input id="si-sell" inputMode="numeric" type="number" min="0" max="100" value={sellAbove} onChange={event => setSellAbove(event.target.value)} aria-invalid={!!errors.sell} aria-describedby={errors.sell ? "si-sell-error" : undefined} /></Field></>}</div>
          <details className="si-details"><summary><span><Gauge size={16} />Period &amp; assumptions</span><ChevronDown size={17} /></summary><div className="si-fields si-fields-secondary"><Field id="si-version" label="Strategy version" hint="Change this when the rule changes." error={errors.version}><input id="si-version" value={strategyVersion} onChange={event => setStrategyVersion(event.target.value)} placeholder="v1" aria-invalid={!!errors.version} aria-describedby={errors.version ? "si-version-error" : undefined} /></Field><Field id="si-period-start" label="Test period start" hint="Optional; use UTC dates." error={errors.period}><input id="si-period-start" type="datetime-local" step="any" value={periodStart} onChange={event => { rawPeriod.current.start = null; setPeriodStart(event.target.value); }} aria-invalid={!!errors.period} aria-describedby={errors.period ? "si-period-start-error" : undefined} /></Field><Field id="si-period-end" label="Test period end" hint="Optional; must be after start." error={errors.period}><input id="si-period-end" type="datetime-local" step="any" value={periodEnd} onChange={event => { rawPeriod.current.end = null; setPeriodEnd(event.target.value); }} aria-invalid={!!errors.period} aria-describedby={errors.period ? "si-period-end-error" : undefined} /></Field></div><div className="si-details-grid"><Field id="si-timezone" label="Timezone"><select id="si-timezone" value={timezone} onChange={event => setTimezone(event.target.value)}><option>UTC</option><option>Europe/London</option><option>America/New_York</option>{!["UTC", "Europe/London", "America/New_York"].includes(timezone) && <option>{timezone}</option>}</select></Field><Field id="si-fee" label="Trading fee" hint="Basis points per trade." error={errors.fee}><input id="si-fee" inputMode="decimal" type="number" min="0" max="10000" step="0.1" value={feeBps} onChange={event => setFeeBps(event.target.value)} aria-invalid={!!errors.fee} aria-describedby={errors.fee ? "si-fee-error" : undefined} /></Field><Field id="si-slippage" label="Slippage" hint="Basis points per trade." error={errors.slippage}><input id="si-slippage" inputMode="decimal" type="number" min="0" max="10000" step="0.1" value={slippageBps} onChange={event => setSlippageBps(event.target.value)} aria-invalid={!!errors.slippage} aria-describedby={errors.slippage ? "si-slippage-error" : undefined} /></Field><Field id="si-description" label="Notes" hint="Optional context for the research record." error={errors.description}><textarea id="si-description" value={description} onChange={event => setDescription(event.target.value)} placeholder="What should the evaluator keep in mind?" rows={2} aria-invalid={!!errors.description} aria-describedby={errors.description ? "si-description-error" : undefined} /></Field></div></details>
          <div className="si-history-link"><CircleHelp size={16} /><span>Already have signals or completed trades?</span><button type="button" onClick={() => onHistoryImportRef.current?.()}>Import history instead <FileUp size={15} /></button></div>
        </div> : <div className="si-body si-review"><div className="si-review-lead"><div className="si-art"><Mascot pose="bull-present-up" className="si-mascot" /><div className="si-speech si-speech-bull"><strong>Read it once.</strong><span>A clear rule makes a fair test possible.</span></div></div><div><p className="si-kicker">YOUR RULE</p><h3>{definition.name || "Untitled strategy"}</h3><p>{definition.symbol} · {definition.timeframe} · {familyCopy[definition.rule.family].label}</p></div></div><dl className="si-review-list"><div><dt>Entry and exit</dt><dd>{family === "ema_crossover" ? `Stay long while the ${fastPeriod}-bar EMA is above the ${slowPeriod}-bar EMA; otherwise stay flat.` : `Enter below RSI ${buyBelow}; exit above RSI ${sellAbove}, using a ${rsiPeriod}-bar window.`}</dd></div><div><dt>Period and costs</dt><dd>{periodStart && periodEnd ? `${periodStart.replace("T", " ")} → ${periodEnd.replace("T", " ")}` : "Test period not set"} · {timezone} · {feeBps} bps fee · {slippageBps} bps slippage</dd></div><div><dt>What happens next</dt><dd>The definition is saved as the source rule. Results remain unavailable until market data and the research engine are available.</dd></div></dl><p className="si-review-check">Saving records your rules. It does not start a test or place an order.</p></div>}
        {formError && <p className="si-form-error" role="alert">{formError}</p>}
        <footer className="si-footer">
          {step === 1 ? <>
            <span className="si-footer-note">Rules stay separate from historical evidence.</span>
            <div><button type="button" className="si-button si-button-secondary" onClick={() => onCloseRef.current()} disabled={saving}>Cancel</button><button type="button" className="si-button si-button-primary kk-primary-button" onClick={() => { if (validate()) setStep(2); }} disabled={saving}>Review rule <ArrowRight size={16} /></button></div>
          </> : <>
            <button type="button" className="si-button si-button-secondary" onClick={() => setStep(1)} disabled={saving}><ArrowLeft size={16} /> Back</button>
            <button type="submit" className="si-button si-button-primary kk-primary-button" disabled={saving}>{saving ? "Saving..." : "Save strategy definition"} {!saving && <Check size={16} />}</button>
          </>}
        </footer>
      </form>}
    </div>
  </div>;
}
