// The guided path for a judge: four plain steps. The current step is worked out from the chain and the wallet, so it moves on by itself.
// Pure HTML generation; main.ts handles the clicks (data-j attributes).
import { alertName } from "./usgs";
import { unconfirmed, type Ev, type Params, type State } from "./chain";
import type { Quake } from "./usgs";
import { duration, esc, mag, short, trem } from "./util";

export interface Ctx {
  me: string | null; params: Params | null; state: State | null; evs: Ev[]; now: number; tok: bigint; tapped: boolean;
  unreported: Quake[]; net: "live" | "demo"; ignoreBefore: number; checking: boolean; realQuake?: boolean; // realQuake: the USGS check says my claimed quake exists
}

export const myEvent = (c: Ctx): Ev | undefined =>
  c.me ? c.evs.filter((e) => e.claimer === c.me && e.created_at > c.ignoreBefore).sort((a, b) => b.created_at - a.created_at)[0] : undefined;

export function botChips(e: Ev, p: Params | null): string {
  const bots = p?.publisher_accounts ?? [];
  const who = new Set(e.versions.flatMap((v) => v.attesters));
  return `<span class="bots" aria-label="${who.size} of ${bots.length} bots have attested">${bots.map((b, i) => `<span class="bot${who.has(b) ? " yes" : ""}" title="${esc(short(b))}">${who.has(b) ? "✓" : i + 1}</span>`).join("")}</span>`;
}

export function renderJourney(c: Ctx): string {
  const p = c.params, ev = myEvent(c), t = c.now;
  const final = !!ev && ev.status === "counted";
  const dead = !!ev && unconfirmed(ev, t);
  if (!c.me) return `<p class="note first">Anyone can tell the contract about a quake, but a claim creates nothing by itself: five fixed bots read the official U.S. Geological Survey record, and only quakes they find there can count.</p><p class="note">Connect your wallet (top of this tab) to try it.</p>`;
  const done = [!!ev, final || dead];
  const now = done.findIndex((d) => !d); const cur = now === -1 ? 2 : now;
  const q = c.unreported[0];
  const steps: { title: string; sum: string; body: string }[] = [
    { title: "Tell the contract about an earthquake", sum: ev ? `You claimed ${esc(ev.event_id)} (${mag(ev.mag_x10)})` : "",
      body: `<p>Anyone can tell the contract about a quake, but a claim creates nothing by itself. Five fixed <b>bots</b> read the official U.S. Geological Survey record, and only quakes they find there can count.</p>
        ${c.net === "live" && !q ? `<p>The bots have already confirmed every recent real quake on the <b>Live</b> contract. You can still make up a fake below, or switch to the Demo (top bar).</p>`
          : q ? `<p>A real earthquake from the USGS whose expected impact is high enough to count:</p><p class="pick"><b>${mag(q.mag_x10)}</b> ${esc(q.place || "unnamed region")} <span class="note">USGS expected impact: ${alertName(q.alert)}</span></p><button class="blue big" data-j="claim" data-id="${esc(q.id)}" data-mag="${q.mag_x10}" data-origin="${q.origin_s}" data-alert="${q.alert}">Tell the contract about it</button>`
          : `<p class="hint">${c.checking ? "Looking up recent earthquakes…" : "No unreported real quake right now."}</p>`}
        <p class="hint">Or <a href="#" data-j="fake">claim a made-up quake</a> and watch the bots ignore it.</p>` },
    { title: "Watch the five bots decide", sum: final ? "Confirmed" : "Not confirmed",
      body: !ev ? "" : `<p>${ev.attestations} of ${ev.needed} needed bots agree on this quake. ${/^fake/i.test(ev.event_id) ? "No bot will confirm it: the USGS has no such event." : "Each bot checks the USGS record on its own and says so only if it finds the same quake."}</p>
        ${botChips(ev, p)}${dead ? "" : `<p class="note">${c.net === "live" ? `Live bots wait ${duration(p?.min_age_s ?? 0)} after a quake (it can still be revised) and run every 20 minutes.` : "On the Demo the bots check every few seconds."}</p>`}
        ${stuck(ev, c) ? `<div class="mode warn slim"><div><b>The bots have not answered yet.</b><p>${c.net === "demo" ? "On the Demo the five bots are run by the project owner, from a computer or a GitHub job. If nobody started them, nothing gets confirmed, even for a real quake. Please tell the project owner (they start them with <code>make demo-bots</code>)." : "On Live the bots run every 20 minutes once a quake is old enough, so this can simply take a little longer."}</p></div></div>` : ""}
        ${ev.claim_open_until && !final ? `<p class="note">Your claim stays open for <b class="cd" data-end="${ev.claim_open_until}">${duration(ev.claim_open_until - t)}</b>.</p>` : ""}` },
    { title: "See what it did", sum: "", body: result(ev, dead) },
  ];
  const li = steps.map((s, i) => {
    const state = i < cur ? "done" : i === cur ? "now" : "todo";
    return `<li class="step ${state}"><span class="num" aria-hidden="true">${state === "done" ? "✓" : String.fromCharCode(97 + i)}</span><div><h4>${esc(s.title)}</h4>${state === "done" && s.sum ? `<p class="sum">${s.sum}</p>` : ""}${state === "now" ? s.body : ""}</div></li>`;
  }).join("");
  return `<ol class="journey">${li}</ol>`;
}

/** a REAL quake (USGS has it), old enough, still has no attestation after a while: the bots are probably not running */
function stuck(ev: Ev, c: Ctx): boolean {
  if (ev.status !== "pending" || ev.attestations > 0 || !c.realQuake || !c.params) return false;
  if (c.now - ev.origin_s < c.params.min_age_s) return false; // not old enough to be confirmed yet
  return c.now - ev.created_at > (c.net === "demo" ? 30 : 2400);
}

function result(ev: Ev | undefined, dead: boolean): string {
  const again = `<div class="acts"><button class="out" data-j="again">Try another quake</button><a class="out" href="#evidence-run">Watch the bots decide</a></div>`;
  if (!ev) return `<p>Appears once your claim is decided.</p>`;
  if (ev.status === "counted") {
    const m = BigInt(ev.minted), each = m / 5n;
    return `<p class="big-result"><b>${trem(m)} new TREM</b> were created and split between five relief accounts (${trem(each)} each), because ${ev.needed} bots agreed.</p>
      ${ev.clipped ? `<p class="hint">A safety cap trimmed it: no week or month can create more than a fixed share of the supply.</p>` : ""}
      <p class="hint">You can see it in the event board and the meters below.</p>${again}`;
  }
  if (dead) return `<p class="big-result"><b>Not confirmed.</b> No bot found this quake, so nothing was created.</p><p class="hint">That is the point: a made-up quake costs nothing to claim, and gains nothing.</p>${again}`;
  return `<p>Appears once your claim is decided.</p>`;
}
export type { State };
