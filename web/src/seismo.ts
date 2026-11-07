import { reduced } from "./util";

interface Burst { t0: number; amp: number }
export interface SeismoOpts { speed: number; color: string; grid?: string; labels?: boolean; baseline?: number; onS?: (amp: number) => void }

/** A scrolling seismogram. burst() adds an event with a small fast P-wave, then a larger slower S-wave that decays (the coda).
 *  setExternal() adds continuous shaking (the nav trace uses it for scroll speed). Pure visual: not a real sensor. */
export class Seismo {
  private ctx: CanvasRenderingContext2D; private w = 0; private h = 0; private bursts: Burst[] = []; private ext = 0; private run = false; private raf = 0;
  private last = performance.now() / 1000; private buf: { t: number; y: number }[] = [];
  constructor(private cv: HTMLCanvasElement, private o: SeismoOpts) {
    this.ctx = cv.getContext("2d")!; this.size(); addEventListener("resize", () => this.size());
    if (reduced) this.drawStatic();
  }
  private size() { const r = this.cv.getBoundingClientRect(), d = Math.min(devicePixelRatio || 1, 2); this.w = r.width; this.h = r.height; this.cv.width = this.w * d; this.cv.height = this.h * d; this.ctx.setTransform(d, 0, 0, d, 0, 0); if (reduced) this.drawStatic(); }
  setExternal(a: number) { this.ext = a; }
  burst(mag_x10: number) {
    const amp = Math.min(1, 0.28 + Math.max(0, mag_x10 - 60) / 26), t0 = performance.now() / 1000;
    this.bursts.push({ t0, amp });
    if (this.o.onS) { const cb = this.o.onS; setTimeout(() => cb(amp), 1400); }
    if (reduced) this.drawStatic();
  }
  private value(t: number): number {
    let y = (this.o.baseline ?? 0.035) * (Math.sin(t * 2 * Math.PI * 17.3) * 0.6 + Math.sin(t * 2 * Math.PI * 7.1 + 1) * 0.4 + (Math.random() - 0.5) * 0.8);
    if (this.ext > 0.01) y += this.ext * (Math.sin(t * 2 * Math.PI * 9) * 0.7 + (Math.random() - 0.5) * 0.9);
    for (const b of this.bursts) {
      const p = t - b.t0; if (p < 0) continue;
      y += 0.22 * b.amp * Math.exp(-p / 0.9) * Math.sin(p * 2 * Math.PI * 11);
      const s = p - 1.4; if (s > 0) y += b.amp * Math.exp(-s / 2.4) * Math.sin(s * 2 * Math.PI * 3.1) * (1 + 0.25 * Math.sin(p * 2 * Math.PI * 7));
    }
    return y;
  }
  start() { if (reduced || this.run) return; this.run = true; this.last = performance.now() / 1000; this.raf = requestAnimationFrame(() => this.frame()); }
  stop() { this.run = false; cancelAnimationFrame(this.raf); }
  private frame() {
    if (!this.run) return;
    const now = performance.now() / 1000, step = 1 / 120;
    for (let t = this.last; t < now; t += step) this.buf.push({ t, y: this.value(t) });
    this.last = now;
    const keep = this.w / this.o.speed + 1; while (this.buf.length && this.buf[0].t < now - keep) this.buf.shift();
    this.bursts = this.bursts.filter((b) => now - b.t0 < 14);
    this.draw(now); this.raf = requestAnimationFrame(() => this.frame());
  }
  private draw(now: number) {
    const { ctx, w, h } = this, cy = h / 2, k = h * 0.44;
    ctx.clearRect(0, 0, w, h);
    if (this.o.grid) {
      ctx.strokeStyle = this.o.grid; ctx.lineWidth = 1; ctx.beginPath();
      for (let x = ((now * this.o.speed) % 60); x < w; x += 60) { const xx = w - x; ctx.moveTo(xx, 0); ctx.lineTo(xx, h); }
      for (let i = 1; i < 6; i++) { ctx.moveTo(0, (h / 6) * i); ctx.lineTo(w, (h / 6) * i); }
      ctx.stroke();
    }
    ctx.strokeStyle = this.o.color; ctx.lineWidth = 1.6; ctx.lineJoin = "round"; ctx.beginPath();
    this.buf.forEach((s, i) => { const x = w - (now - s.t) * this.o.speed, y = cy - s.y * k; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
    ctx.stroke();
    if (this.o.labels) {
      ctx.font = "600 11px ui-sans-serif, system-ui, sans-serif"; ctx.fillStyle = "#b64400"; ctx.strokeStyle = "#b64400"; ctx.lineWidth = 1;
      for (const b of this.bursts) for (const [off, lab] of [[0, "P"], [1.4, "S"]] as const) {
        const x = w - (now - b.t0 - off) * this.o.speed; if (x < 0 || x > w) continue;
        ctx.globalAlpha = 0.6; ctx.beginPath(); ctx.moveTo(x, 8); ctx.lineTo(x, h - 8); ctx.stroke(); ctx.globalAlpha = 1; ctx.fillText(lab, x + 5, 20);
      }
    }
  }
  private drawStatic() { // reduced motion: one frozen trace
    const { ctx, w, h } = this; ctx.clearRect(0, 0, w, h); ctx.strokeStyle = this.o.color; ctx.lineWidth = 1.6; ctx.beginPath();
    const burst = this.bursts[this.bursts.length - 1]; for (let x = 0; x <= w; x += 2) { const p = x / w * 12, a = burst ? burst.amp : 0.3; const y = 0.03 * Math.sin(x * 0.9) + (p > 5 ? a * Math.exp(-(p - 5) / 2.4) * Math.sin((p - 5) * 6.2 * 1.6) : 0); x ? ctx.lineTo(x, h / 2 - y * h * 0.44) : ctx.moveTo(x, h / 2); }
    ctx.stroke();
  }
}
