import { USGS } from "./config";

export interface Quake { id: string; mag_x10: number; origin_s: number; status: string; place: string; lat: number; lon: number }
export type Flag = { kind: "match" | "missing" | "mag" | "time" | "unknown"; text: string };

export const usgsPage = (id: string) => `https://earthquake.usgs.gov/earthquakes/eventpage/${encodeURIComponent(id)}`;

/** Compares one on-chain report with the USGS record, in the browser. USGS data is treated as data only. */
export async function checkEvent(id: string, mag_x10: number, origin_s: number): Promise<Flag> {
  try {
    const r = await fetch(`${USGS}?format=geojson&eventid=${encodeURIComponent(id)}`);
    if (r.status === 404 || r.status === 400) return { kind: "missing", text: "Not found in USGS" };
    if (!r.ok) return { kind: "unknown", text: "USGS check unavailable" };
    const p = (await r.json()).properties;
    const m = Math.round(p.mag * 10);
    if (m !== mag_x10) return { kind: "mag", text: `Magnitude differs: USGS says M${(m / 10).toFixed(1)}` };
    if (Math.abs(Math.floor(p.time / 1000) - origin_s) > 60) return { kind: "time", text: "Origin time differs from USGS" };
    return { kind: "match", text: "Matches USGS" };
  } catch { return { kind: "unknown", text: "USGS check unavailable" }; }
}

export async function recentM6(days: number): Promise<Quake[]> {
  const start = new Date(Date.now() - days * 86400_000).toISOString().slice(0, 19);
  const r = await fetch(`${USGS}?format=geojson&minmagnitude=6&starttime=${start}&orderby=time`);
  const j = await r.json();
  return j.features.filter((f: any) => f.properties.type === "earthquake").map((f: any) => ({
    id: f.id, mag_x10: Math.round(f.properties.mag * 10), origin_s: Math.floor(f.properties.time / 1000), status: f.properties.status,
    place: f.properties.place ?? "", lat: f.geometry.coordinates[1], lon: f.geometry.coordinates[0],
  }));
}

export function parseCsv(text: string): Record<string, string>[] {
  const lines = text.split(/\r?\n/).filter((l) => l && !l.startsWith("#"));
  const split = (l: string) => { const o: string[] = []; let cur = "", q = false; for (const c of l) { if (c === '"') q = !q; else if (c === "," && !q) { o.push(cur); cur = ""; } else cur += c; } o.push(cur); return o; };
  const head = split(lines[0]);
  return lines.slice(1).map((l) => Object.fromEntries(split(l).map((v, i) => [head[i], v])));
}

export async function loadCatalog(): Promise<Quake[]> {
  const rows = parseCsv(await (await fetch("data/usgs_60d.csv")).text());
  return rows.map((r) => ({ id: r.event_id, mag_x10: +r.mag_x10, origin_s: +r.origin_s, status: r.status, place: r.place, lat: +r.lat, lon: +r.lon }));
}
