"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { ArrowLeft, ArrowRight, HelpCircle, X } from "lucide-react";
import { Mascot, type MascotPose } from "./mascot";
import { useInterfaceReducedMotion } from "./ui-motion";
import "./workspace-guide.css";

/** The page-level guide is opt-in: it never starts while a user is reading a page. */
export type GuidePage = "strategy" | "overview" | "conditions" | "evidence" | "compare" | "plans" | "review" | "portfolio";

type GuideStep = {
  target: string;
  fallback?: string;
  pose: MascotPose;
  eyebrow: string;
  title: string;
  body: string;
};

type GuideRect = { top: number; left: number; width: number; height: number; right: number; bottom: number };

const clampRect = (rect: DOMRect, viewport: { width: number; height: number }): GuideRect => {
  const edge = 12;
  const left = Math.max(edge, Math.min(rect.left, Math.max(edge, viewport.width - edge)));
  const top = Math.max(edge, Math.min(rect.top, Math.max(edge, viewport.height - edge)));
  const right = Math.max(left + 8, Math.min(rect.right, viewport.width - edge));
  const bottom = Math.max(top + 8, Math.min(rect.bottom, viewport.height - edge));
  return { left, top, right, bottom, width: right - left, height: bottom - top };
};

const GUIDE_STEPS: Record<GuidePage, GuideStep[]> = {
  strategy: [
    { target: "[data-guide-target='strategy-verdict']", fallback: ".svd-banner, .sv-notice, .sv-result-empty, .sv-research-state", pose: "bull-welcome", eyebrow: "READ THIS FIRST", title: "The verdict is earned from evidence.", body: "Read the decision and its source. “Not proven” means the supplied evidence has not established a reliable edge. Open the source trail before changing the rule.", },
    { target: "[data-guide-target='strategy-action']", fallback: ".sv-research", pose: "bull-take-note", eyebrow: "NEXT", title: "Start with position history.", body: "Use the positions file or connected positions input you already trust. The evaluator can then check where the strategy held up without changing its source.", },
  ],
  overview: [
    { target: "[data-guide-target='strategy-verdict']", fallback: ".ov-scene-callout, .ov-hero-value, .ov-hero", pose: "bull-point-right", eyebrow: "READ THIS FIRST", title: "Start with the verdict.", body: "Read the decision and its reason together. It applies to the strategy shown here; a proposed filter needs its own evidence.", },
    { target: "[data-guide-target='strategy-health']", fallback: ".sh-health, [data-guide-target='strategy-health-range'], .ov-hero-action, .ov-chart-wrap, .ov-chart, .research-chart", pose: "bear-question", eyebrow: "CHECK IT", title: "Check the strategy health.", body: "Inside the supplied training range is not a profit or Keep signal. These are recorded validation blocks, not live observations. Open their evidence for the next check.", },
  ],
  conditions: [
    { target: "[data-guide-target='conditions-finding']", fallback: ".cv-leading-note, .cv-pattern-aside, .cv-situation-detail", pose: "bull-frame-region", eyebrow: "LOOK FOR", title: "Where did it hold up?", body: "The selected condition is the clearest place to begin. Small samples still need care.", },
    { target: "[data-guide-target='conditions-table']", fallback: ".cv-patterns, .cv-interval-rows, .cv-chart-section", pose: "bear-read-sheet", eyebrow: "COMPARE", title: "Then scan the other conditions.", body: "Each row is supplied evidence. Open its source instead of treating the grouping as a new rule.", },
  ],
  evidence: [
    { target: "[data-guide-target='evidence-verdict'], [data-guide-target='evidence-finding']", fallback: ".ev-leading-note, .ev-findings, .ev-hypothesis-list", pose: "bull-magnifier", eyebrow: "THE CLAIM", title: "What changed?", body: "This is the finding in accessible language. Open the exact evidence link before turning it into a next action.", },
    { target: "[data-guide-target='evidence-path']", fallback: ".ev-path, .ev-technical", pose: "bear-read-sheet", eyebrow: "THE TRAIL", title: "Follow the source trail.", body: "Use the report and evidence links to see what was checked, rejected or left uncertain, then return to the proposed next check.", },
  ],
  compare: [
    { target: "[data-guide-target='compare-conclusion']", fallback: ".cmp-reading, .cmp-result-line, .cmp-annotation", pose: "bull-compare", eyebrow: "DECISION", title: "Read which test is complete.", body: "Validation chooses a proposed rule; the sealed new-data test is the check it must survive. The conclusion tells you which stage the supplied report actually reached.", },
    { target: "[data-guide-target='compare-chart']", fallback: ".cmp-plot-section, .research-chart, .kk-chart", pose: "bear-compare", eyebrow: "INSPECT", title: "Keep the baselines visible.", body: "Compare the original strategy, simple rule, proposed filter and cash on the same supplied view before choosing a next action.", },
    { target: "[data-guide-target='checked-filters']", fallback: ".cmp-details-disclosure", pose: "bull-read-sheet", eyebrow: "TAKE IT WITH YOU", title: "See what was actually checked.", body: "A tested filter is not automatically a passed filter. Inspect its recorded decision, then download the unchanged strategy reference, filter settings and evidence together.", },
  ],
  plans: [
    { target: "[data-guide-target='plans-status']", fallback: ".ob-status, .ob-plan, .ob-list", pose: "bear-waiting", eyebrow: "SAVED PLAN", title: "A plan is not a running test.", body: "Saved protocols stay planned and not running until a real observation service exists.", },
    { target: "[data-guide-target='plans-action']", fallback: ".ob-action, .ob-plan-detail, .ob-footer", pose: "bull-acknowledge", eyebrow: "NEXT", title: "Review before approval.", body: "Check the frozen strategy identity and assumptions before approving a paper-test protocol.", },
  ],
  review: [
    { target: "[data-guide-target='review-conclusion']", fallback: ".pr-summary, .pr-conclusion, .paper-review-summary", pose: "bear-question", eyebrow: "REVIEW", title: "Ask what is actually known.", body: "The summary keeps supplied findings separate from anything the product has not measured.", },
    { target: "[data-guide-target='review-approval']", fallback: ".pr-approval, .pr-actions, .paper-review-actions", pose: "bull-acknowledge", eyebrow: "LAST STEP", title: "Approval saves a protocol.", body: "It does not start live orders or invent observations. The plan remains saved and not running.", },
  ],
  portfolio: [
    { target: "[data-guide-target='portfolio-verdicts']", fallback: ".portfolio-verdicts, .portfolio-summary, .portfolio-grid", pose: "bull-compare", eyebrow: "READ THIS FIRST", title: "Start with the decisions.", body: "Each strategy gets a verdict earned from the evidence supplied for it. “Not proven” means the data is not enough to establish a reliable edge.", },
    { target: "[data-guide-target='portfolio-action']", fallback: ".portfolio-action, .portfolio-next, .portfolio-cta", pose: "bear-question", eyebrow: "NEXT", title: "Open one strategy at a time.", body: "Choose the strategy whose evidence you want to inspect next. Keep the original assumptions visible as you compare.", },
  ],
};

function findTarget(step: GuideStep): HTMLElement | null {
  const preferCopy = (element: HTMLElement) => element.querySelector<HTMLElement>(".kk-mascot-copy") ?? element;
  const direct = document.querySelector<HTMLElement>(step.target);
  if (direct) return preferCopy(direct);
  if (!step.fallback) return null;
  for (const selector of step.fallback.split(",")) {
    const found = document.querySelector<HTMLElement>(selector.trim());
    if (found) return preferCopy(found);
  }
  return null;
}

function escapeTarget(target: HTMLElement) {
  if (window.innerWidth < 768) {
    const top = window.scrollY + target.getBoundingClientRect().top - 84;
    window.scrollTo({ top: Math.max(0, top), behavior: "auto" });
    return;
  }
  target.scrollIntoView({ block: "center", inline: "nearest", behavior: "auto" });
}

export function WorkspaceGuide({ page, label = "Explain this page" }: { page: GuidePage; label?: string }) {
  const reduced = useInterfaceReducedMotion();
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<GuideRect | null>(null);
  const [bubbleRect, setBubbleRect] = useState<GuideRect | null>(null);
  const [targetMissing, setTargetMissing] = useState(false);
  const [viewport, setViewport] = useState({ width: 1, height: 1 });
  const guideRootRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const bubbleRef = useRef<HTMLDivElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const frame = useRef<number | null>(null);
  const steps = useMemo(() => GUIDE_STEPS[page] ?? GUIDE_STEPS.strategy, [page]);
  const step = steps[Math.min(index, steps.length - 1)];

  useEffect(() => {
    const update = () => setViewport({ width: window.innerWidth, height: window.innerHeight });
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const measureTarget = useCallback(() => {
    if (!step) return;
    const target = findTarget(step);
    const bubble = bubbleRef.current?.getBoundingClientRect();
    setBubbleRect(bubble ? clampRect(bubble, viewport) : null);
    if (!target) { setTargetMissing(true); setTargetRect(null); return; }
    setTargetMissing(false);
    setTargetRect(clampRect(target.getBoundingClientRect(), viewport));
  }, [step, viewport]);

  const scheduleMeasure = useCallback(() => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => { frame.current = null; measureTarget(); });
  }, [measureTarget]);

  const close = useCallback(() => {
    setOpen(false);
    setTargetRect(null);
    setBubbleRect(null);
    const focus = previousFocus.current;
    previousFocus.current = null;
    window.setTimeout(() => {
      const destination = focus && focus.isConnected ? focus : launcherRef.current;
      destination?.focus({ preventScroll: true });
    }, 0);
  }, []);

  useEffect(() => {
    // Changing tabs while a guide is open should never leave an old explanation
    // pointing at a new screen.
    if (open) close();
    setIndex(0);
  }, [page]);

  const openGuide = () => {
    // Do not cover an evidence/native report dialog that already owns focus.
    if (document.querySelector("[role='dialog']:not(.kk-guide-dialog)")) return;
    previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setIndex(0);
    setOpen(true);
  };

  const next = () => {
    if (index >= steps.length - 1) close();
    else setIndex(current => current + 1);
  };

  useEffect(() => {
    if (!open || !step) return;
    const target = findTarget(step);
    // Unlock briefly while moving to the next real section. The overlay blocks
    // interaction, but the target is still allowed to scroll into view.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "";
    if (target) escapeTarget(target);
    const timer = window.setTimeout(() => {
      document.body.style.overflow = "hidden";
      scheduleMeasure();
    }, reduced ? 0 : 260);
    return () => {
      window.clearTimeout(timer);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, step, reduced, scheduleMeasure]);

  useEffect(() => {
    if (!open) return;
    const root = guideRootRef.current;
    const touched: { element: HTMLElement; hadInert: boolean }[] = [];
    const markBackground = (container: Element) => {
      for (const child of Array.from(container.children)) {
        if (child === root) continue;
        if (root && child.contains(root)) markBackground(child);
        else if (child instanceof HTMLElement) {
          touched.push({ element: child, hadInert: child.hasAttribute("inert") });
          child.setAttribute("inert", "");
        }
      }
    };
    const app = root?.closest(".kk-app");
    if (app) markBackground(app);
    else markBackground(document.body);
    return () => touched.forEach(({ element, hadInert }) => { if (!hadInert) element.removeAttribute("inert"); });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const update = () => scheduleMeasure();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    if (dialogRef.current) observer?.observe(dialogRef.current);
    closeRef.current?.focus();
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
      observer?.disconnect();
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, [open, scheduleMeasure]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); close(); return; }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = [...dialogRef.current.querySelectorAll<HTMLElement>("button, [href], [tabindex]:not([tabindex='-1'])")].filter(item => !item.hasAttribute("disabled"));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!dialogRef.current.contains(document.activeElement)) { event.preventDefault(); first.focus(); return; }
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    const onFocusIn = (event: FocusEvent) => {
      if (!dialogRef.current?.contains(event.target as Node)) closeRef.current?.focus();
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("focusin", onFocusIn);
    return () => { document.removeEventListener("keydown", onKeyDown); document.removeEventListener("focusin", onFocusIn); };
  }, [open, close]);

  const onDialogKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" && (event.target as HTMLElement).tagName === "DIV") next();
  };

  const arrowStart = bubbleRect
    ? { x: bubbleRect.left + Math.min(136, bubbleRect.width * .42), y: bubbleRect.top + bubbleRect.height * .58 }
    : { x: Math.max(24, viewport.width - 420), y: viewport.height - 220 };
  const arrowEnd = targetRect
    ? (() => {
      const centerX = targetRect.left + targetRect.width / 2;
      const fromRight = arrowStart.x >= centerX;
      const x = fromRight ? targetRect.right : targetRect.left;
      const y = Math.max(targetRect.top + 14, Math.min(arrowStart.y, targetRect.bottom - 14));
      return { x, y };
    })()
    : { x: viewport.width / 2, y: viewport.height / 2 };
  const bendX = (arrowStart.x + arrowEnd.x) / 2;
  const path = `M ${arrowStart.x} ${arrowStart.y} C ${bendX} ${arrowStart.y - 90}, ${bendX} ${arrowEnd.y + 90}, ${arrowEnd.x} ${arrowEnd.y}`;

  return <>
    {!open && <button ref={launcherRef} type="button" className="kk-guide-launcher" onClick={openGuide}><HelpCircle size={17} aria-hidden="true" />{label}</button>}
    {open && <div aria-hidden="true" style={{ height: viewport.height, pointerEvents: "none" }} />}
    {open && <div ref={guideRootRef} className="kk-guide-root" data-target-missing={targetMissing ? "true" : "false"}>
      <div className="kk-guide-scrim" aria-hidden="true" />
      {targetRect && <div className="kk-guide-spotlight" aria-hidden="true" style={{ top: targetRect.top - 12, left: targetRect.left - 12, width: targetRect.width + 24, height: targetRect.height + 24 }} />}
      <svg className="kk-guide-arrow" viewBox={`0 0 ${viewport.width} ${viewport.height}`} preserveAspectRatio="none" aria-hidden="true"><defs><marker id="kk-guide-arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="var(--kk-accent)" /></marker></defs><path d={path} markerEnd="url(#kk-guide-arrowhead)" /></svg>
      <div ref={dialogRef} className="kk-guide-dialog" role="dialog" aria-modal="true" aria-labelledby="kk-guide-title" aria-describedby="kk-guide-body" tabIndex={-1} onKeyDown={onDialogKeyDown}>
        <div ref={bubbleRef} className="kk-guide-bubble"><span className="kk-guide-eyebrow">{step.eyebrow} · {index + 1}/{steps.length}</span><h2 id="kk-guide-title">{step.title}</h2><p id="kk-guide-body">{step.body}</p><span className="kk-guide-bubble-tail" aria-hidden="true" /></div>
        <Mascot key={`${page}-${index}`} pose={step.pose} className="kk-guide-mascot" />
        <div className="kk-guide-controls"><button ref={closeRef} type="button" className="kk-guide-skip" onClick={close}>Skip <X size={14} aria-hidden="true" /></button><div><button type="button" className="kk-guide-back" onClick={() => setIndex(current => Math.max(0, current - 1))} disabled={index === 0}><ArrowLeft size={15} aria-hidden="true" />Back</button><button type="button" className="kk-guide-next kk-primary-button" onClick={next}>{index >= steps.length - 1 ? "Done" : "Next"}<ArrowRight size={15} aria-hidden="true" /></button></div></div>
      </div>
    </div>}
  </>;
}

export default WorkspaceGuide;
