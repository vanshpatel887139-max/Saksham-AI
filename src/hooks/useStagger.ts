import { useEffect, useRef, useState, type CSSProperties } from 'react';

export const STAGGER_MS = 65;
export const MAX_CARD_DELAY_MS = 400;

export const staggerStyle = (index: number, active: boolean): CSSProperties => ({
  animationDelay: `${active ? Math.min(index * STAGGER_MS, MAX_CARD_DELAY_MS) : 0}ms`,
  animationPlayState: active ? 'running' : 'paused',
});

export function useStagger() {
  const animatedRef = useRef(false);
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    if (!animatedRef.current) {
      animatedRef.current = true;
      setAnimate(true);
    }
  }, []);

  return { animate, staggerStyle };
}