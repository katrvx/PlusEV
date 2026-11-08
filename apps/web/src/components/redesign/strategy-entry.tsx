"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ArrowDown, ArrowUpRight, Pause, Play, RotateCcw } from "lucide-react";
import type { Experiment } from "./types";
import { monotonePath } from "./chart-path";
import { MagneticAction, useInterfaceReducedMotion } from "./ui-motion";
import KineticText from "./kinetic-text";
import ResearchStory from "./research-story";
import { MascotDuo } from "./mascot";
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
  const reduced = useInterfaceReducedMotion();
  const [visible, setVisible] = useState(false);
  const points = useMemo(() => {
    const rows = (example?.mode === "demo" ? example.equity : [])
      .filter(row => Number.isFinite(row.base) && Number.isFinite(row.proposed) && Number.isFinite(Date.parse(row.date)))
      .sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
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
  const path = (key: "base" | "proposed") => monotonePath(points.map(point => ({ x: point.x, y: point[key] })));
  const area = points.length ? `${path("proposed")} L992,260 L8,260 Z` : "";

  useEffect(() => {
    const element = root.current;
    if (!element) return;
    let inView = false;
    const update = () => setVisible(inView && !document.hidden);
    const observer = new IntersectionObserver(([entry]) => { inView = entry.isIntersecting; update(); });
    observer.observe(element);
    document.addEventListener("visibilitychange", update);
    return () => { observer.disconnect(); document.removeEventListener("visibilitychange", update); };
  }, []);

  useEffect(() => {
    progress.current = 0;
    setFinished(false);
    setPlaying(true);
  }, [points]);

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
    if (reduced) { progress.current = 1; paint(); setPlaying(false); setFinished(true); return; }
    paint();
    if (!playing || !visible) return;
    const tick = (time: number) => {
      if (previous) progress.current = Math.min(1, progress.current + Math.min(time - previous, 80) / 8500);
      previous = time;
      paint();
      if (progress.current < 1) frame = requestAnimationFrame(tick);
      else { setPlaying(false); setFinished(true); }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, points, reduced, visible]);

  const togglePlayback = () => {
    if (finished) { progress.current = 0; setFinished(false); setPlaying(true); }
    else setPlaying(value => !value);
  };

  if (!points.length) {
    return <ol className="se-process-cue" aria-label="Verification workflow">
      <li>Agents propose</li><li>Code tests</li><li>Human approves</li>
    </ol>;
  }

  return <div className="se-playback" ref={root}>
    {points.length > 0 && <>
      <div className="se-example-label"><span className="se-series-original">Original</span><span className="se-series-filtered">With a filter</span></div>
      <svg className="se-graph" viewBox="0 0 1000 260" preserveAspectRatio="none" role="img" aria-label="Animated playback of the recorded example: original strategy and suggested filter. Illustrative data, not live performance.">
        <defs><clipPath id={clipId}><rect ref={clip} width="0" height="260" /></clipPath></defs>
        <g clipPath={`url(#${clipId})`}>
          <path d={area} fill="var(--kk-accent)" fillOpacity="0.045" />
          <path d={path("base")} fill="none" stroke="var(--kk-original)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
          <path d={path("proposed")} fill="none" stroke="var(--kk-accent)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        </g>
        <g ref={cursor} transform={`translate(${points[0].x},${points[0].proposed})`}><circle r="3" fill="var(--kk-accent)" /></g>
      </svg>
    </>}
    <div className="se-playback-meta"><span>Example data · not a live result</span><span ref={date} className="se-date" />{!reduced && <button type="button" onClick={togglePlayback} aria-label={finished ? "Replay example animation" : playing ? "Pause example animation" : "Play example animation"}>{finished ? <RotateCcw size={14} /> : playing ? <Pause size={14} /> : <Play size={14} />}</button>}</div>
  </div>;
}

export default function StrategyEntry({ example, onImport, onExample, onResume }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const dragCount = useRef(0);
  return <div className="se-landing"><section className={`se-entry ${dragging ? "se-dragging" : ""}`} aria-labelledby="se-title"
    onDragEnter={event => { event.preventDefault(); dragCount.current++; setDragging(true); }}
    onDragOver={event => event.preventDefault()}
    onDragLeave={event => { event.preventDefault(); if (--dragCount.current <= 0) setDragging(false); }}
    onDrop={event => { event.preventDefault(); dragCount.current = 0; setDragging(false); const file = event.dataTransfer.files[0]; if (file) onImport(file); }}>
    <div className="se-topline"><p aria-label="+EV"><span>+</span>EV</p><div><a href="#research-story">How it works <ArrowDown size={15} /></a>{onResume && <button type="button" className="se-resume" onClick={onResume}>Your workspace <ArrowUpRight size={16} /></button>}</div></div>
    <div className="se-hero-grid">
      <div className="se-invitation">
        <p className="se-kicker">Strategy verification · evidence before action</p>
        <h1 id="se-title" key={dragging ? "drop" : "ready"}>{dragging ? <KineticText trigger="mount">Let’s take a look.</KineticText> : <><KineticText trigger="mount">Good strategy.</KineticText><br /><KineticText trigger="mount" delay={0.16} className="se-title-accent">Wrong market?</KineticText></>}</h1>
        <p className="se-intro">See when a strategy works, why, and what verdict the evidence supports.</p>
        <div className="se-actions"><MagneticAction><button className="se-choose kk-primary-button" type="button" onClick={onExample}>Try an example <ArrowUpRight size={20} /></button></MagneticAction><button className="se-example" type="button" onClick={() => onImport()}>Verify your strategy <ArrowUpRight size={18} /></button></div>
        <input ref={input} type="file" accept=".json,application/json" className="se-file" tabIndex={-1} aria-label="Choose an optional strategy rules JSON file" onChange={event => { const file = event.target.files?.[0]; if (file) onImport(file); event.target.value = ""; }} />
      </div>
      <div className="se-hero-scene" aria-label="A conceptual strategy path: it climbs in a clear trend, then becomes choppy. This illustration is not performance data.">
        <div className="se-hero-note se-hero-note-bull">The rule works <strong>when it fits.</strong></div>
        <svg className="se-hero-chart" viewBox="0 0 640 280" role="img" aria-hidden="true"><path d="M34 230 C82 222 110 190 152 197 S222 165 264 133 S318 96 360 111 S407 184 445 161 S491 190 528 147 S576 172 610 138" /><path className="se-hero-chart-dot" d="M360 111v-30" /></svg>
        <MascotDuo className="se-hero-duo" />
        <span className="se-hero-caption">A conceptual strategy path · not live performance</span>
      </div>
    </div>
    <div className="se-hero-mark" aria-hidden="true"><svg viewBox="0 0 500 110" fill="none"><path pathLength="1" d="M10 82 C90 82 106 18 174 40 S259 109 325 55 S414 12 490 26" /></svg></div>
    <a className="se-scroll-cue" href="#research-story"><span>See how we find out</span><ArrowDown size={18} /></a>
  </section><ResearchStory example={example} playback={<ExamplePlayback example={example} />} onImport={onImport} onExample={onExample} /></div>;
}
