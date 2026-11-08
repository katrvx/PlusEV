"use client";

import { useLayoutEffect, useRef, type ReactNode } from "react";
import { ArrowUpRight, Check, Minus, X } from "lucide-react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import type { Experiment } from "./types";
import KineticText from "./kinetic-text";
import StorySignal from "./story-signal";
import { MascotCallout } from "./mascot";
import { MagneticAction, useInterfaceReducedMotion } from "./ui-motion";
import "./research-story.css";

gsap.registerPlugin(ScrollTrigger);

type Props = { example: Experiment | null; playback: ReactNode; onImport: () => void; onExample: () => void };

// Conceptual market shapes, never recorded returns or timestamped conditions.
const contexts = [
  { name: "A clear trend", path: "M10 108 C40 108 42 91 65 90 S100 72 123 74 S155 48 178 51 S209 32 232 34 S256 16 280 16" },
  { name: "A noisy market", path: "M10 72 C23 72 25 18 40 28 S60 112 78 93 S97 32 114 46 S135 109 151 83 S172 6 190 30 S214 110 233 81 S260 42 280 59" },
  { name: "A quiet spell", path: "M10 67 C33 67 38 59 58 62 S91 76 114 68 S144 60 166 65 S198 72 222 64 S260 68 280 63" },
];

export default function ResearchStory({ example, playback, onImport, onExample }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const reduced = useInterfaceReducedMotion();
  const demo = example?.mode === "demo" ? example : null;
  const findings = demo?.hypotheses.slice(0, 3) ?? [];

  useLayoutEffect(() => {
    const scope = root.current;
    if (!scope || reduced) return;
    const media = gsap.matchMedia();
    const context = gsap.context(() => {
      const timing = scope.querySelector(".rs-timing");
      const shapes = scope.querySelectorAll(".rs-context-path");
      gsap.fromTo(shapes, { strokeDasharray: 1, strokeDashoffset: 1 }, {
        strokeDashoffset: 0, stagger: .16, ease: "none",
        scrollTrigger: { trigger: timing, start: "top 70%", end: "top 5%", scrub: .5 },
      });
      media.add("(min-width: 761px)", () => {
        const sequence = gsap.timeline({ scrollTrigger: { trigger: timing, start: "top top", end: "bottom bottom", scrub: .6 } });
        sequence.fromTo(".rs-context-focus", { xPercent: 0 }, { xPercent: 200, duration: 2, ease: "none" })
          .to(".rs-timing-first", { yPercent: -45, autoAlpha: 0, duration: .6 }, .7)
          .fromTo(".rs-timing-next", { yPercent: 45, autoAlpha: 0 }, { yPercent: 0, autoAlpha: 1, duration: .6 }, .95)
          .fromTo(".rs-timing-resolution", { y: 16, opacity: 0 }, { y: 0, opacity: 1, duration: .5 }, 1.5);
        return () => sequence.revert();
      });
      const findingRows = scope.querySelectorAll(".rs-finding");
      const rejectionMarks = scope.querySelectorAll(".rs-reject-strike");
      if (findingRows.length) gsap.fromTo(findingRows, { x: 48, opacity: 0 }, {
        x: 0, opacity: 1, stagger: .15, duration: .7, ease: "power3.out",
        scrollTrigger: { trigger: ".rs-findings", start: "top 80%", once: true },
      });
      if (rejectionMarks.length) gsap.fromTo(rejectionMarks, { scaleX: 0 }, {
        scaleX: 1, transformOrigin: "left center", duration: .7,
        scrollTrigger: { trigger: ".rs-findings", start: "center 65%", once: true },
      });
      const sceneCallouts = scope.querySelectorAll(".rs-timing-annotation,.rs-research-mascot,.rs-challenge-note,.rs-finale-note");
      sceneCallouts.forEach(callout => gsap.fromTo(callout, { autoAlpha: 0, y: 24 }, {
        autoAlpha: 1, y: 0, duration: .62, ease: "power3.out",
        scrollTrigger: { trigger: callout, start: "top 82%", once: true },
      }));
      gsap.fromTo(".rs-finale-rule", { scaleX: 0 }, {
        scaleX: 1, transformOrigin: "left center", ease: "none",
        scrollTrigger: { trigger: ".rs-finale", start: "top 85%", end: "top 30%", scrub: .5 },
      });
    }, scope);
    ScrollTrigger.refresh();
    return () => { media.revert(); context.revert(); };
  }, [reduced, demo]);

  return <div id="research-story" className="rs-story" ref={root} data-reduced={reduced} tabIndex={-1} role="region" aria-label="The strategy research story">
    <section className="rs-timing" aria-labelledby="rs-timing-title">
      <div className="rs-timing-sticky">
        <div className="rs-timing-copy">
          <h2 id="rs-timing-title"><span className="kk-sr-only">When does the rule hold?</span><span aria-hidden="true"><KineticText>When does it hold?</KineticText><span className="rs-timing-swap"><span className="rs-timing-first">In one market.</span><span className="rs-timing-next">In the right market.</span></span></span></h2>
          <p className="rs-section-copy">A strategy is a set of rules.<br />The market decides when they get room to work.</p>
        </div>
        <div className="rs-contexts" role="img" aria-label="Illustrations of a clear trend, a noisy market and a quiet spell. Conceptual shapes, not performance data.">
          <div className="rs-context-focus" aria-hidden="true" />
          {contexts.map(item => <div className="rs-context" key={item.name}><svg viewBox="0 0 290 130" aria-hidden="true"><path className="rs-context-ghost" d={item.path} /><path className="rs-context-path" pathLength="1" d={item.path} /></svg><span>{item.name}</span></div>)}
        </div>
        <p className="rs-timing-resolution">The question is <strong>when.</strong></p>
        <MascotCallout pose="bull-point-right" title="A strategy is a rule." className="rs-timing-annotation">The market decides when that rule gets room to work.</MascotCallout>
      </div>
    </section>

    <section className="rs-research rs-section" aria-labelledby="rs-research-title">
      <div className="rs-research-copy"><h2 id="rs-research-title"><KineticText>What explains the difference?</KineticText></h2><p className="rs-section-copy">Agents propose explanations.<br className="rs-desktop-break" /> Code tests them against the evidence.</p></div>
      <div className="rs-research-stage"><StorySignal /><MascotCallout pose="bull-magnifier" title="Find the conditions." className="rs-research-mascot">What helped, what hurt, and what remains unclear.</MascotCallout></div>
    </section>

    <section className="rs-challenge rs-section" aria-labelledby="rs-challenge-title">
      <div className="rs-challenge-copy"><h2 id="rs-challenge-title"><KineticText>Can the rule survive?</KineticText></h2><p className="rs-section-copy">A proposed filter is a hypothesis.<br className="rs-desktop-break" /> Evidence decides what deserves a sealed test.</p><MascotCallout pose="bear-question" className="rs-challenge-note">Keep uncertainty visible.</MascotCallout></div>
      <div className="rs-findings">
        <p className="rs-findings-label">{findings.length ? "Inside an example investigation" : "Every explanation faces a test"}</p>
        {findings.length ? findings.map(finding => {
          const rejected = finding.status === "rejected";
          const supported = finding.status === "supported";
          const Icon = supported ? Check : rejected ? X : Minus;
          return <article className={"rs-finding rs-finding-" + finding.status} key={finding.id}><span className="rs-finding-icon"><Icon size={21} strokeWidth={1.8} /></span><div><span className="rs-finding-status">{supported ? "Support recorded" : rejected ? "Explanation rejected" : "Still uncertain"}</span><h3><span>{finding.title}{rejected && <i className="rs-reject-strike" aria-hidden="true" />}</span></h3></div></article>;
        }) : <p className="rs-findings-empty">Support it. Challenge it. Keep the uncertainty visible.</p>}
      </div>
    </section>

    <section className="rs-finale rs-section" aria-labelledby="rs-finale-title">
      <div className="rs-finale-rule" aria-hidden="true" />
      <h2 id="rs-finale-title"><KineticText>What happens next?</KineticText></h2>
      <p className="rs-section-copy">Agents propose. Code tests. A human approves the next step.</p>
      <MascotCallout pose="bear-pause" className="rs-finale-note">Good evidence earns the next question.</MascotCallout>
      {playback}
      <div className="rs-cta-actions"><MagneticAction><button type="button" className="kk-primary-button" onClick={onExample}>Try an example <ArrowUpRight size={19} /></button></MagneticAction><button type="button" className="rs-secondary-action" onClick={onImport}>Verify your strategy <ArrowUpRight size={18} /></button></div>
      <p className="rs-file-note">Start with private positions or strategy rules. Nothing trades live.</p>
      <footer className="rs-footer"><span><span>+</span>EV</span><p>Research before risk.</p></footer>
    </section>
  </div>;
}
