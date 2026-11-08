"use client";

import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ChartSeries, ResearchChartProps } from "./types";
import { monotonePath } from "./chart-path";
export { monotonePath } from "./chart-path";
import "./research-chart.css";

type Point = { x: number; y: number; date: string; value: number };
type SeriesDef = { id: ChartSeries; label: string; color: string; dash?: string; width: number };

const SERIES: SeriesDef[] = [
  { id: "base", label: "Original strategy", color: "var(--kk-original, #38253c)", width: 3.5 },
  { id: "rule", label: "Simple rule", color: "var(--kk-simple, #9389df)", dash: "7 6", width: 2.5 },
  { id: "proposed", label: "Suggested filter", color: "var(--kk-chart-accent, #ff681b)", width: 4.5 },
  { id: "cash", label: "Cash", color: "var(--kk-cash, #847480)", dash: "2 7", width: 1.5 },
];
const revealedDatasets = new Set<string>();
const useIsomorphicLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

const isFiniteNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const dateMs = (value: string) => {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
};
const displayDate = (value: string) => {
  const parsed = dateMs(value);
  return parsed === null ? value : new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(parsed);
};
const displayTimestamp = (value: string) => {
  const parsed = dateMs(value);
  return parsed === null ? value : `${new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }).format(parsed)} UTC`;
};
const shortDate = (value: string) => {
  const parsed = dateMs(value);
  return parsed === null ? value : new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }).format(parsed);
};
const valueText = (value: number) => value.toFixed(2);

function finiteValue(row: ResearchChartProps["data"][number], id: ChartSeries) {
  const value = row[id];
  return isFiniteNumber(value) ? value : null;
}

function yTicks(min: number, max: number) {
  return Array.from({ length: 5 }, (_, index) => max - ((max - min) * index) / 4);
}

function overviewTicks(min: number, max: number) {
  return [max, (max + min) / 2, min];
}

function makeSegments(data: ResearchChartProps["data"], id: ChartSeries, xFor: (row: ResearchChartProps["data"][number], index: number) => number, yFor: (value: number) => number) {
  const segments: Point[][] = [];
  let current: Point[] = [];
  data.forEach((row, index) => {
    const value = finiteValue(row, id);
    const point = value === null ? null : { x: xFor(row, index), y: yFor(value), date: row.date, value };
    if (point) current.push(point);
    else if (current.length) { segments.push(current); current = []; }
  });
  if (current.length) segments.push(current);
  return segments;
}

function nearestIndex(data: ResearchChartProps["data"], x: number, xFor: (row: ResearchChartProps["data"][number], index: number) => number) {
  let nearest = 0;
  let distance = Number.POSITIVE_INFINITY;
  data.forEach((row, index) => {
    const next = Math.abs(xFor(row, index) - x);
    if (next < distance) { nearest = index; distance = next; }
  });
  return nearest;
}

export default function ResearchChart({ data, series = ["base", "rule", "proposed", "cash"], seriesLabels, selectedDate, onSelectDate, label = "Strategy value", mode, height, reveal = true, compact = false, presentation = "default" }: ResearchChartProps) {
  const areaGradientId = `kk-chart-area-${useId().replace(/:/g, "")}`;
  const rootRef = useRef<HTMLElement>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const dwellRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const leaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previousSelectedDateRef = useRef(selectedDate);
  const [chartSize, setChartSize] = useState({ width: 960, height: 420 });
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [pointerIndexState, setPointerIndexState] = useState<number | null>(null);
  const [pinnedIndex, setPinnedIndex] = useState<number | null>(null);
  const [showData, setShowData] = useState(false);
  const allowedSeries = useMemo(
    () => SERIES.filter(item => series.includes(item.id)).map(item => ({ ...item, label: seriesLabels?.[item.id] ?? item.label })),
    [series.join(","), seriesLabels?.base, seriesLabels?.rule, seriesLabels?.proposed, seriesLabels?.cash],
  );
  const allowedIds = allowedSeries.map(item => item.id);
  const [visibleSeries, setVisibleSeries] = useState<ChartSeries[]>(allowedIds);
  const [localSelectedDate, setLocalSelectedDate] = useState<string | null>(selectedDate ?? null);
  // Overview charts only show the original strategy and cash. Give the main
  // recorded series the accent and extra weight in that single-series mode;
  // comparison charts retain the neutral original-vs-filter palette.
  const emphasiseBase = !visibleSeries.includes("proposed");
  const colorFor = (item: SeriesDef) => item.id === "base" && emphasiseBase ? "var(--kk-chart-accent, #ff681b)" : item.color;
  const widthFor = (item: SeriesDef) => item.id === "base" && emphasiseBase ? 4.5 : item.width;

  useEffect(() => { setVisibleSeries(allowedIds); }, [allowedIds.join(",")]);
  useEffect(() => { setLocalSelectedDate(selectedDate ?? null); }, [selectedDate]);
  useEffect(() => {
    const propChanged = previousSelectedDateRef.current !== selectedDate;
    previousSelectedDateRef.current = selectedDate;
    if (!propChanged || pinnedIndex === null || selectedDate === undefined) return;
    const pinnedDate = data[pinnedIndex]?.date;
    if (selectedDate === null || selectedDate !== pinnedDate) setPinnedIndex(null);
  }, [data, pinnedIndex, selectedDate]);
  useIsomorphicLayoutEffect(() => {
    const element = chartRef.current;
    if (!element) return;
    const initialBox = element.getBoundingClientRect();
    if (initialBox.width > 0 || initialBox.height > 0) {
      setChartSize({ width: Math.max(1, Math.round(initialBox.width || 960)), height: Math.max(1, Math.round(initialBox.height || 420)) });
    }
    const observer = new ResizeObserver(entries => {
      const box = entries[0]?.contentRect;
      if (!box) return;
      const next = { width: Math.max(1, Math.round(box.width || 960)), height: Math.max(1, Math.round(box.height || 420)) };
      setChartSize(previous => previous.width === next.width && previous.height === next.height ? previous : next);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const clearOutside = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        if (dwellRef.current) clearTimeout(dwellRef.current);
        if (leaveRef.current) clearTimeout(leaveRef.current);
        setHoverIndex(null); setPointerIndexState(null); setPinnedIndex(null);
      }
    };
    document.addEventListener("pointerdown", clearOutside);
    return () => document.removeEventListener("pointerdown", clearOutside);
  }, []);
  useEffect(() => () => { if (dwellRef.current) clearTimeout(dwellRef.current); if (leaveRef.current) clearTimeout(leaveRef.current); }, []);

  const viewWidth = chartSize.width;
  const requestedHeight = height ?? (compact ? 280 : viewWidth < 760 ? 280 : 420);
  const chartHeight = viewWidth < 760 ? Math.min(requestedHeight, 300) : requestedHeight;
  const viewHeight = chartHeight;
  const plot = useMemo(() => {
    if (presentation === "overview") {
      return { left: viewWidth < 600 ? 28 : 36, right: viewWidth < 600 ? 18 : 28, top: 22, bottom: viewWidth < 600 ? 52 : 38 };
    }
    return { left: viewWidth < 600 ? 36 : 62, right: viewWidth < 600 ? 32 : 158, top: 28, bottom: viewWidth < 600 ? 70 : 47 };
  }, [presentation, viewWidth]);

  const metrics = useMemo(() => {
    const times = data.map(row => dateMs(row.date));
    const validTimes = times.filter((value): value is number => value !== null);
    const firstTime = validTimes[0] ?? 0;
    const lastTime = validTimes[validTimes.length - 1] ?? firstTime;
    const span = lastTime - firstTime || 1;
    const rawValues = data.flatMap(row => allowedSeries.flatMap(item => {
      const value = finiteValue(row, item.id);
      return value === null ? [] : [value];
    }));
    const minValue = rawValues.length ? Math.min(...rawValues, 100) : 0;
    const maxValue = rawValues.length ? Math.max(...rawValues, 100) : 100;
    const spread = Math.max(maxValue - minValue, 1);
    const yMin = minValue - spread * 0.09;
    const yMax = maxValue + spread * 0.09;
    const xFor = (row: ResearchChartProps["data"][number], index: number) => {
      const time = dateMs(row.date);
      const ratio = time === null ? (data.length <= 1 ? 0 : index / (data.length - 1)) : (time - firstTime) / span;
      return plot.left + Math.max(0, Math.min(1, ratio)) * (viewWidth - plot.left - plot.right);
    };
    const yFor = (value: number) => plot.top + (1 - (value - yMin) / (yMax - yMin)) * (viewHeight - plot.top - plot.bottom);
    return { yMin, yMax, xFor, yFor, ticks: presentation === "overview" ? overviewTicks(yMin, yMax) : yTicks(yMin, yMax) };
  }, [allowedSeries, data, plot, presentation, viewHeight, viewWidth]);

  const selectedIndex = useMemo(() => {
    const activeDate = localSelectedDate ?? selectedDate;
    if (!activeDate) return null;
    const index = data.findIndex(row => row.date === activeDate);
    return index >= 0 ? index : null;
  }, [data, localSelectedDate, selectedDate]);
  const activeIndex = pinnedIndex ?? selectedIndex ?? hoverIndex;
  const activeRow = activeIndex === null || !data[activeIndex] ? null : data[activeIndex];
  const readoutIndex = pinnedIndex ?? hoverIndex;
  const readoutRow = readoutIndex === null || !data[readoutIndex] ? null : data[readoutIndex];
  const readoutX = readoutRow && readoutIndex !== null ? metrics.xFor(readoutRow, readoutIndex) : null;
  const readoutValues = readoutRow ? allowedSeries.filter(item => visibleSeries.includes(item.id)).map(item => ({ ...item, color: colorFor(item), width: widthFor(item), value: finiteValue(readoutRow, item.id) })).filter((item): item is SeriesDef & { value: number } => item.value !== null) : [];
  const endLabels = useMemo(() => {
    const labels = allowedSeries.filter(item => visibleSeries.includes(item.id)).map(item => {
      const points = makeSegments(data, item.id, metrics.xFor, metrics.yFor).flat();
      const point = points[points.length - 1];
      return point ? { ...item, color: colorFor(item), width: widthFor(item), point, labelY: point.y } : null;
    }).filter((item): item is SeriesDef & { point: Point; labelY: number } => item !== null).sort((a, b) => a.labelY - b.labelY);
    for (let index = 1; index < labels.length; index += 1) {
      if (labels[index].labelY - labels[index - 1].labelY < 18) labels[index].labelY = labels[index - 1].labelY + 18;
    }
    const lower = viewHeight - plot.bottom - 4;
    const upper = plot.top + 4;
    if (labels.length && labels[labels.length - 1].labelY > lower) {
      const shift = labels[labels.length - 1].labelY - lower;
      labels.forEach(item => { item.labelY -= shift; });
    }
    labels.forEach(item => { item.labelY = Math.max(upper, Math.min(lower, item.labelY)); });
    return labels;
  }, [allowedSeries, data, metrics, plot, viewHeight, visibleSeries]);
  const datasetKey = useMemo(() => data.map(row => `${row.date}:${allowedSeries.map(item => String(row[item.id] ?? "")).join(",")}`).join("|"), [allowedSeries, data]);
  const shouldReveal = reveal && !revealedDatasets.has(datasetKey);
  useEffect(() => { if (reveal && datasetKey) revealedDatasets.add(datasetKey); }, [datasetKey, reveal]);

  const chooseIndex = (index: number, pin: boolean) => {
    if (!data.length) return;
    const safe = Math.max(0, Math.min(data.length - 1, index));
    setHoverIndex(safe);
    if (pin || pinnedIndex !== null) setPinnedIndex(safe);
    setLocalSelectedDate(data[safe].date);
    onSelectDate?.(data[safe].date);
  };
  const clearSelection = () => {
    if (dwellRef.current) clearTimeout(dwellRef.current);
    if (leaveRef.current) clearTimeout(leaveRef.current);
    setHoverIndex(null);
    setPointerIndexState(null);
    setPinnedIndex(null);
    setLocalSelectedDate(null);
    onSelectDate?.(null);
  };

  const pointerIndex = (event: { clientX: number; currentTarget: SVGRectElement }) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    const x = plot.left + ratio * (viewWidth - plot.left - plot.right);
    return nearestIndex(data, x, metrics.xFor);
  };
  const handlePointerMove = (event: React.PointerEvent<SVGRectElement>) => {
    if (dwellRef.current) clearTimeout(dwellRef.current);
    const index = pointerIndex(event);
    setPointerIndexState(index);
    dwellRef.current = setTimeout(() => setHoverIndex(index), 120);
  };
  const clearHover = () => {
    if (dwellRef.current) clearTimeout(dwellRef.current);
    if (leaveRef.current) clearTimeout(leaveRef.current);
    leaveRef.current = setTimeout(() => { setHoverIndex(null); setPointerIndexState(null); }, 140);
  };
  const keepReadout = () => { if (leaveRef.current) clearTimeout(leaveRef.current); };
  const handleKeyDown = (event: React.KeyboardEvent<SVGRectElement>) => {
    if (!data.length) return;
    const current = activeIndex ?? 0;
    if (event.key === "ArrowRight") { event.preventDefault(); chooseIndex(current + 1, false); }
    else if (event.key === "ArrowLeft") { event.preventDefault(); chooseIndex(current - 1, false); }
    else if (event.key === "Home") { event.preventDefault(); chooseIndex(0, false); }
    else if (event.key === "End") { event.preventDefault(); chooseIndex(data.length - 1, false); }
    else if (event.key === "Enter" || event.key === " ") { event.preventDefault(); chooseIndex(current, true); }
    else if (event.key === "Escape") { event.preventDefault(); clearSelection(); }
  };
  const handleRangeKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") { event.preventDefault(); clearSelection(); }
  };
  const downloadCsv = () => {
    const columns = ["date", ...allowedSeries.filter(item => visibleSeries.includes(item.id)).map(item => item.id)];
    const rows = data.map(row => columns.map(column => JSON.stringify(row[column as keyof typeof row] ?? "")).join(","));
    const blob = new Blob([[columns.join(","), ...rows].join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "keep-or-kill-chart-data.csv"; anchor.click(); URL.revokeObjectURL(url);
  };

  if (!data.length) return <section className="kk-chart kk-chart-empty" aria-label={label}><p>No measured series are available for this view.</p></section>;
  const guideIndex = pinnedIndex ?? pointerIndexState ?? hoverIndex ?? selectedIndex;
  const guideRow = guideIndex === null ? null : data[guideIndex];
  const guideX = guideRow && guideIndex !== null ? metrics.xFor(guideRow, guideIndex) : null;
  const narrow = viewWidth < 600;
  const readoutPlacement = readoutX !== null && readoutX < viewWidth * 0.28 ? "start" : readoutX !== null && readoutX > viewWidth * 0.72 ? "end" : "center";
  const readoutHint = mode === "demo" ? "Recorded example point" : "Actual observation";
  const showEndLabels = presentation !== "overview";
  const overviewPrimary = allowedSeries.find(item => item.id === "base" && visibleSeries.includes(item.id)) ?? allowedSeries.find(item => visibleSeries.includes(item.id));
  const overviewAreaSegments = useMemo(() => {
    if (presentation !== "overview" || !overviewPrimary) return [];
    return makeSegments(data, overviewPrimary.id, metrics.xFor, metrics.yFor);
  }, [data, metrics, overviewPrimary, presentation]);
  const overviewEndpoint = overviewAreaSegments.at(-1)?.at(-1) ?? null;
  const areaPath = (segment: Point[]) => {
    if (!segment.length) return "";
    const base = monotonePath(segment);
    const bottom = viewHeight - plot.bottom;
    const first = segment[0];
    const last = segment[segment.length - 1];
    return `${base} L${last.x.toFixed(2)} ${bottom.toFixed(2)} L${first.x.toFixed(2)} ${bottom.toFixed(2)} Z`;
  };
  const chartControls = <>
    <div className="kk-chart-controls">
      <div className="kk-chart-series-toggle" aria-label="Visible chart series">{allowedSeries.map(item => <label key={item.id} data-series={item.id}><input type="checkbox" checked={visibleSeries.includes(item.id)} onChange={() => setVisibleSeries(current => current.includes(item.id) ? current.filter(value => value !== item.id) : [...current, item.id])} /><i style={{ backgroundColor: colorFor(item) }} />{item.label}</label>)}</div>
      <div className="kk-chart-actions"><button type="button" className="kk-chart-link" onClick={() => setShowData(value => !value)}>{showData ? "Hide data" : "View data"}</button><button type="button" className="kk-chart-link" onClick={downloadCsv}>Download data</button></div>
    </div>
    {narrow && showEndLabels && <div className="kk-chart-narrow-labels" aria-label="Latest values">{endLabels.map(item => <span key={item.id}><i style={{ backgroundColor: item.color }} />{item.label}<b>{valueText(item.point.value)}</b></span>)}</div>}
    <label className="kk-chart-scrubber"><span>Select date</span><input type="range" min={0} max={Math.max(0, data.length - 1)} value={activeIndex ?? 0} onChange={event => chooseIndex(Number(event.target.value), true)} onKeyDown={handleRangeKeyDown} aria-label="Select an observation date" /><output>{activeRow ? displayDate(activeRow.date) : "No date selected"}</output></label>
    {showData && <div className="kk-chart-data"><table><caption>Actual chart observations</caption><thead><tr><th>Date</th>{allowedSeries.filter(item => visibleSeries.includes(item.id)).map(item => <th key={item.id}>{item.label}</th>)}</tr></thead><tbody>{data.map(row => <tr key={row.date}><th scope="row">{displayTimestamp(row.date)}</th>{allowedSeries.filter(item => visibleSeries.includes(item.id)).map(item => <td key={item.id}>{finiteValue(row, item.id) === null ? "—" : valueText(finiteValue(row, item.id) as number)}</td>)}</tr>)}</tbody></table></div>}
  </>;

  return <section ref={rootRef} className={`kk-chart ${compact ? "kk-chart-compact" : ""} ${presentation === "overview" ? "kk-chart-presentation-overview" : ""}`} style={{ "--kk-chart-height": `${chartHeight}px` } as React.CSSProperties} aria-label={label}>
    {presentation !== "overview" && <div className="kk-chart-toolbar">
      <div><span className="kk-chart-label">{label}</span><span className="kk-chart-unit">Value of 100 · indexed strategy value</span></div>
      <div className="kk-chart-scope">{mode === "demo" ? "Illustrative example" : mode === "pending" ? "Awaiting measured results" : "Measured result"}</div>
    </div>}
    <div className={`kk-chart-stage ${shouldReveal ? "kk-chart-reveal" : ""}`} ref={chartRef}>
      <svg viewBox={`0 0 ${viewWidth} ${viewHeight}`} preserveAspectRatio="none" role="group" aria-label={`${label} chart`}>
        {presentation === "overview" && overviewPrimary && overviewAreaSegments.length > 0 && <defs><linearGradient id={areaGradientId} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--kk-accent, #2454f4)" stopOpacity="0.14" /><stop offset="100%" stopColor="var(--kk-accent, #2454f4)" stopOpacity="0" /></linearGradient></defs>}
        <g className="kk-chart-grid" aria-hidden="true">
          {metrics.ticks.map((tick, index) => { const y = metrics.yFor(tick); return <g key={`y-${index}`}><line x1={plot.left} x2={viewWidth - plot.right} y1={y} y2={y} /><text className="kk-chart-y-tick" x={plot.left - 12} y={y + 4} textAnchor="end">{tick.toFixed(0)}</text></g>; })}
          {data.filter((_, index) => presentation === "overview" ? index === 0 || index === data.length - 1 : index === 0 || index === data.length - 1 || index === Math.floor((data.length - 1) / 2)).map((row, index) => <text className="kk-chart-x-tick" key={`x-${row.date}-${index}`} x={metrics.xFor(row, data.indexOf(row))} y={viewHeight - 15} textAnchor={presentation === "overview" ? (index === 0 ? "start" : "end") : index === 0 ? "start" : index === 2 ? "end" : "middle"}>{shortDate(row.date)}</text>)}
          {presentation !== "overview" && <><text className="kk-chart-axis-label" x={plot.left} y={15}>Value</text><text className="kk-chart-axis-label" x={viewWidth - plot.right} y={viewHeight - 1} textAnchor="end">UTC date</text></>}
        </g>
        {presentation === "overview" && overviewPrimary && overviewAreaSegments.length > 0 && <g className="kk-chart-area" aria-hidden="true">{overviewAreaSegments.map((segment, index) => <path key={`area-${overviewPrimary.id}-${index}`} d={areaPath(segment)} fill={`url(#${areaGradientId})`} />)}</g>}
        <g className="kk-chart-series" aria-hidden="true">
          {allowedSeries.filter(item => visibleSeries.includes(item.id)).map(item => makeSegments(data, item.id, metrics.xFor, metrics.yFor).map((segment, index) => <path key={`${item.id}-${index}`} className={`kk-chart-line kk-chart-line--${item.id}`} d={monotonePath(segment)} fill="none" stroke={colorFor(item)} strokeDasharray={item.dash} strokeWidth={widthFor(item)} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />))}
          {presentation === "overview" && overviewPrimary && overviewEndpoint && <circle className="kk-chart-endpoint" cx={overviewEndpoint.x} cy={overviewEndpoint.y} r="4" fill={colorFor(overviewPrimary)} />}
          {!narrow && showEndLabels && endLabels.map(item => <text key={`${item.id}-label`} className="kk-chart-end-label" x={item.point.x + 12} y={item.labelY + 4} fill={item.color}>{item.label} {valueText(item.point.value)}</text>)}
        </g>
        {guideX !== null && <line className="kk-chart-guide" x1={guideX} x2={guideX} y1={plot.top} y2={viewHeight - plot.bottom} aria-hidden="true" />}
        <rect className="kk-chart-hit-area" x={plot.left} y={plot.top} width={Math.max(1, viewWidth - plot.left - plot.right)} height={Math.max(1, viewHeight - plot.top - plot.bottom)} tabIndex={0} role="slider" aria-label="Chart observation" aria-valuemin={0} aria-valuemax={Math.max(0, data.length - 1)} aria-valuenow={activeIndex ?? 0} aria-valuetext={activeRow ? displayTimestamp(activeRow.date) : "No date selected"} onPointerMove={handlePointerMove} onPointerLeave={clearHover} onClick={event => chooseIndex(pointerIndex(event), true)} onKeyDown={handleKeyDown} />
      </svg>
      {readoutRow && readoutX !== null && <div className={`kk-chart-readout kk-chart-readout--${readoutPlacement}`} style={{ left: `${(readoutX / viewWidth) * 100}%`, "--kk-chart-readout-left": `${(readoutX / viewWidth) * 100}%` } as React.CSSProperties} onPointerEnter={keepReadout} onPointerLeave={clearHover}><strong>{displayTimestamp(readoutRow.date)}</strong>{readoutValues.map(item => <span key={item.id}><i style={{ backgroundColor: item.color }} />{item.label}<b>{valueText(item.value)}</b></span>)}<small>{readoutHint} · press Escape to clear</small></div>}
    </div>
    {presentation !== "overview" && chartControls}
  </section>;
}
