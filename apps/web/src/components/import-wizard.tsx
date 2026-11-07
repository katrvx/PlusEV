"use client";

import { API_ROUTES } from "../../../../packages/contracts/api";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Info,
  Loader2,
  UploadCloud,
  X,
} from "lucide-react";
import type {
  ImportKind,
  ImportPreview,
  ImportRequest,
  ImportResult,
  Strategy,
  ValidationIssue,
} from "../../../../packages/contracts/types";
import { api } from "@/lib/api";
import "./import-wizard.css";

type Props = {
  onClose: () => void;
  onImported: (strategy: Strategy) => void;
  initialFile?: File | null;
};

type FormState = {
  name: string;
  symbol: string;
  timeframe: string;
  strategy_version: string;
  kind: ImportKind;
  timezone: string;
  fee_bps: string;
  slippage_bps: string;
  description: string;
};

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const DEFAULT_FORM: FormState = {
  name: "",
  symbol: "BTCUSDT",
  timeframe: "1h",
  strategy_version: "v1",
  kind: "positions",
  timezone: "UTC",
  fee_bps: "5",
  slippage_bps: "3",
  description: "",
};

const POSITION_FIELDS = [
  { key: "decision_time", label: "Timestamp", hint: "When this row was recorded" },
  { key: "symbol", label: "Market / symbol", hint: "The asset this row refers to" },
  { key: "target_position", label: "Capital allocation", hint: "How much capital the strategy uses here (−1 to 1)" },
] as const;

const TRADE_FIELDS = [
  { key: "entry_time", label: "Entry time", hint: "When the trade opened" },
  { key: "exit_time", label: "Exit time", hint: "When the trade closed" },
  { key: "symbol", label: "Market / symbol", hint: "The asset traded" },
  { key: "side", label: "Direction", hint: "Long or short" },
  { key: "quantity", label: "Amount", hint: "How much was traded" },
  { key: "entry_price", label: "Entry price", hint: "Price when it opened" },
  { key: "exit_price", label: "Exit price", hint: "Price when it closed" },
] as const;

const prettyBytes = (bytes: number) => {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const fieldLabel = (field: string) => field.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function ImportWizard({ onClose, onImported, initialFile = null }: Props) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef(0);
  const initialFileRef = useRef<File | null>(null);
  const mountedRef = useRef(true);
  const importingRef = useRef(false);
  const onCloseRef = useRef(onClose);
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issues, setIssues] = useState<ValidationIssue[]>([]);
  const [result, setResult] = useState<Strategy | null>(null);
  const [assumptionsOpen, setAssumptionsOpen] = useState(false);

  onCloseRef.current = onClose;
  importingRef.current = importing;

  const requiredFields = useMemo(() => (form.kind === "positions" ? POSITION_FIELDS : TRADE_FIELDS), [form.kind]);
  const hasErrors = issues.some((issue) => issue.severity === "error");
  const assumptionErrors = issues.some((issue) => issue.severity === "error" && ["invalid_fee", "invalid_slippage"].includes(issue.code));

  useEffect(() => {
    mountedRef.current = true;
    const previousActive = document.activeElement as HTMLElement | null;
    const getFocusable = () => Array.from(
      dialogRef.current?.querySelectorAll<HTMLElement>(
        "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]",
      ) ?? [],
    ).filter((element) => {
      const style = window.getComputedStyle(element);
      return style.display !== "none" && style.visibility !== "hidden" && element.getClientRects().length > 0 && !element.hasAttribute("aria-hidden");
    });
    const focusDialog = window.setTimeout(() => {
      const first = getFocusable()[0];
      (first ?? dialogRef.current)?.focus();
    }, 0);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (importingRef.current) return;
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = getFocusable();
      if (!focusable.length) {
        event.preventDefault();
        dialogRef.current.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialogRef.current)) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      mountedRef.current = false;
      requestRef.current += 1;
      window.clearTimeout(focusDialog);
      document.removeEventListener("keydown", onKeyDown);
      if (previousActive?.isConnected) previousActive.focus?.();
    };
  }, []);

  const resetForFile = useCallback((nextFile: File) => {
    requestRef.current += 1;
    setFile(nextFile);
    setPreview(null);
    setMapping({});
    setIssues([]);
    setError(null);
    setResult(null);
    setStep(1);
    setForm((current) => ({ ...DEFAULT_FORM, kind: current.kind }));
  }, []);

  const previewFile = useCallback(
    async (nextFile: File) => {
      const requestId = requestRef.current;
      if (!nextFile.name.toLowerCase().match(/\.(csv|parquet|pq)$/)) {
        setError("Choose a CSV or Parquet file.");
        return;
      }
      if (nextFile.size > MAX_UPLOAD_BYTES) {
        setError("This file is larger than 10 MB. Export a bounded backtest window and try again.");
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const response = await api.preview(nextFile);
        if (!mountedRef.current || requestRef.current !== requestId) return;
        setPreview(response);
        setMapping(response.suggested_mapping ?? {});
        setForm((current) => ({
          ...current,
          name: current.name || nextFile.name.replace(/\.(csv|parquet|pq)$/i, "").replaceAll("_", " "),
          kind: response.detected_kind || current.kind,
        }));
        setIssues(response.issues ?? []);
        setStep(2);
      } catch (previewError) {
        if (!mountedRef.current || requestRef.current !== requestId) return;
        setError(previewError instanceof Error ? previewError.message : "We could not inspect this file.");
      } finally {
        if (mountedRef.current && requestRef.current === requestId) setLoading(false);
      }
    },
    [],
  );

  const chooseFile = useCallback(
    (candidate: File | undefined) => {
      if (!candidate) return;
      resetForFile(candidate);
      void previewFile(candidate);
    },
    [previewFile, resetForFile],
  );

  useEffect(() => {
    if (!initialFile || initialFileRef.current === initialFile) return;
    const startPreview = window.setTimeout(() => {
      if (initialFileRef.current === initialFile) return;
      initialFileRef.current = initialFile;
      chooseFile(initialFile);
    }, 0);
    return () => window.clearTimeout(startPreview);
  }, [chooseFile, initialFile]);

  const updateForm = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    if (key === "kind" && preview) {
      setMapping((current) => {
        const fields = value === "positions" ? POSITION_FIELDS : TRADE_FIELDS;
        return Object.fromEntries(fields.map(({ key: field }) => [field, current[field] ?? ""]));
      });
      setIssues([]);
    }
  };

  const importStrategy = async () => {
    if (!preview || !file) return;
    const nextIssues: ValidationIssue[] = [];
    if (!form.name.trim()) nextIssues.push({ severity: "error", code: "missing_name", message: "Give this strategy a name." });
    if (!form.symbol.trim()) nextIssues.push({ severity: "error", code: "missing_symbol", message: "Add the instrument symbol." });
    for (const field of requiredFields) {
      if (!mapping[field.key]) nextIssues.push({ severity: "error", code: `missing_${field.key}`, message: `Map ${field.label.toLowerCase()} before importing.` });
    }
    const fee = Number(form.fee_bps);
    const slippage = Number(form.slippage_bps);
    if (!form.fee_bps.trim() || !Number.isFinite(fee) || fee < 0 || fee > 10_000) nextIssues.push({ severity: "error", code: "invalid_fee", message: "Enter a non-negative fee in basis points." });
    if (!form.slippage_bps.trim() || !Number.isFinite(slippage) || slippage < 0 || slippage > 10_000) nextIssues.push({ severity: "error", code: "invalid_slippage", message: "Enter a non-negative slippage value in basis points." });
    if (nextIssues.length) {
      setIssues(nextIssues);
      return;
    }
    setImporting(true);
    setError(null);
    const request: ImportRequest = {
      upload_id: preview.upload_id,
      name: form.name.trim(),
      symbol: form.symbol.trim().toUpperCase(),
      timeframe: form.timeframe.trim() || "1h",
      strategy_version: form.strategy_version.trim() || "v1",
      kind: form.kind,
      mapping,
      timezone: form.timezone,
      fee_bps: fee,
      slippage_bps: slippage,
      description: form.description.trim(),
    };
    try {
      const response: ImportResult = await api.importStrategy(request);
      setIssues(response.issues ?? []);
      if (!response.valid || !response.strategy) {
        setError("The file needs a few fixes before it can enter the research workspace.");
        return;
      }
      setResult(response.strategy);
      setStep(3);
      onImported(response.strategy);
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : "The import could not be completed.");
    } finally {
      setImporting(false);
    }
  };

  const renderIssues = () => {
    if (!issues.length) return null;
    return (
      <div className={`iw-issues ${hasErrors ? "iw-issues-error" : "iw-issues-warning"}`} role="alert">
        <AlertTriangle size={16} aria-hidden="true" />
        <div>
          <strong>{hasErrors ? "Needs attention" : "Review before continuing"}</strong>
          <ul>
            {issues.slice(0, 8).map((issue, index) => (
              <li key={`${issue.code}-${index}`}>{issue.message}{issue.row ? ` (row ${issue.row})` : ""}</li>
            ))}
          </ul>
        </div>
      </div>
    );
  };

  return (
    <div className="iw-backdrop" role="presentation" onMouseDown={(event) => { if (!importingRef.current && event.target === event.currentTarget) onCloseRef.current(); }}>
      <div
        className="iw-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        ref={dialogRef}
      >
        <header className="iw-header">
          <div>
            <div className="iw-eyebrow"><span className="iw-eyebrow-dot" /> Strategy intake</div>
            <h2 id={titleId}>{step === 3 ? "Strategy ready for research" : "Bring your strategy"}</h2>
            <p id={descriptionId}>
              {step === 3 ? "Your original file is saved for research." : "Upload the history your team already uses."}
            </p>
          </div>
          <button className="iw-icon-button" type="button" aria-label="Close import dialog" disabled={importing} onClick={() => onCloseRef.current()}><X size={19} /></button>
        </header>

        <div className="iw-steps" aria-label="Import progress">
          {["Upload", "Match & review", "Ready"].map((label, index) => {
            const number = index + 1;
            const completed = step > number;
            return (
              <div className={`iw-step ${step === number ? "iw-step-active" : ""} ${completed ? "iw-step-done" : ""}`} key={label}>
                <span className="iw-step-number">{completed ? <Check size={14} /> : number}</span>
                <span>{label}</span>
              </div>
            );
          })}
        </div>

        <main className="iw-body">
          {error && <div className="iw-error" role="alert"><AlertTriangle size={16} /><span>{error}</span></div>}

          {step === 1 && (
            <section className="iw-upload-section" aria-labelledby={`${titleId}-upload`}>
              <div className="iw-section-heading">
                <div><h3 id={`${titleId}-upload`}>Choose your strategy file</h3><p>CSV or Parquet. Position history is testable; completed trades are diagnosis only.</p></div>
                <FileSpreadsheet className="iw-heading-icon" size={23} aria-hidden="true" />
              </div>
              <div
                className={`iw-dropzone ${dragging ? "iw-dropzone-active" : ""} ${loading ? "iw-dropzone-loading" : ""}`}
                onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files?.[0]); }}
              >
                <input ref={inputRef} className="iw-visually-hidden" type="file" accept=".csv,.parquet,.pq,text/csv" onChange={(event) => chooseFile(event.target.files?.[0])} />
                <div className="iw-upload-icon"><UploadCloud size={23} /></div>
                {loading ? <><h3>Inspecting your file…</h3><Loader2 className="iw-spin" size={18} /></> : <><h3>Drop your strategy export</h3><p><button className="iw-upload-cta kk-primary-button" type="button" onClick={() => inputRef.current?.click()}>Choose a CSV or Parquet file</button></p></>}
                <span className="iw-upload-note">Example: positions.csv · timestamp, symbol, allocation</span>
              </div>
              {file && <div className="iw-active-file"><div className="iw-active-file-icon"><FileSpreadsheet size={16} /></div><div><span>Active file</span><strong>{file.name}</strong><small>{prettyBytes(file.size)}{loading ? " · inspecting columns…" : " · ready to configure"}</small></div></div>}
              <div className="iw-source-row">
                <Info size={15} aria-hidden="true" />
                <span>Need a reference? Start with a sample.</span>
              </div>
              <div className="iw-template-card">
                <div><strong>Sample files</strong><span>Check the expected columns before uploading.</span></div>
                <div className="iw-template-links"><a href={API_ROUTES.positionTemplate} download><Download size={14} /> Position history</a><a href={API_ROUTES.tradeTemplate} download><Download size={14} /> Trade history</a></div>
              </div>
            </section>
          )}

          {step === 2 && preview && (
            <section aria-labelledby={`${titleId}-map`}>
              <div className="iw-section-heading"><div><h3 id={`${titleId}-map`}>Match your columns</h3><p>{preview.row_count.toLocaleString()} rows · {preview.columns.length} columns · <strong>{file?.name}</strong></p></div><span className="iw-file-chip"><FileSpreadsheet size={14} /> {file ? prettyBytes(file.size) : ""}</span></div>
              <div className="iw-kind-toggle" role="group" aria-label="Input type">
                <button type="button" aria-pressed={form.kind === "positions"} className={form.kind === "positions" ? "iw-kind-selected" : ""} onClick={() => updateForm("kind", "positions")}><span>Position history <b className="iw-recommended">Recommended</b></span><small>Allocation at each timestamp · testable</small></button>
                <button type="button" aria-pressed={form.kind === "trades"} className={form.kind === "trades" ? "iw-kind-selected" : ""} onClick={() => updateForm("kind", "trades")}><span>Trade history</span><small>Completed trades · diagnosis only</small></button>
              </div>
              <div className="iw-map-grid">
                <div className="iw-map-fields">
                  <div className="iw-subheading"><span>Columns to match</span><span className="iw-subheading-note">{requiredFields.length} fields</span></div>
                  {requiredFields.map((field) => (
                    <label className="iw-map-field" key={field.key}>
                      <span><strong>{field.label}</strong><small>{field.hint}</small></span>
                      <select aria-invalid={issues.some((issue) => issue.severity === "error" && issue.code === `missing_${field.key}`)} value={mapping[field.key] ?? ""} onChange={(event) => setMapping((current) => ({ ...current, [field.key]: event.target.value }))}>
                        <option value="">Select a column</option>
                        {preview.columns.map((column) => <option value={column} key={column}>{column}</option>)}
                      </select>
                      {issues.find((issue) => issue.severity === "error" && issue.code === `missing_${field.key}`) && <small className="iw-map-error">Choose a column for {field.label.toLowerCase()}.</small>}
                    </label>
                  ))}
                </div>
                <div className="iw-preview-card"><div className="iw-subheading"><span>Raw preview</span><span className="iw-subheading-note">first {Math.min(5, preview.rows.length)} rows</span></div><div className="iw-table-wrap"><table><thead><tr>{preview.columns.slice(0, 6).map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{preview.rows.slice(0, 5).map((row, rowIndex) => <tr key={rowIndex}>{preview.columns.slice(0, 6).map((column) => <td key={`${rowIndex}-${column}`}>{row[column] == null || row[column] === "" ? <span className="iw-null">—</span> : String(row[column])}</td>)}</tr>)}</tbody></table></div></div>
              </div>
              {renderIssues()}
              <div className="iw-subheading iw-details-heading"><span>About this strategy</span><span className="iw-subheading-note">saved with this file</span></div>
              <div className="iw-form-grid iw-core-form-grid">
                <label><span>Strategy name <em>*</em></span><input value={form.name} onChange={(event) => updateForm("name", event.target.value)} placeholder="e.g. BTC trend v1" /></label>
                <label><span>Market / symbol <em>*</em></span><input value={form.symbol} onChange={(event) => updateForm("symbol", event.target.value)} placeholder="BTCUSDT" /></label>
                <label><span>How often is it recorded?</span><select value={form.timeframe} onChange={(event) => updateForm("timeframe", event.target.value)}><option>1m</option><option>5m</option><option>15m</option><option>1h</option><option>4h</option><option>1d</option></select></label>
              </div>
              <details className="iw-assumptions" open={assumptionsOpen || assumptionErrors} onToggle={(event) => setAssumptionsOpen(event.currentTarget.open)}>
                <summary><span><strong>Assumptions: costs, timing &amp; version</strong><small>Example costs are shown up front; edit them if you know your venue details.</small></span><b>Example: {form.timezone} · fee {form.fee_bps || "—"} bps · slippage {form.slippage_bps || "—"} bps</b></summary>
                <div className="iw-form-grid iw-assumptions-grid">
                  <label><span>Strategy version</span><input value={form.strategy_version} onChange={(event) => updateForm("strategy_version", event.target.value)} placeholder="v1.0.0 or git SHA" /><small>A label to help you find this version later.</small></label>
                  <label><span>Timestamp timezone</span><select value={form.timezone} onChange={(event) => updateForm("timezone", event.target.value)}><option>UTC</option><option>Europe/London</option><option>America/New_York</option><option>Asia/Singapore</option></select><small>Used when timestamps do not include a timezone.</small></label>
                  <label><span>Trading fee (bps)</span><input inputMode="decimal" type="number" min="0" step="0.1" value={form.fee_bps} onChange={(event) => updateForm("fee_bps", event.target.value)} /><small>Example assumption: 5 bps. Replace it with the fee your venue charges.</small></label>
                  <label><span>Slippage (bps)</span><input inputMode="decimal" type="number" min="0" step="0.1" value={form.slippage_bps} onChange={(event) => updateForm("slippage_bps", event.target.value)} /><small>Example assumption: 3 bps. Replace it when you have a measured estimate.</small></label>
                  <label className="iw-wide"><span>Notes <small>optional</small></span><textarea rows={2} value={form.description} onChange={(event) => updateForm("description", event.target.value)} placeholder="Venue, assumptions, or the question you want the agents to investigate" /></label>
                </div>
              </details>
              <div className="iw-disclosure"><Info size={15} /><span>{form.kind === "trades" ? "Trade history is for diagnosis. Use position history to test an on/off policy." : "Your original strategy stays unchanged. Research uses the costs shown above."}</span></div>
            </section>
          )}

          {step === 3 && result && (
            <section className="iw-success" aria-labelledby={`${titleId}-success`}>
              <div className="iw-success-icon"><CheckCircle2 size={31} /></div>
              <h3 id={`${titleId}-success`}>{result.name} is ready</h3>
              <p>We stored {result.row_count.toLocaleString()} {result.kind === "positions" ? "position rows" : "completed trades"} for <strong>{result.symbol}</strong>. The original file remains the unchanged starting point for research.</p>
              <div className="iw-success-grid"><div><span>Input type</span><strong>{result.kind === "positions" ? "Position history" : "Trade history"}</strong></div><div><span>Date range</span><strong>{result.date_start.slice(0, 10)} → {result.date_end.slice(0, 10)}</strong></div><div><span>Version</span><strong>{result.strategy_version}</strong></div><div><span>Hash</span><strong>{result.dataset_hash.slice(0, 12)}…</strong></div></div>
              {result.kind === "trades" && <div className="iw-disclosure"><Info size={15} /><span>This file is ready for diagnostic research. Upload position history when you want to test a new on/off policy on unseen data.</span></div>}
            </section>
          )}
        </main>

        <footer className="iw-footer">
          {step === 1 && <><span className="iw-footer-hint">Source stays unchanged.</span><button className="iw-button iw-button-secondary" type="button" disabled={importing} onClick={() => onCloseRef.current()}>Cancel</button></>}
          {step === 2 && <><button className="iw-button iw-button-ghost" type="button" disabled={importing} onClick={() => { setStep(1); setError(null); }}><ArrowLeft size={16} /> Replace file</button><div className="iw-footer-actions"><button className="iw-button iw-button-secondary" type="button" disabled={importing} onClick={() => onCloseRef.current()}>Cancel</button><button className="iw-button iw-button-primary kk-primary-button" type="button" disabled={importing || !preview} onClick={() => void importStrategy()}>{importing ? <><Loader2 className="iw-spin" size={16} /> Validating…</> : <>Import strategy <ArrowRight size={16} /></>}</button></div></>}
          {step === 3 && <><span className="iw-footer-hint">Next: investigate this strategy.</span><button className="iw-button iw-button-primary kk-primary-button" type="button" onClick={onClose}>Open research workspace <ArrowRight size={16} /></button></>}
        </footer>
      </div>
    </div>
  );
}
