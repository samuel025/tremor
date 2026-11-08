// Which contract this page talks to: "live" (real timing: quakes are confirmed after 6 hours) or "demo" (confirmed within seconds).
export interface Dep { contract: string; label: string; min_age_s?: number; claim_wait_s?: number; bots?: string[] }
export let NET: "live" | "demo" = "live";
export let DEP: Dep = { contract: "", label: "" };
export let ALL: Record<string, Dep> = {};

export async function loadDeployments() {
  ALL = await (await fetch("deployments.json")).json();
  NET = "live"; DEP = ALL.live; // the page reads the real Live contract; the interactive demo is the in-browser simulation
}
export function switchNet(net: "live" | "demo", hash = "") {
  try { localStorage.setItem("tremor-net", net); } catch { /* ignore */ }
  const u = new URL(location.href); u.searchParams.set("net", net); u.hash = hash; location.href = u.toString();
}
