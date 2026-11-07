import { reduced } from "./util";
const running = new WeakMap<HTMLElement, number>();

/** Damped shaking of one element, like ground motion after an S-wave arrives. amp is in px at the start. No-op with reduced motion. */
export function shake(el: HTMLElement, amp: number, ms = 1800) {
  if (reduced || amp <= 0) return;
  const prev = running.get(el); if (prev) cancelAnimationFrame(prev);
  const t0 = performance.now(), phase = Math.random() * 6.28;
  const step = () => {
    const t = performance.now(), k = Math.max(0, (t - t0) / ms); // never negative: rAF timestamps can precede t0
    if (k >= 1) { el.style.transform = ""; running.delete(el); return; }
    const env = amp * Math.exp(-3.6 * k), s = Math.max(0, t - t0) / 1000;
    const x = env * (Math.sin(s * 2 * Math.PI * 13 + phase) + 0.45 * Math.sin(s * 2 * Math.PI * 31)), y = env * 0.5 * Math.sin(s * 2 * Math.PI * 17 + 1.3);
    el.style.transform = `translate3d(${x.toFixed(2)}px,${y.toFixed(2)}px,0)`;
    running.set(el, requestAnimationFrame(step));
  };
  running.set(el, requestAnimationFrame(step));
}

/** Shake amplitude in px for a magnitude (x10): M6.0 is about 3 px, M8.0 about 11 px. */
export const ampFor = (mag_x10: number) => Math.min(12, 3 + Math.max(0, mag_x10 - 60) * 0.4);
