import { reduced } from "./util";
/** Soft expanding rings behind the hero, like waves from far-off epicentres. Pauses when off-screen or when motion is reduced. */
export function ripples(canvas: HTMLCanvasElement) {
  const ctx = canvas.getContext("2d")!; let w = 0, h = 0, run = true;
  type Ring = { x: number; y: number; t: number; speed: number };
  const rings: Ring[] = [];
  const size = () => { const r = canvas.getBoundingClientRect(), d = Math.min(devicePixelRatio || 1, 2); w = r.width; h = r.height; canvas.width = w * d; canvas.height = h * d; ctx.setTransform(d, 0, 0, d, 0, 0); };
  size(); addEventListener("resize", size);
  const spawn = () => rings.push({ x: w * (0.55 + Math.random() * 0.4), y: h * (0.2 + Math.random() * 0.6), t: 0, speed: 0.5 + Math.random() * 0.5 });
  const frame = () => {
    if (!run) return;
    ctx.clearRect(0, 0, w, h);
    for (let i = rings.length - 1; i >= 0; i--) {
      const r = rings[i]; r.t += 0.006 * r.speed; if (r.t > 1) { rings.splice(i, 1); continue; }
      for (let k = 0; k < 3; k++) { const p = Math.max(0, r.t - k * 0.07); if (p <= 0) continue; ctx.beginPath(); ctx.arc(r.x, r.y, p * Math.max(w, h) * 0.5, 0, 6.2832); ctx.strokeStyle = `rgba(255,255,255,${(1 - p) * 0.35})`; ctx.lineWidth = 2 - k * 0.5; ctx.stroke(); }
      ctx.beginPath(); ctx.arc(r.x, r.y, 4 * (1 - r.t) + 1, 0, 6.2832); ctx.fillStyle = `rgba(255,255,255,${1 - r.t})`; ctx.fill();
    }
    if (rings.length < 4 && Math.random() < 0.015) spawn();
    requestAnimationFrame(frame);
  };
  if (reduced) { spawn(); rings[0].t = 0.35; ctx.clearRect(0, 0, w, h); const r = rings[0]; for (let k = 0; k < 3; k++) { ctx.beginPath(); ctx.arc(r.x, r.y, (r.t - k * 0.07) * Math.max(w, h) * 0.5, 0, 6.2832); ctx.strokeStyle = "rgba(255,255,255,.25)"; ctx.stroke(); } return; }
  spawn(); frame();
  new IntersectionObserver(([e]) => { const was = run; run = e.isIntersecting; if (run && !was) frame(); }).observe(canvas);
}
