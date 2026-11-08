"use client";

/**
 * A restrained word reveal inspired by React Bits SplitText.
 *
 * Reference: https://reactbits.dev/text-animations/split-text
 * Upstream source family: https://github.com/DavidHDev/react-bits
 *
 * This product component keeps the source text in one accessible label and
 * animates only visual word wrappers. It intentionally avoids character-level
 * scrambling and never animates numeric result values.
 */

import { useLayoutEffect, useMemo, useRef, type HTMLAttributes } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useInterfaceReducedMotion } from "./ui-motion";
import "./kinetic-text.css";

gsap.registerPlugin(ScrollTrigger);

export type KineticTextProps = Omit<HTMLAttributes<HTMLSpanElement>, "children"> & {
  children: string;
  /** Reveal on first paint or when the heading enters the viewport. */
  trigger?: "mount" | "scroll";
  /** Delay before the first word starts, in seconds. */
  delay?: number;
  /** Delay between word starts, in seconds. */
  stagger?: number;
  /** Duration for each word, in seconds. */
  duration?: number;
  /** Intersection threshold used by the scroll trigger. */
  threshold?: number;
};

const tokensFor = (text: string) => text.split(/(\s+)/).filter(Boolean);

export default function KineticText({
  children,
  trigger = "scroll",
  delay = 0,
  stagger = 0.045,
  duration = 0.7,
  threshold = 0.16,
  className = "",
  ...props
}: KineticTextProps) {
  const root = useRef<HTMLSpanElement>(null);
  const reduced = useInterfaceReducedMotion();
  const tokens = useMemo(() => tokensFor(children), [children]);

  useLayoutEffect(() => {
    const element = root.current;
    if (!element) return undefined;

    const words = Array.from(element.querySelectorAll<HTMLElement>(".kt-word"));
    const prefersReduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    element.classList.add("kt-ready");
    if (!words.length || reduced || prefersReduced) {
      element.classList.remove("kt-ready");
      return undefined;
    }

    const context = gsap.context(() => {
      // Create the deferred tween while the GSAP context is active. The
      // ScrollTrigger callback only plays it, so unmount cleanup owns it.
      const revealTimeline = gsap.timeline({
        paused: true,
        onComplete: () => element.classList.remove("kt-ready")
      });
      revealTimeline.fromTo(
        words,
        { yPercent: 105, rotation: 4, opacity: 0 },
        {
          yPercent: 0,
          rotation: 0,
          opacity: 1,
          duration: Math.max(0.05, duration),
          delay: Math.max(0, delay),
          stagger: Math.max(0, stagger),
          ease: "power3.out",
          clearProps: "transform,opacity"
        }
      );

      if (trigger === "mount") {
        revealTimeline.play();
        return;
      }

      ScrollTrigger.create({
        trigger: element,
        start: `top ${Math.round((1 - Math.min(Math.max(threshold, 0), 1)) * 100)}%`,
        once: true,
        onEnter: () => revealTimeline.play()
      });
    }, element);

    return () => {
      context.revert();
      element.classList.remove("kt-ready");
    };
  }, [delay, duration, reduced, stagger, threshold, trigger, children]);

  return (
    <span ref={root} className={`kt-root ${className}`.trim()} {...props}>
      <span className="kt-sr-only">{children}</span>
      <span className="kt-visual" aria-hidden="true">
        {tokens.map((token, index) => token.trim() ? (
          <span className="kt-word-mask" key={`${token}-${index}`}><span className="kt-word">{token}</span></span>
        ) : <span className="kt-space" key={`${token}-${index}`}>{token}</span>)}
      </span>
    </span>
  );
}
