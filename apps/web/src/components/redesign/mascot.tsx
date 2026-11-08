"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import manifest from "../../../public/mascots/v1/manifest.json";
import { useInterfaceReducedMotion } from "./ui-motion";
import "./mascot.css";

export type MascotPose =
  | "bull-point-left" | "bull-point-right" | "bull-present-up" | "bull-welcome"
  | "bull-compare" | "bull-neutral" | "bull-magnifier" | "bull-read-sheet"
  | "bull-take-note" | "bull-frame-region" | "bull-thoughtful" | "bull-acknowledge"
  | "bear-point-left" | "bear-point-right" | "bear-present-up" | "bear-question"
  | "bear-compare" | "bear-neutral" | "bear-magnifier" | "bear-read-sheet"
  | "bear-chin-rest" | "bear-folded-arms" | "bear-pause" | "bear-waiting";

/** These are distinct editorial poses, never sequential animation frames. */
export function Mascot({ pose, className = "", alt = "" }: {
  pose: MascotPose; className?: string; alt?: string;
}) {
  const sprite = manifest.sprites.find(item => item.id === pose);
  if (!sprite) return null;
  const style: CSSProperties = {
    backgroundImage: `url(/mascots/v1/${sprite.file})`,
    backgroundPosition: sprite.backgroundPosition,
    backgroundSize: sprite.backgroundSize,
    aspectRatio: `${sprite.width} / ${sprite.height}`,
  };
  return <span className={`kk-mascot ${className}`} data-pose={pose} style={style}
    role={alt ? "img" : undefined} aria-label={alt || undefined} aria-hidden={alt ? undefined : true} />;
}

export function MascotCallout({ pose, title, className = "", children }: {
  pose: MascotPose; title?: string; className?: string; children: ReactNode;
}) {
  const root = useRef<HTMLDivElement>(null);
  const reduced = useInterfaceReducedMotion();
  const [peek, setPeek] = useState(false);
  useEffect(() => {
    const element = root.current;
    if (!element) return;
    let observer: IntersectionObserver | undefined;
    const watch = () => {
      observer?.disconnect();
      if (reduced || !("IntersectionObserver" in window)) { setPeek(true); return; }
      setPeek(false);
      observer = new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) {
          setPeek(true);
          observer?.disconnect();
        }
      }, { threshold: .35, rootMargin: "0px 0px -20px 0px" });
      observer.observe(element);
    };
    watch();
    return () => observer?.disconnect();
  }, [pose, reduced]);
  return <div ref={root} className={`kk-mascot-callout ${className}`} data-peek={peek || reduced ? "shown" : "waiting"} data-character={pose.startsWith("bear") ? "bear" : "bull"} role="note">
    <Mascot key={pose} pose={pose} />
    <div className="kk-mascot-copy">{title && <strong>{title}</strong>}<div>{children}</div></div>
  </div>;
}

export function MascotDuo({ className = "" }: { className?: string }) {
  return <img className={`kk-mascot-duo ${className}`} src={`/mascots/v1/${manifest.hero.file}`}
    width={manifest.hero.width} height={manifest.hero.height} alt="" decoding="async" fetchPriority="high" />;
}

export default Mascot;
