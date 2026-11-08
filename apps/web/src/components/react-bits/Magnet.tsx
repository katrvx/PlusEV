'use client';

/**
 * React Bits Magnet, adapted for PlusEV.
 *
 * Source: https://github.com/DavidHDev/react-bits/blob/4dc7b5b7772e1217c8fb8d2a7aa074302180e5b4/src/ts-default/Animations/Magnet/Magnet.tsx
 * License: React Bits is MIT + Commons Clause (copyright David Haz).
 * Adaptations: coarse-pointer and reduced-motion opt-out, bounded movement,
 * and cleanup-safe pointer handling for shared app navigation controls.
 */

import { useEffect, useRef, type HTMLAttributes, type ReactNode } from 'react';

export type MagnetAxis = 'both' | 'x' | 'y';

export interface MagnetSpring {
  stiffness?: number;
  damping?: number;
  mass?: number;
}

export interface MagnetProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  padding?: number;
  disabled?: boolean;
  magnetStrength?: number;
  maxOffset?: number;
  axis?: MagnetAxis;
  tilt?: number;
  scale?: number;
  spring?: MagnetSpring;
  onActiveChange?: (active: boolean) => void;
  wrapperClassName?: string;
  innerClassName?: string;
}

type Motion = { x: number; y: number; tiltX: number; tiltY: number; scale: number };

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const Magnet = ({
  children,
  padding = 100,
  disabled = false,
  magnetStrength = 2,
  maxOffset,
  axis = 'both',
  tilt = 0,
  scale = 1,
  spring,
  onActiveChange,
  wrapperClassName = '',
  innerClassName = '',
  style,
  ...props
}: MagnetProps) => {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  const settingsRef = useRef({ disabled, padding, magnetStrength, maxOffset, axis, tilt, scale, spring, onActiveChange });
  settingsRef.current = { disabled, padding, magnetStrength, maxOffset, axis, tilt, scale, spring, onActiveChange };

  useEffect(() => {
    const wrapper = wrapperRef.current;
    const inner = innerRef.current;
    if (!wrapper || !inner) return undefined;

    const reduceQuery = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const coarseQuery = window.matchMedia?.('(pointer: coarse)');
    const touchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    const hasKeyboardFocus = () => wrapper.matches(':focus-visible') || Boolean(wrapper.querySelector(':focus-visible'));
    const shouldDisable = () => Boolean(settingsRef.current.disabled || reduceQuery?.matches || coarseQuery?.matches || touchDevice || hasKeyboardFocus());

    const current: Motion = { x: 0, y: 0, tiltX: 0, tiltY: 0, scale: 1 };
    const velocity: Motion = { x: 0, y: 0, tiltX: 0, tiltY: 0, scale: 0 };
    let pointer: { x: number; y: number } | null = null;
    let active = false;
    let raf = 0;
    let last = 0;

    const markActive = (next: boolean) => {
      if (next === active) return;
      active = next;
      if (next) wrapper.setAttribute('data-magnet-active', '');
      else wrapper.removeAttribute('data-magnet-active');
      settingsRef.current.onActiveChange?.(next);
    };

    const resetMotion = () => {
      pointer = null;
      markActive(false);
      cancelAnimationFrame(raf);
      raf = 0;
      last = 0;
      (Object.keys(current) as (keyof Motion)[]).forEach(key => {
        current[key] = key === 'scale' ? 1 : 0;
        velocity[key] = 0;
      });
      inner.style.transform = '';
    };

    const resetPointer = (immediate = shouldDisable()) => {
      pointer = null;
      if (immediate) {
        resetMotion();
        return;
      }
      wake();
    };

    const readTarget = (): { target: Motion; engaged: boolean } => {
      const target: Motion = { x: 0, y: 0, tiltX: 0, tiltY: 0, scale: 1 };
      if (shouldDisable() || !pointer) return { target, engaged: false };
      const settings = settingsRef.current;
      const rect = wrapper.getBoundingClientRect();
      const dx = pointer.x - (rect.left + rect.width / 2);
      const dy = pointer.y - (rect.top + rect.height / 2);
      const outside = Math.hypot(Math.max(0, Math.abs(dx) - rect.width / 2), Math.max(0, Math.abs(dy) - rect.height / 2));
      const safePadding = Math.max(0, settings.padding);
      if (outside > safePadding) return { target, engaged: false };
      const pull = safePadding ? 1 - clamp(outside / safePadding, 0, 1) : 1;
      const strength = Math.max(0.1, settings.magnetStrength);
      let x = settings.axis === 'y' ? 0 : (dx / strength) * pull;
      let y = settings.axis === 'x' ? 0 : (dy / strength) * pull;
      if (settings.maxOffset !== undefined) {
        const length = Math.hypot(x, y);
        if (length > settings.maxOffset) {
          x *= settings.maxOffset / length;
          y *= settings.maxOffset / length;
        }
      }
      target.x = x;
      target.y = y;
      target.tiltX = clamp(-dy / Math.max(rect.height / 2, 1), -1, 1) * settings.tilt * pull;
      target.tiltY = clamp(dx / Math.max(rect.width / 2, 1), -1, 1) * settings.tilt * pull;
      target.scale = 1 + (settings.scale - 1) * pull;
      return { target, engaged: true };
    };

    const apply = () => {
      const { x, y, tiltX, tiltY, scale: nextScale } = current;
      const tiltValue = Math.abs(tiltX) > 0.01 || Math.abs(tiltY) > 0.01
        ? ` perspective(800px) rotateX(${tiltX.toFixed(2)}deg) rotateY(${tiltY.toFixed(2)}deg)` : '';
      const scaleValue = Math.abs(nextScale - 1) > 0.0005 ? ` scale(${nextScale.toFixed(4)})` : '';
      inner.style.transform = `translate3d(${x.toFixed(2)}px, ${y.toFixed(2)}px, 0)${tiltValue}${scaleValue}`;
    };

    const solve = (target: Motion, dt: number) => {
      const settings = settingsRef.current;
      const stiffness = Math.max(1, settings.spring?.stiffness ?? 170);
      const damping = Math.max(0, settings.spring?.damping ?? 16);
      const mass = Math.max(0.01, settings.spring?.mass ?? 1);
      let resting = true;
      (Object.keys(current) as (keyof Motion)[]).forEach(key => {
        const force = stiffness * (target[key] - current[key]) - damping * velocity[key];
        velocity[key] += (force / mass) * dt;
        current[key] += velocity[key] * dt;
        const epsilon = key === 'scale' ? 0.001 : 0.05;
        if (Math.abs(target[key] - current[key]) > epsilon || Math.abs(velocity[key]) > epsilon) resting = false;
      });
      return resting;
    };

    const frame = (now: number) => {
      raf = 0;
      if (shouldDisable()) {
        resetMotion();
        return;
      }
      const dt = last ? Math.min((now - last) / 1000, 1 / 30) : 1 / 60;
      last = now;
      const { target, engaged } = readTarget();
      markActive(engaged);
      const steps = Math.ceil(dt / (1 / 120));
      let resting = true;
      for (let index = 0; index < steps; index += 1) resting = solve(target, dt / steps);
      if (resting) {
        (Object.keys(current) as (keyof Motion)[]).forEach(key => { current[key] = target[key]; velocity[key] = 0; });
      }
      apply();
      if (!resting) raf = requestAnimationFrame(frame);
      else last = 0;
    };

    function wake() { if (!raf) raf = requestAnimationFrame(frame); }
    const onPointerMove = (event: PointerEvent) => {
      if (event.pointerType === 'touch' || shouldDisable()) return;
      pointer = { x: event.clientX, y: event.clientY };
      wake();
    };
    const onPreferenceChange = () => { if (shouldDisable()) resetPointer(true); else wake(); };
    const onPointerLeave = () => resetPointer(false);
    const onFocusIn = () => resetPointer(true);
    const onWindowBlur = () => resetPointer(true);
    const onWindowScroll = () => resetPointer(false);

    window.addEventListener('pointermove', onPointerMove, { passive: true });
    wrapper.addEventListener('pointerleave', onPointerLeave);
    wrapper.addEventListener('focusin', onFocusIn);
    window.addEventListener('blur', onWindowBlur);
    window.addEventListener('scroll', onWindowScroll, { passive: true, capture: true });
    reduceQuery?.addEventListener?.('change', onPreferenceChange);
    coarseQuery?.addEventListener?.('change', onPreferenceChange);
    if (!shouldDisable()) wake();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', onPointerMove);
      wrapper.removeEventListener('pointerleave', onPointerLeave);
      wrapper.removeEventListener('focusin', onFocusIn);
      window.removeEventListener('blur', onWindowBlur);
      window.removeEventListener('scroll', onWindowScroll, { capture: true });
      reduceQuery?.removeEventListener?.('change', onPreferenceChange);
      coarseQuery?.removeEventListener?.('change', onPreferenceChange);
      wrapper.removeAttribute('data-magnet-active');
      resetMotion();
    };
  }, [disabled]);

  return (
    <div ref={wrapperRef} className={wrapperClassName} style={{ position: 'relative', display: 'inline-block', ...style }} {...props}>
      <div ref={innerRef} className={innerClassName} style={{ willChange: 'transform' }}>{children}</div>
    </div>
  );
};

export default Magnet;
