export const $ = <T extends HTMLElement>(sel: string, root: ParentNode = document) => root.querySelector(sel) as T;
export const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
export const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

/** base units (6 decimals) -> "1,234.56" */
export function trem(base: string | bigint, dp = 2): string {
  const b = BigInt(base), s = 10n ** 6n, whole = b / s, frac = ((b % s) * 10n ** BigInt(dp)) / s;
  return whole.toLocaleString("en-US") + (dp ? "." + frac.toString().padStart(dp, "0") : "");
}
export const pct = (x: number, dp = 1) => (x * 100).toFixed(dp) + "%";
export const mag = (x10: number) => "M" + (x10 / 10).toFixed(1);
export const short = (acct: string) => acct.split(".")[0];

export function duration(s: number): string {
  if (s <= 0) return "0s";
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : m ? `${m}m ${sec}s` : `${sec}s`;
}
export function ago(s: number): string { return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)} min ago` : s < 86400 ? `${Math.floor(s / 3600)} h ago` : `${Math.floor(s / 86400)} d ago`; }

/** Animate a number from its current value to a target (respects reduced motion). */
export function countUp(el: HTMLElement, to: number, fmt: (n: number) => string) {
  const from = Number(el.dataset.v ?? 0); el.dataset.v = String(to);
  if (reduced || from === to) { el.textContent = fmt(to); return; }
  const t0 = performance.now(), dur = 1100;
  const tick = (t: number) => { const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3); el.textContent = fmt(from + (to - from) * e); if (k < 1) requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
}

export function reveal() {
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.12 });
  document.querySelectorAll(".reveal:not(.in)").forEach((n) => (reduced ? n.classList.add("in") : io.observe(n)));
}

/** Very small Markdown-to-HTML for results/sim/SUMMARY.md (headings, tables, lists, code, bold). Escapes everything first. */
export function md(src: string): string {
  const inline = (s: string) => esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  const out: string[] = []; const lines = src.split("\n"); let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (/^#{1,3} /.test(l)) { const n = l.match(/^#+/)![0].length + 1; out.push(`<h${n}>${inline(l.replace(/^#+ /, ""))}</h${n}>`); i++; }
    else if (l.startsWith("|")) {
      const rows: string[][] = []; while (i < lines.length && lines[i].startsWith("|")) { if (!/^\|[-| ]+\|$/.test(lines[i])) rows.push(lines[i].split("|").slice(1, -1).map((c) => c.trim())); i++; }
      out.push("<div class='tbl'><table><thead><tr>" + rows[0].map((c) => `<th>${inline(c)}</th>`).join("") + "</tr></thead><tbody>" + rows.slice(1).map((r) => "<tr>" + r.map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>").join("") + "</tbody></table></div>");
    } else if (l.startsWith("- ")) { const items: string[] = []; while (i < lines.length && lines[i].startsWith("- ")) items.push(`<li>${inline(lines[i++].slice(2))}</li>`); out.push(`<ul>${items.join("")}</ul>`); }
    else if (l.trim()) { out.push(`<p>${inline(l)}</p>`); i++; } else i++;
  }
  return out.join("\n");
}
