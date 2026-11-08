"use client";

import { createContext, useContext, type ReactNode } from "react";
import { MotionConfig, motion, useReducedMotion } from "motion/react";
import AnimatedContent from "../react-bits/AnimatedContent";
import Magnet from "../react-bits/Magnet";
import type { MotionPreference } from "./types";

const ReducedMotion = createContext(false);

export const useInterfaceReducedMotion = () => useContext(ReducedMotion);

/** One motion policy and timing scale for the entire research workspace. */
export function InterfaceMotion({ preference, children }: { preference: MotionPreference; children: ReactNode }) {
  const systemReduced = useReducedMotion();
  const reduced = preference === "reduced" || !!systemReduced;
  return <ReducedMotion.Provider value={reduced}>
    <MotionConfig reducedMotion={reduced ? "always" : "user"} transition={{ duration: reduced ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] }}>
      {children}
    </MotionConfig>
  </ReducedMotion.Provider>;
}

export function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const reduced = useContext(ReducedMotion);
  return <AnimatedContent disabled={reduced} distance={14} duration={0.42} delay={delay} threshold={0} ease="power3.out" className={className}>
    {children}
  </AnimatedContent>;
}

export function MagneticAction({ children }: { children: ReactNode }) {
  const reduced = useContext(ReducedMotion);
  return <Magnet disabled={reduced} padding={18} magnetStrength={8} maxOffset={4} wrapperClassName="kk-magnetic">
    {children}
  </Magnet>;
}

export function ActiveIndicator({ group }: { group: "primary" | "explore" }) {
  const reduced = useContext(ReducedMotion);
  return <motion.span className="kk-active-indicator" layoutId={reduced ? undefined : `kk-${group}-selection`} aria-hidden="true" />;
}
