"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { ChevronRight, FileSearch } from "lucide-react";
import type { TeamEvidence } from "../../../../packages/contracts/research";
import "./research-source-browser.css";

export type ResearchSourceBrowserProps = {
  /** The complete recorded source set. The browser never derives new output. */
  evidence: TeamEvidence[];
  /** When a finding links into this view, select and reveal the matching source. */
  focusedEvidence?: string | null;
  /** Optional bridge for a parent that tracks the selected source in URL/state. */
  onSelectEvidence?: (evidenceId: string) => void;
};

const toolLabels: Record<string, string> = {
  arbiter_evaluate: "Independent comparison",
  cost_attribution: "Cost attribution",
  feature_grid: "Feature coverage",
  regime_performance: "Condition performance",
  sentiment_episodes: "Sentiment episodes",
  strategy_health: "Strategy health",
  test_gate_train: "Candidate rule check",
  walk_forward_fold: "Walk-forward check",
};

const toolLabel = (tool: string) => toolLabels[tool] || tool.replaceAll("_", " ").replace(/\b\w/g, character => character.toUpperCase());
const prettyDate = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" });
};
const rawJson = (value: unknown) => JSON.stringify(value, null, 2);

function moveSelection(event: KeyboardEvent<HTMLButtonElement>, index: number, count: number, select: (index: number) => void) {
  if (count < 2) return;
  let next = index;
  if (event.key === "ArrowDown" || event.key === "ArrowRight") next = (index + 1) % count;
  else if (event.key === "ArrowUp" || event.key === "ArrowLeft") next = (index - 1 + count) % count;
  else if (event.key === "Home") next = 0;
  else if (event.key === "End") next = count - 1;
  else return;
  event.preventDefault();
  select(next);
}

export default function ResearchSourceBrowser({ evidence, focusedEvidence = null, onSelectEvidence }: ResearchSourceBrowserProps) {
  const panelRef = useRef<HTMLElement>(null);
  const firstId = evidence[0]?.evidence_id || "";
  const initialId = focusedEvidence && evidence.some(item => item.evidence_id === focusedEvidence) ? focusedEvidence : firstId;
  const [selectedId, setSelectedId] = useState(initialId);
  const selected = useMemo(() => evidence.find(item => item.evidence_id === selectedId) || evidence[0] || null, [evidence, selectedId]);

  const selectAt = (index: number, reveal = false) => {
    const item = evidence[index];
    if (!item) return;
    setSelectedId(item.evidence_id);
    onSelectEvidence?.(item.evidence_id);
    if (reveal) requestAnimationFrame(() => document.getElementById(`research-source-${item.evidence_id}`)?.focus());
  };

  useEffect(() => {
    setSelectedId(current => focusedEvidence && evidence.some(item => item.evidence_id === focusedEvidence)
      ? focusedEvidence : evidence.some(item => item.evidence_id === current) ? current : firstId);
    if (focusedEvidence && evidence.some(item => item.evidence_id === focusedEvidence)) {
      const frame = requestAnimationFrame(() => { panelRef.current?.scrollIntoView({ block: "nearest", behavior: "instant" }); panelRef.current?.focus({ preventScroll: true }); });
      return () => cancelAnimationFrame(frame);
    }
  }, [evidence, firstId, focusedEvidence]);

  if (!selected) return <section className="research-source-browser" aria-label="Recorded source evidence"><div className="rsb-empty"><FileSearch size={20} /><strong>No recorded sources</strong><p>This report did not attach source records.</p></div></section>;

  return <section className="research-source-browser" aria-label="Recorded source evidence">
    <div className="rsb-heading"><div><span className="eyebrow">TRACEABLE RESEARCH</span><h2>Show me the source.</h2><p>Choose one recorded check. Its exact arguments and output stay visible beside the list.</p></div><span className="rsb-count">{evidence.length} sources</span></div>
    <div className="rsb-layout">
      <div className="rsb-source-list" role="tablist" aria-label="Recorded source checks">
        {evidence.map((item, index) => <button id={`research-source-${item.evidence_id}`} key={item.evidence_id} type="button" role="tab" tabIndex={item.evidence_id === selected.evidence_id ? 0 : -1} aria-selected={item.evidence_id === selected.evidence_id} aria-controls="research-source-panel" className={item.evidence_id === selected.evidence_id ? "selected" : ""} onClick={() => selectAt(index)} onKeyDown={event => moveSelection(event, index, evidence.length, nextIndex => selectAt(nextIndex, true))}>
          <span className="rsb-source-icon" aria-hidden="true"><FileSearch size={15} /></span><span className="rsb-source-copy"><strong>{toolLabel(item.tool)}</strong><small>{item.evidence_id}</small></span><ChevronRight size={15} aria-hidden="true" />
        </button>)}
      </div>
      <article id="research-source-panel" ref={panelRef} className="rsb-source-panel" role="tabpanel" aria-labelledby={`research-source-${selected.evidence_id}`} tabIndex={-1}>
        <header className="rsb-panel-heading"><div><span className="eyebrow">SELECTED SOURCE</span><h3>{toolLabel(selected.tool)}</h3><p><code>{selected.evidence_id}</code> · {prettyDate(selected.created_at)}</p></div><span className="rsb-panel-tool">{selected.tool}</span></header>
        <div className="rsb-raw-grid"><section><h4>Tool arguments</h4><pre tabIndex={0} aria-label="Recorded tool arguments">{rawJson(selected.args)}</pre></section><section><h4>Raw tool output</h4><pre tabIndex={0} aria-label="Recorded tool output">{rawJson(selected.payload)}</pre></section></div>
      </article>
    </div>
  </section>;
}
