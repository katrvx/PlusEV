'use client';

/**
 * React Bits AnimatedContent, adapted for PlusEV.
 *
 * Source: https://github.com/DavidHDev/react-bits/blob/4dc7b5b7772e1217c8fb8d2a7aa074302180e5b4/src/ts-default/Animations/AnimatedContent/AnimatedContent.tsx
 * License: React Bits is MIT + Commons Clause (copyright David Haz).
 * Adaptations: explicit disabled support, reduced-motion handling, visible SSR
 * fallback, and a small prop surface used by PlusEV's shared motion settings.
 */

import { useEffect, useLayoutEffect, useRef, type CSSProperties, type HTMLAttributes, type ReactNode } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export interface AnimatedContentProps extends Omit<HTMLAttributes<HTMLDivElement>, 'onAnimationStart'> {
  children?: ReactNode;
  container?: Element | string | null;
  distance?: number;
  direction?: 'vertical' | 'horizontal';
  reverse?: boolean;
  duration?: number;
  ease?: string;
  initialOpacity?: number;
  animateOpacity?: boolean;
  scale?: number;
  blur?: number;
  rotate?: number;
  tilt?: number;
  threshold?: number;
  delay?: number;
  trigger?: 'scroll' | 'mount';
  once?: boolean;
  disabled?: boolean;
  onStart?: () => void;
  onComplete?: () => void;
  className?: string;
  style?: CSSProperties;
}

const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;

const AnimatedContent = ({
  children,
  container,
  distance = 100,
  direction = 'vertical',
  reverse = false,
  duration = 0.8,
  ease = 'power3.out',
  initialOpacity = 0,
  animateOpacity = true,
  scale = 1,
  blur = 0,
  rotate = 0,
  tilt = 0,
  threshold = 0.1,
  delay = 0,
  trigger = 'scroll',
  once = true,
  disabled = false,
  onStart,
  onComplete,
  className = '',
  style,
  ...props
}: AnimatedContentProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const callbacksRef = useRef({ onStart, onComplete });
  callbacksRef.current = { onStart, onComplete };

  useIsomorphicLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;

    // The component is deliberately visible before hydration. If JavaScript
    // is unavailable the research story remains readable instead of hidden.
    el.style.visibility = 'visible';

    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const reduce = media?.matches ?? false;
    if (disabled || reduce) return undefined;

    let scroller: Element | null = typeof container === 'string'
      ? document.querySelector(container)
      : container ?? document.getElementById('snap-main-container');

    const ctx = gsap.context(() => {
      const targets: Element[] = el.children.length ? Array.from(el.children) : [el];
      const horizontal = direction === 'horizontal';
      const axis = horizontal ? 'x' : 'y';
      const sign = reverse ? -1 : 1;

      gsap.set(el, { visibility: 'visible' });

      const from: gsap.TweenVars = {
        [axis]: distance * sign,
        scale,
        opacity: animateOpacity ? initialOpacity : 1
      };
      const to: gsap.TweenVars = {
        [axis]: 0,
        scale: 1,
        opacity: 1,
        duration: Math.max(duration, 0.01),
        ease
      };

      if (blur > 0) {
        from.filter = `blur(${blur}px)`;
        to.filter = 'blur(0px)';
      }
      if (rotate) {
        from.rotation = rotate * sign;
        to.rotation = 0;
      }
      if (tilt) {
        const tiltAxis = horizontal ? 'rotationY' : 'rotationX';
        from[tiltAxis] = horizontal ? -tilt * sign : tilt * sign;
        to[tiltAxis] = 0;
        from.transformPerspective = 900;
        to.transformPerspective = 900;
      }

      const tl = gsap.timeline({
        paused: true,
        onStart: () => callbacksRef.current.onStart?.(),
        onComplete: () => {
          callbacksRef.current.onComplete?.();
          gsap.set(targets, { clearProps: 'filter,transform' });
        }
      });
      tl.fromTo(targets, from, to, Math.max(delay, 0));

      if (trigger === 'mount') {
        tl.play();
        return;
      }

      ScrollTrigger.create({
        trigger: el,
        scroller,
        start: `top ${(1 - Math.min(Math.max(threshold, 0), 1)) * 100}%`,
        once,
        onEnter: () => tl.play(),
        onLeaveBack: once ? undefined : () => tl.reverse()
      });
    }, el);

    const onMotionPreferenceChange = () => {
      if (media?.matches) {
        ctx.revert();
        el.style.visibility = 'visible';
      }
    };
    media?.addEventListener?.('change', onMotionPreferenceChange);

    return () => {
      media?.removeEventListener?.('change', onMotionPreferenceChange);
      ctx.revert();
    };
  }, [container, distance, direction, reverse, duration, ease, initialOpacity, animateOpacity, scale, blur, rotate, tilt, threshold, delay, trigger, once, disabled]);

  return (
    <div ref={ref} className={className} style={{ visibility: 'visible', ...style }} {...props}>
      {children}
    </div>
  );
};

export default AnimatedContent;
