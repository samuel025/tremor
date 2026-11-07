// Which contract this page talks to: "live" (real 24 h / 48 h windows, kept busy by the keeper) or "demo" (2 and 3 minute windows).
export interface Dep { contract: string; label: string; window_s: number; vote_s: number; keeper?: string }
export let NET: "live" | "demo" = "live";
export let DEP: Dep = { contract: "", label: "", window_s: 0, vote_s: 0 };
export let ALL: Record<string, Dep> = {};

export async function loadDeployments() {
  ALL = await (await fetch("deployments.json")).json();
  const q = new URLSearchParams(location.search).get("net");
  let saved: string | null = null; try { saved = localStorage.getItem("tremor-net"); } catch { /* private mode */ }
  const want = q ?? saved ?? "demo";
  NET = want === "live" && ALL.live?.contract ? "live" : "demo";
  DEP = ALL[NET];
}
export function switchNet(net: "live" | "demo") {
  try { localStorage.setItem("tremor-net", net); } catch { /* ignore */ }
  const u = new URL(location.href); u.searchParams.set("net", net); u.hash = ""; location.href = u.toString();
}
