// "Watch the bots decide": a narrated replay of a real recorded run on testnet (fixtures/testnet-demo.json, made by `make demo`).
// It is a recording, not a live action, and says so. Narration is generated from the recorded log lines, so the numbers are the chain's.
import { esc, mag, short, trem } from "./util";

interface Line { event: string; data: Record<string, any> }
const nice = (a: string) => short(a).replace(/^./, (c) => c.toUpperCase());
const botNo = (a: string) => short(a).replace("bot", "bot ");

export async function initDecide(host: HTMLElement) {
  let fx: { log: string[]; params: { publisher_accounts: string[]; threshold: number } };
  try { fx = await (await fetch("fixtures/testnet-demo.json")).json(); } catch { host.innerHTML = `<p class="note">The recording could not be loaded.</p>`; return; }
  if (!fx?.params?.publisher_accounts || !Array.isArray(fx.log)) { host.innerHTML = `<p class="note">The recording does not match this version of the contract.</p>`; return; }
  const bots = fx.params.publisher_accounts, need = fx.params.threshold;
  const lines: Line[] = fx.log.map((l) => JSON.parse(l));
  const versions = new Map<string, Map<string, Set<string>>>(); const status = new Map<string, string>(); const claimer = new Map<string, string>();
  type Step = { title: string; text: string; frame: string };
  const steps: Step[] = [];
  const frame = (id: string) => {
    const v = versions.get(id); const who = new Set([...(v?.values() ?? [])].flatMap((s) => [...s]));
    const chips = `<span class="bots">${bots.map((b, i) => `<span class="bot${who.has(b) ? " yes" : ""}" title="${esc(short(b))}">${who.has(b) ? "✓" : i + 1}</span>`).join("")}</span>`;
    const rows = [...(v?.entries() ?? [])].map(([k, s]) => `<p class="note">${esc(k)}: ${[...s].map(botNo).join(", ")} (${s.size} of ${need})</p>`).join("");
    const st = status.get(id) ?? "pending";
    return `<div class="rec-card"><b>${esc(id)}</b><span class="pill st-${st}">${st === "counted" ? "Counted" : "Waiting for the bots"}</span>${chips}${rows}</div>`;
  };
  for (const { event, data: d } of lines) {
    const id: string = d.event_id ?? ""; let title = "", text = "";
    if (event === "claim_submitted") {
      status.set(id, "pending"); claimer.set(id, d.claimer); versions.set(id, new Map());
      const fake = /^fake/.test(id); title = fake ? "A made-up quake is claimed" : "A quake is claimed";
      text = fake ? `${nice(d.claimer)} tells the contract about a quake called “${id}”, magnitude ${(d.mag_x10 / 10).toFixed(1)}. It does not exist: the USGS has no such event. A claim creates nothing by itself.`
        : `${nice(d.claimer)} tells the contract about a real magnitude ${(d.mag_x10 / 10).toFixed(1)} quake (${id}). A claim creates nothing by itself: the bots must confirm it.`;
    } else if (event === "attested") {
      const m = versions.get(id) ?? new Map<string, Set<string>>(); versions.set(id, m);
      const key = mag(d.mag_x10); const set = m.get(key) ?? new Set<string>(); set.add(d.publisher); m.set(key, set);
      const fake = /^fake/.test(id), others = [...m.keys()].length > 1;
      title = fake ? "A bad bot attests the made-up quake" : "A bot confirms the quake";
      text = fake ? `${nice(d.publisher)} attests “${id}” even though the USGS has no record of it (this recording shows what a bad bot could do). ${d.attestations} of ${need} needed.`
        : `${nice(d.publisher)} found this quake in the USGS record and attests it as ${key}. ${d.attestations} of ${need} needed bots agree.${others ? " Another bot saw a different magnitude, so those two records are counted separately." : ""}`;
    } else if (event === "event_counted") {
      status.set(id, "counted"); const fake = /^fake/.test(id);
      title = "It counts"; text = `${need} bots attested the same record, so the quake counts: ${trem(d.minted)} new TREM are created and split between the five relief accounts${d.clipped ? " (trimmed by a cap)" : ""}. Supply is now ${trem(d.supply, 0)}.${fake ? " This is the honest worst case: if three bots were bad, a fake could count, but never past the caps." : ""}`;
    } else continue;
    steps.push({ title, text, frame: frame(id) });
  }
  if (!steps.length) { host.innerHTML = `<p class="note">The recording is empty.</p>`; return; }
  let i = 0, timer: number | undefined;
  const draw = () => {
    const s = steps[i];
    host.innerHTML = `<div class="rec"><div class="rec-text"><small>Step ${i + 1} of ${steps.length}</small><h3>${esc(s.title)}</h3><p>${esc(s.text)}</p></div><div class="rec-frame">${s.frame}</div></div>
      <div class="acts"><button class="out" data-d="prev" ${i === 0 ? "disabled" : ""}>Back</button><button class="blue" data-d="next" ${i === steps.length - 1 ? "disabled" : ""}>Next</button><button class="out" data-d="play">${timer ? "Pause" : "Play"}</button><span class="note">A recording of a real run on testnet, not a live action.</span></div>`;
  };
  host.onclick = (e) => {
    const b = (e.target as HTMLElement).closest<HTMLElement>("[data-d]"); if (!b) return;
    const stop = () => { if (timer) { clearInterval(timer); timer = undefined; } };
    if (b.dataset.d === "next" && i < steps.length - 1) { stop(); i++; }
    else if (b.dataset.d === "prev" && i > 0) { stop(); i--; }
    else if (b.dataset.d === "play") { if (timer) stop(); else { if (i >= steps.length - 1) i = 0; timer = window.setInterval(() => { if (i < steps.length - 1) { i++; draw(); } else { stop(); draw(); } }, 2600); } }
    draw();
  };
  draw();
}
