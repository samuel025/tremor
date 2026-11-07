// "Watch a challenge play out": a narrated replay of a real recorded run on testnet (fixtures/testnet-demo.json, made by `make demo`).
// It is a recording, not a live action, and says so. Narration is generated from the recorded log lines, so the numbers are the chain's.
import { esc, short, trem } from "./util";

interface Line { event: string; data: Record<string, any> }
const nice = (a: string) => short(a).replace(/^./, (c) => c.toUpperCase());

export async function initDispute(host: HTMLElement) {
  let fx: { log: string[] };
  try { fx = await (await fetch("fixtures/testnet-demo.json")).json(); } catch { host.innerHTML = `<p class="note">The recording could not be loaded.</p>`; return; }
  const lines: Line[] = fx.log.map((l) => JSON.parse(l));
  const votes = new Map<string, { real: bigint; no: bigint }>(); const status = new Map<string, string>();
  let supply = 1_000_000n * 1_000_000n;
  type Step = { text: string; title: string; evId: string; frame: string };
  const steps: Step[] = [];
  const bar = (id: string) => { const v = votes.get(id); if (!v) return ""; const t = v.real + v.no || 1n; return `<div class="split"><i class="yes" style="width:${Number((v.real * 1000n) / t) / 10}%"></i><i class="no" style="width:${Number((v.no * 1000n) / t) / 10}%"></i></div><div class="dl"><span><i class="sw yes"></i>Real ${trem(v.real, 0)}</span><span><i class="sw no"></i>Not real ${trem(v.no, 0)}</span></div>`; };
  for (const { event, data: d } of lines) {
    const id: string = d.event_id ?? ""; let title = "", text = "";
    if (event === "event_posted") { status.set(id, "waiting"); const fake = /^fake/.test(id); title = fake ? "A lie is reported" : "A real quake is reported";
      text = fake ? `${nice(d.reporter)} reports a quake called “${id}”, magnitude ${(d.mag_x10 / 10).toFixed(1)}. It does not exist: nobody can find it in the USGS record. They lock a deposit anyway.` : `${nice(d.reporter)} reports a real magnitude ${(d.mag_x10 / 10).toFixed(1)} quake (${id}) and locks a deposit.`; }
    else if (event === "event_challenged") { status.set(id, "challenged"); votes.set(id, { real: 0n, no: 0n }); title = "Someone challenges it"; text = `${nice(d.challenger)} says “this is false” and locks a matching deposit. Now every holder can vote with their coins.`; }
    else if (event === "vote_cast") { const v = votes.get(id)!; const a = BigInt(d.amount); if (d.side === "real") v.real += a; else v.no += a; title = "A vote"; text = `${nice(d.voter)} locks ${trem(a, 0)} TREM on “${d.side === "real" ? "real" : "not real"}”.`; }
    else if (event === "event_counted") { status.set(id, "counted"); supply = BigInt(d.supply); title = "It counts"; text = `The window ended with no successful challenge, so the quake counts: ${trem(d.minted)} new TREM are created and split between the five relief accounts${d.clipped ? " (trimmed by a cap)" : ""}. Supply is now ${trem(supply, 0)}.${/^fake/.test(id) ? " This one was made up and nobody checked it: that is the weak spot, and the caps limit it." : ""}`; }
    else if (event === "event_rejected") { status.set(id, "rejected"); title = "It is rejected"; text = `More coins were locked on “not real”, so the report is rejected. Nothing is created. The liar loses the deposit and a fifth of the coins locked on the losing side; that goes to the winners.`; }
    else if (event === "claimed") { title = "Payout"; text = `${nice(d.account)} claims ${trem(d.paid)} TREM back from the vote.`; }
    else continue;
    const st = status.get(id) ?? "waiting";
    steps.push({ title, text, evId: id, frame: `<div class="rec-card"><b>${esc(id)}</b><span class="pill st-${st}">${st[0].toUpperCase() + st.slice(1)}</span>${bar(id)}</div>` });
  }
  let i = 0, timer: number | undefined;
  const draw = () => {
    const s = steps[i];
    host.innerHTML = `<div class="rec"><div class="rec-text"><small>Step ${i + 1} of ${steps.length}</small><h3>${esc(s.title)}</h3><p>${esc(s.text)}</p></div><div class="rec-frame">${s.frame}</div></div>
      <div class="acts"><button class="out" data-d="prev" ${i === 0 ? "disabled" : ""}>Back</button><button class="blue" data-d="next" ${i === steps.length - 1 ? "disabled" : ""}>Next</button><button class="out" data-d="play">${timer ? "Pause" : "Play"}</button><span class="note">A recording of a real run on testnet (13 checks), not a live action.</span></div>`;
  };
  host.onclick = (e) => {
    const b = (e.target as HTMLElement).closest<HTMLElement>("[data-d]"); if (!b) return;
    const stop = () => { if (timer) { clearInterval(timer); timer = undefined; } };
    if (b.dataset.d === "next" && i < steps.length - 1) { stop(); i++; }
    else if (b.dataset.d === "prev" && i > 0) { stop(); i--; }
    else if (b.dataset.d === "play") { if (timer) stop(); else { if (i >= steps.length - 1) i = 0; timer = window.setInterval(() => { if (i < steps.length - 1) { i++; draw(); } else { stop(); draw(); } }, 3200); } }
    draw();
  };
  draw();
}
