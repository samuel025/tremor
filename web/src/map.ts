import type { Quake } from "./usgs";
import { parseCsv } from "./usgs";
import { esc, mag, reduced } from "./util";

const T0 = 1788825600; // 2026-09-08 00:00 UTC, start of the committed catalog window

/** Equirectangular dot map of the committed 60-day catalog with a replay of supply growth (simulation, chosen parameters). */
export async function initMap(host: HTMLElement, cat: Quake[]) {
  const series = parseCsv(await (await fetch("sim/scenario1_real.csv")).text()).map((r) => Number(r.supply));
  const S0 = 1_000_000 * 1e6;
  const dots = cat.map((q) => {
    const day = Math.floor((q.origin_s - T0) / 86400), big = q.mag_x10 >= 60;
    const r = big ? 1.4 + (q.mag_x10 - 60) * 0.35 : 0.7;
    return { q, day, big, html: `<g class="dot${big ? " big" : ""}" data-day="${day}" transform="translate(${(q.lon + 180).toFixed(2)} ${(90 - q.lat).toFixed(2)})"><title>${esc(mag(q.mag_x10))} · ${esc(q.place)}</title>${big ? `<circle class="ring" r="${r}"/>` : ""}<circle class="core" r="${r}"/></g>` };
  });
  const grat = [...Array(11)].map((_, i) => `<line x1="${i * 36}" x2="${i * 36}" y1="0" y2="180" class="gr"/>`).join("") + [...Array(5)].map((_, i) => `<line x1="0" x2="360" y1="${i * 45}" y2="${i * 45}" class="gr"/>`).join("");
  host.innerHTML = `<div class="mapbox"><svg viewBox="0 0 360 180" role="img" aria-label="Map of magnitude 5 and larger earthquakes in the committed 60-day catalog">${grat}${dots.map((d) => d.html).join("")}</svg></div>
    <div class="replay"><button class="btn" id="play" aria-label="Play replay">▶ Replay 60 days</button><input id="scrub" type="range" min="0" max="59" value="59" aria-label="Day of the 60-day window">
    <div class="readout"><span><small>Day</small><b id="rd-day">60</b></span><span><small>Supply</small><b id="rd-sup">–</b></span><span><small>Quakes M6+ so far</small><b id="rd-n">–</b></span></div></div>`;
  const svg = host.querySelector("svg")!, scrub = host.querySelector<HTMLInputElement>("#scrub")!, play = host.querySelector<HTMLButtonElement>("#play")!;
  const els = [...svg.querySelectorAll<SVGGElement>(".dot")];
  let last = -1;
  const show = (day: number) => {
    els.forEach((g) => { const on = +g.dataset.day! <= day; const was = g.classList.contains("on"); g.classList.toggle("on", on); if (on && !was && g.classList.contains("big") && !reduced) { g.classList.remove("pulse"); void (g as unknown as SVGElement).getBoundingClientRect(); g.classList.add("pulse"); } });
    host.querySelector("#rd-day")!.textContent = String(day + 1);
    host.querySelector("#rd-sup")!.textContent = (series[day] / 1e6).toLocaleString("en-US", { maximumFractionDigits: 0 }) + " TREM (" + (((series[day] - S0) / S0) * 100).toFixed(2) + "%)";
    host.querySelector("#rd-n")!.textContent = String(dots.filter((d) => d.big && d.day <= day).length);
    scrub.value = String(day); last = day;
  };
  let timer: number | undefined;
  const stop = () => { if (timer) clearInterval(timer); timer = undefined; play.textContent = "▶ Replay 60 days"; };
  play.onclick = () => {
    if (timer) return stop();
    let d = last >= 59 ? -1 : last; play.textContent = "❚❚ Pause";
    timer = window.setInterval(() => { d++; if (d > 59) return stop(); show(d); }, reduced ? 30 : 160);
  };
  scrub.oninput = () => { stop(); show(+scrub.value); };
  show(59);
}
