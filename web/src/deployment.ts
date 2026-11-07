// Which contract this page talks to: "live" (real timing: quakes are confirmed after 6 hours) or "demo" (confirmed within seconds).
export interface Dep { contract: string; label: string; min_age_s?: number; claim_wait_s?: number; bots?: string[] }
export let NET: "live" | "demo" = "live";
export let DEP: Dep = { contract: "", label: "" };
export let ALL: Record<string, Dep> = {};

export async function loadDeployments() {
  ALL = await (await fetch("deployments.json")).json();
  const q = new URLSearchParams(location.search).get("net");
  let saved: string | null = null; try { saved = localStorage.getItem("tremor-net"); } catch { /* private mode */ }
  const want = q ?? saved ?? "demo";
  NET = want === "live" && ALL.live?.contract ? "live" : "demo";
  DEP = ALL[NET];
}
export function switchNet(net: "live" | "demo", hash = "") {
  try { localStorage.setItem("tremor-net", net); } catch { /* ignore */ }
  const u = new URL(location.href); u.searchParams.set("net", net); u.hash = hash; location.href = u.toString();
}
