"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ArrowDown, ArrowUpRight, Pause, Play, RotateCcw } from "lucide-react";
import type { Experiment } from "./types";
import "./strategy-entry.css";

type Props = {
  example: Experiment | null;
  onImport: (file?: File) => void;
  onExample: () => void;
  onResume?: () => void;
};

// This is a playback of the existing example's points, never a generated return curve.
function ExamplePlayback({ example }: { example: Experiment | null }) {
  const clipId = useId().replace(/:/g, "");
  const root = useRef<HTMLDivElement>(null);
  const clip = useRef<SVGRectElement>(null);
  const date = useRef<HTMLSpanElement>(null);
  const cursor = useRef<SVGGElement>(null);
  const progress = useRef(0);
  const [playing, setPlaying] = useState(true);
  const [finished, setFinished] = useState(false);
  const [reduced, setReduced] = useState(false);
  const points = useMemo(() => {
    const rows = (example?.mode === "demo" ? example.equity : []).filter(row => Number.isFinite(row.base) && Number.isFinite(row.proposed) && Number.isFinite(Date.parse(row.date)));
    if (rows.length < 2) return [];
    const low = Math.min(...rows.flatMap(row => [row.base, row.proposed]));
    const high = Math.max(...rows.flatMap(row => [row.base, row.proposed]));
    const from = Date.parse(rows[0].date);
    const duration = Date.parse(rows[rows.length - 1].date) - from || 1;
    return rows.map(row => ({
      date: row.date,
      x: 8 + (Date.parse(row.date) - from) / duration * 984,
      base: 237 - (row.base - low) / (high - low || 1) * 205,
      proposed: 237 - (row.proposed - low) / (high - low || 1) * 205,
    }));
  }, [example]);
  const path = (key: "base" | "proposed") => points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(2)},${point[key].toFixed(2)}`).join(" ");
  const area = points.length ? `${path("proposed")} L992,260 L8,260 Z` : "";

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const app = root.current?.closest(".kk-app");
    const update = () => setReduced(app?.getAttribute("data-motion") === "reduced" || (app?.getAttribute("data-motion") !== "full" && media.matches));
    update();
    media.addEventListener("change", update);
    const observer = new MutationObserver(update);
    if (app) observer.observe(app, { attributes: true, attributeFilter: ["data-motion"] });
    return () => { media.removeEventListener("change", update); observer.disconnect(); };
  }, []);

  useEffect(() => {
    if (!points.length) return;
    let frame = 0;
    let previous = 0;
    let lastIndex = -1;
    const paint = () => {
      const x = 8 + progress.current * 984;
      clip.current?.setAttribute("width", String(x));
      const index = points.findLastIndex(point => point.x <= x);
      const point = points[Math.max(0, index)];
      // Mark the last recorded point, without inventing values between observations.
      cursor.current?.setAttribute("transform", `translate(${point.x},${point.proposed})`);
      if (index !== lastIndex && date.current) {
        lastIndex = index;
        date.current.textContent = new Date(point.date).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
      }
    };
    if (reduced) { progress.current = 1; paint(); return; }
    paint();
    if (!playing) return;
    const tick = (time: number) => {
      if (previous) progress.current = Math.min(1, progress.current + Math.min(time - previous, 80) / 12000);
      previous = time;
      paint();
      if (progress.current < 1) frame = requestAnimationFrame(tick);
      else { setPlaying(false); setFinished(true); }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, points, reduced]);

  const togglePlayback = () => {
    if (finished) { progress.current = 0; setFinished(false); setPlaying(true); }
    else setPlaying(value => !value);
  };

  return <div className="se-playback" ref={root}>
    {points.length > 0 && <>
      <div className="se-example-label">Example <span>original + filtered</span></div>
      <svg className="se-graph" viewBox="0 0 1000 260" preserveAspectRatio="none" role="img" aria-label="Animated playback of the recorded example: original strategy and suggested filter. Illustrative data, not live performance.">
        <defs><clipPath id={clipId}><rect ref={clip} width="0" height="260" /></clipPath></defs>
        <g clipPath={`url(#${clipId})`}>
          <path d={area} fill="#F47735" fillOpacity="0.035" />
          <path d={path("base")} fill="none" stroke="#B4AEA5" strokeWidth="1.35" vectorEffect="non-scaling-stroke" />
          <path d={path("proposed")} fill="none" stroke="#F47735" strokeWidth="1.8" vectorEffect="non-scaling-stroke" />
        </g>
        <g ref={cursor} transform={`translate(${points[0].x},${points[0].proposed})`}><circle r="3" fill="#F47735" /></g>
      </svg>
    </>}
    <div className="se-playback-meta"><span>Example data · not a live result</span><span ref={date} className="se-date" />{points.length > 0 && !reduced && <button type="button" onClick={togglePlayback} aria-label={finished ? "Replay example animation" : playing ? "Pause example animation" : "Play example animation"}>{finished ? <RotateCcw size={14} /> : playing ? <Pause size={14} /> : <Play size={14} />}</button>}</div>
  </div>;
}

export default function StrategyEntry({ example, onImport, onExample, onResume }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const dragCount = useRef(0);
  return <section className={`se-entry ${dragging ? "se-dragging" : ""}`} aria-labelledby="se-title"
    onDragEnter={event => { event.preventDefault(); dragCount.current++; setDragging(true); }}
    onDragOver={event => event.preventDefault()}
    onDragLeave={event => { event.preventDefault(); if (--dragCount.current <= 0) setDragging(false); }}
    onDrop={event => { event.preventDefault(); dragCount.current = 0; setDragging(false); const file = event.dataTransfer.files[0]; if (file) onImport(file); }}>
    <div className="se-topline"><p>Start with your strategy.</p><span>01 / Import</span></div>
    <div className="se-invitation">
      <h1 id="se-title">{dragging ? "Let’s take a look." : "Drop your strategy."}</h1>
      <p>CSV or Parquet <span>· signals or positions</span></p>
      <div className="se-direction" aria-hidden="true"><span /><ArrowDown size={20} /></div>
      <button className="se-choose" type="button" onClick={() => input.current?.click()}>Choose file <ArrowUpRight size={25} /></button>
      <button className="se-example" type="button" onClick={onExample}>Try an example</button>
      <input ref={input} type="file" accept=".csv,.parquet,.pq" className="se-file" tabIndex={-1} aria-label="Choose a strategy file" onChange={event => { const file = event.target.files?.[0]; if (file) onImport(file); event.target.value = ""; }} />
    </div>
    <ExamplePlayback example={example} />
    <footer className="se-footer">{onResume ? <button type="button" className="se-resume" onClick={onResume}>Your workspace <ArrowUpRight size={14} /></button> : <span />}<ol aria-label="Strategy workflow"><li aria-current="step">Import</li><li aria-hidden="true">→</li><li>Check data</li><li aria-hidden="true">→</li><li>Explore</li></ol></footer>
  </section>;
}
