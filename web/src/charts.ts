import { parseCsv } from "./usgs";
import { esc } from "./util";

interface Series { name: string; label: string; vals: number[] }
const PANELS: { title: string; note: string; series: [string, string][] }[] = [
  { title: "1 · Real quakes", note: "28 real M6+ events, five honest bots", series: [["scenario1_real", "real catalog"]] },
  { title: "2 · Swarm", note: "12 extra events in 36 hours: the caps hold", series: [["scenario1_real", "real only"], ["scenario2_swarm", "with swarm"]] },
  { title: "3 · Bad bots", note: "10 made-up quakes; 2 bad bots (none count) or 3 (all count, capped)", series: [["scenario3_badbots_k2", "2 bad bots"], ["scenario3_badbots_k3", "3 bad bots"]] },
  { title: "4 · Bots offline", note: "2 offline: nothing changes. 3 offline: nothing is created", series: [["scenario4_offline_m2", "2 offline"], ["scenario4_offline_m3", "3 offline"]] },
  { title: "5 · Claim spam", note: "6 made-up claims an hour: real quakes still count", series: [["scenario5_claimspam", "under spam"]] },
];

async function load(name: string, label: string, s0: number): Promise<Series> {
  const rows = parseCsv(await (await fetch(`sim/${name}.csv`)).text());
  return { name, label, vals: rows.map((r) => Number(r.supply) / s0) };
}

export async function renderCharts(host: HTMLElement, s0: number) {
  const panels = await Promise.all(PANELS.map(async (p) => ({ ...p, data: await Promise.all(p.series.map(([n, l]) => load(n, l, s0))) })));
  const ymax = Math.max(...panels.flatMap((p) => p.data.flatMap((d) => d.vals))) * 1.005;
  const W = 320, H = 190, L = 40, B = 24, T = 10, R = 8;
  host.innerHTML = panels.map((p) => {
    const x = (i: number) => L + (i / 59) * (W - L - R), y = (v: number) => T + (1 - (v - 1) / (ymax - 1)) * (H - T - B);
    const grid = [1, 1.025, 1.05, 1.075].filter((g) => g < ymax).map((g) => `<line x1="${L}" x2="${W - R}" y1="${y(g)}" y2="${y(g)}" class="grid"/><text x="${L - 6}" y="${y(g) + 4}" text-anchor="end">${g.toFixed(3)}</text>`).join("");
    const lines = p.data.map((d, k) => `<polyline class="line s${k}" fill="none" points="${d.vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ")}"/>`).join("");
    const legend = p.data.map((d, k) => `<span><i class="sw s${k}"></i>${esc(d.label)}</span>`).join("");
    return `<figure class="chart reveal"><figcaption><b>${esc(p.title)}</b><small>${esc(p.note)}</small></figcaption>
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(p.title)}: total supply over 60 days, relative to the initial supply">${grid}
      <text x="${L}" y="${H - 6}">day 0</text><text x="${W - R}" y="${H - 6}" text-anchor="end">day 60</text>${lines}</svg><div class="legend">${legend}</div></figure>`;
  }).join("");
}
