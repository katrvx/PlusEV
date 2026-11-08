"use client";

import { useLayoutEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useInterfaceReducedMotion } from "./ui-motion";
import "./story-signal.css";

gsap.registerPlugin(ScrollTrigger);

type StorySignalProps = {
  /** Optional local override for static previews and reduced-motion snapshots. */
  reduced?: boolean;
};

/**
 * A small process illustration for the landing story.
 *
 * The strands are intentionally conceptual: they communicate how research
 * separates conditions before testing a rule. They are not a market chart and
 * contain no synthetic performance values.
 */
export default function StorySignal({ reduced }: StorySignalProps) {
  const contextReduced = useInterfaceReducedMotion();
  const isReduced = reduced ?? contextReduced;
  const root = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const scope = root.current;
    const target = stage.current;
    if (!scope || !target || isReduced) return undefined;

    const context = gsap.context(() => {
      const strands = gsap.utils.toArray<SVGPathElement>(".ss-strand");
      const evidence = target.querySelector<SVGPathElement>(".ss-evidence-line");
      const lens = target.querySelector<SVGGElement>(".ss-lens-group");
      const checks = gsap.utils.toArray<SVGElement>(".ss-check");

      gsap.set(strands, { strokeDasharray: 1, strokeDashoffset: 1 });
      if (evidence) gsap.set(evidence, { strokeDasharray: 1, strokeDashoffset: 1 });
      if (lens) gsap.set(lens, { autoAlpha: 0.34, scale: 0.78, transformOrigin: "500px 215px" });
      gsap.set(checks, { autoAlpha: 0, y: 8 });

      const timeline = gsap.timeline({ paused: true });
      timeline.to(strands, { strokeDashoffset: 0, duration: 0.56, stagger: 0.1, ease: "power2.out" }, 0);
      if (lens) timeline.to(lens, { autoAlpha: 1, scale: 1, duration: 0.34, ease: "back.out(1.5)" }, 0.38);
      if (evidence) timeline.to(evidence, { strokeDashoffset: 0, duration: 0.56, ease: "power2.out" }, 0.58);
      timeline.to(checks, { autoAlpha: 1, y: 0, duration: 0.24, stagger: 0.1, ease: "power2.out" }, 0.94);

      ScrollTrigger.create({
        trigger: target,
        start: "top 78%",
        end: "bottom 30%",
        scrub: 0.7,
        animation: timeline,
      });
    }, scope);

    return () => context.revert();
  }, [isReduced]);

  return (
    <figure ref={root} className="ss-signal" aria-labelledby="ss-signal-caption">
      <div className="ss-mobile-key" aria-label="Research inputs and evidence output">
        <span><i className="ss-key-line ss-key-trend" />Trend</span>
        <span><i className="ss-key-line ss-key-volatility" />Volatility</span>
        <span><i className="ss-key-line ss-key-costs" />Costs</span>
        <span><i className="ss-key-line ss-key-evidence" />Evidence</span>
      </div>
      <div ref={stage} className="ss-signal-stage">
        <svg viewBox="0 0 960 430" role="img" aria-labelledby="ss-signal-svg-title ss-signal-svg-desc">
          <title id="ss-signal-svg-title">Research separates conditions before testing a strategy</title>
          <desc id="ss-signal-svg-desc">Trend, volatility and costs flow through a research lens and become one evidence line.</desc>

          <g className="ss-signal-grid" aria-hidden="true">
            <path d="M88 84H882" />
            <path d="M88 215H882" />
            <path d="M88 346H882" />
          </g>

          <g className="ss-signal-labels" aria-hidden="true">
            <text x="88" y="72">Trend</text>
            <text x="88" y="203">Volatility</text>
            <text x="88" y="334">Costs</text>
            <text x="785" y="145" className="ss-evidence-label">Evidence</text>
          </g>

          <g className="ss-signal-strands" fill="none" strokeLinecap="round" strokeLinejoin="round">
            <path className="ss-strand ss-strand-trend" d="M88 108C185 104 222 167 306 145C365 130 405 168 454 202" pathLength={1} />
            <path className="ss-strand ss-strand-volatility" d="M88 228C178 208 235 253 312 220C371 195 409 214 454 214" pathLength={1} />
            <path className="ss-strand ss-strand-costs" d="M88 347C183 363 235 284 313 284C372 284 411 251 454 228" pathLength={1} />
          </g>

          <g className="ss-lens-group" aria-hidden="true">
            <circle className="ss-lens-halo" cx="500" cy="215" r="72" />
            <circle className="ss-lens" cx="500" cy="215" r="53" />
            <circle className="ss-lens-core" cx="500" cy="215" r="5" />
          </g>

          <path className="ss-evidence-line" d="M546 215C618 188 666 240 735 204C786 178 829 204 882 156" pathLength={1} fill="none" strokeLinecap="round" strokeLinejoin="round" />

          <g className="ss-checks" aria-hidden="true">
            <g className="ss-check ss-check-one" transform="translate(630 294)">
              <circle r="12" />
              <path d="M-5 0L-1 4L6-4" />
            </g>
            <g className="ss-check ss-check-two" transform="translate(786 328)">
              <circle r="12" />
              <path d="M-5 0L-1 4L6-4" />
            </g>
          </g>
        </svg>
      </div>
      <figcaption id="ss-signal-caption" className="ss-signal-caption">Process illustration</figcaption>
    </figure>
  );
}
