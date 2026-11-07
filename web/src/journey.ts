// The guided path for a judge: seven plain steps, each with one button. The current step is worked out from the chain and the wallet,
// so it moves on by itself as things happen. Pure HTML generation; main.ts handles the clicks (data-j attributes).
import type { Ev, Params, State } from "./chain";
import type { Quake } from "./usgs";
import { duration, esc, mag, short, trem } from "./util";

export interface Ctx {
  me: string | null; params: Params | null; state: State | null; evs: Ev[]; now: number; tok: bigint; bond: bigint; tapped: boolean;
  unreported: Quake[]; net: "live" | "demo"; ignoreBefore: number; checking: boolean;
}

export const myEvent = (c: Ctx): Ev | undefined =>
  c.me ? c.evs.filter((e) => e.reporter === c.me && e.reported_at > c.ignoreBefore).sort((a, b) => b.reported_at - a.reported_at)[0] : undefined;

export function renderJourney(c: Ctx): string {
  const p = c.params, ev = myEvent(c), t = c.now;
  const bondAmt = p ? BigInt(p.bond) : 1_000_000_000n, tapAmt = p ? BigInt(p.tap_amount) : 0n;
  const over = !!ev && ((ev.status === "waiting" && t >= ev.window_ends) || (ev.status === "challenged" && !!ev.vote_ends && t >= ev.vote_ends) || ev.status === "counted" || ev.status === "rejected");
  const final = !!ev && (ev.status === "counted" || ev.status === "rejected");
  const done = [!!c.me, c.tapped || c.tok > 0n || c.bond > 0n || tapAmt === 0n, c.bond >= bondAmt || !!ev, !!ev, over, final];
  const now = done.findIndex((d) => !d); const cur = now === -1 ? 6 : now; // 6 = the last step (the result)
  const pool = c.state ? BigInt(c.state.tap_pool) : 0n;
  const q = c.unreported[0];
  const dep = c.tok < bondAmt ? c.tok : bondAmt; // exactly what one report needs
  const steps: { title: string; sum: string; body: string }[] = [
    { title: "Connect a free wallet", sum: c.me ? `Connected as ${esc(c.me)}` : "",
      body: `<p>You need a free testnet account. It takes a minute in the Meteor wallet (switch it to <b>testnet</b>). Nothing here has any value.</p><button class="blue big" data-j="connect">Connect wallet</button>` },
    { title: "Get free starter coins", sum: `You have ${trem(c.tok)} TREM in your wallet`,
      body: tapAmt === 0n ? `<p>This contract has no starter-coin tap.</p>` : pool < tapAmt && !c.tapped ? `<p>The starter-coin pool is empty. Ask whoever runs this demo to refill it.</p>`
        : `<p>Press the button for ${trem(tapAmt, 0)} TREM. They are free, have no value, and you can take them once.</p><button class="blue big" data-j="tap">Get ${trem(tapAmt, 0)} TREM</button><p class="hint">Your wallet may ask for a tiny storage fee (0.00125 NEAR) the first time.</p>` },
    { title: "Put a deposit down", sum: `Deposit ready: ${trem(c.bond)} TREM`,
      body: `<p>Reporting an earthquake needs a ${trem(bondAmt, 0)} TREM <b>deposit</b>. You get it back if you turn out to be right, and lose it if you are wrong. That is what stops people posting lies for free.</p>
        ${c.tok >= bondAmt ? `<button class="blue big" data-j="deposit" data-amt="${dep}">Put ${trem(dep, 0)} TREM down</button>` : `<p class="hint">You need at least ${trem(bondAmt, 0)} TREM in your wallet first (step 2).</p>`}` },
    { title: "Report an earthquake", sum: ev ? `You reported ${esc(ev.event_id)} (${mag(ev.mag_x10)})` : "",
      body: c.net === "live" && !q
        ? `<p>The bot has already reported every recent real quake on the <b>Live</b> contract. Switch to the Demo (top bar) to report one yourself, or make up a fake one below.</p>`
        : `<p>Tell the contract about a real earthquake that just happened. This one is from the U.S. Geological Survey:</p>
           ${q ? `<p class="pick"><b>${mag(q.mag_x10)}</b> ${esc(q.place || "unnamed region")}</p><button class="blue big" data-j="report" data-id="${esc(q.id)}" data-mag="${q.mag_x10}" data-origin="${q.origin_s}">Report this earthquake</button>` : `<p class="hint">${c.checking ? "Looking up recent earthquakes…" : "No unreported real quake right now."}</p>`}`
        + `<p class="hint">Or <a href="#" data-j="fake">report a made-up one</a> to see what happens to lies.</p>` },
    { title: "Wait out the safety window", sum: "The window is over",
      body: !ev ? "" : ev.status === "challenged"
        ? `<p><b>Someone challenged your report.</b> Holders now lock coins on “real” or “not real”; the bigger side wins.</p>${voteUi(ev, c)}`
        : `<p>For a short time anyone can <b>challenge</b> a report they think is false. Nobody has yet.</p>${progress(ev, t)}${c.net === "live" ? `<p class="hint">This is the Live contract: the real window is ${duration(p?.window_s ?? 0)}. Switch to Demo (top bar) for a 2 minute window.</p>` : ""}` },
    { title: "Finalize", sum: "Settled",
      body: ev && over && !final ? `<p>The window is over. Press the button to settle it: if nobody proved the report wrong, the quake counts.</p><button class="blue big" data-j="finalize" data-id="${esc(ev.event_id)}">Finalize</button>` : `<p>Appears once the window is over.</p>` },
    { title: "See what it did", sum: "",
      body: result(ev, c) },
  ];
  const li = steps.map((s, i) => {
    const state = i < cur ? "done" : i === cur ? "now" : "todo";
    return `<li class="step ${state}"><span class="num" aria-hidden="true">${state === "done" ? "✓" : i + 1}</span><div><h3>${i + 1}. ${esc(s.title)}</h3>${state === "done" && s.sum ? `<p class="sum">${s.sum}</p>` : ""}${state === "now" ? s.body : ""}</div></li>`;
  }).join("");
  return `<ol class="journey">${li}</ol>`;
}

function progress(ev: Ev, t: number): string {
  const total = Math.max(1, ev.window_ends - ev.reported_at), k = Math.min(1, Math.max(0, (t - ev.reported_at) / total));
  return `<div class="bar"><i style="width:${Math.max(2, k * 100)}%"></i></div><p class="note">${t >= ev.window_ends ? "The window is over." : `Time left: <b class="cd" data-end="${ev.window_ends}">${duration(ev.window_ends - t)}</b>`}</p>`;
}

function voteUi(ev: Ev, c: Ctx): string {
  const real = BigInt(ev.real_locked), no = BigInt(ev.not_real_locked), left = ev.vote_ends ? ev.vote_ends - c.now : 0;
  return `<p class="note">Locked so far: ${trem(real, 0)} “real”, ${trem(no, 0)} “not real”. ${left > 0 ? `Voting ends in <b class="cd" data-end="${ev.vote_ends}">${duration(left)}</b>.` : "Voting is over."}</p>
    ${left > 0 && c.bond < 2500n * 1_000_000n && c.tok >= 2500n * 1_000_000n ? `<p class="hint">Voting uses coins from your deposit balance (${trem(c.bond, 0)} TREM there now).</p><button class="out" data-j="deposit" data-amt="${2500n * 1_000_000n}">Add 2,500 TREM to my deposit</button>` : ""}
    ${left > 0 ? `<div class="vote"><input type="number" min="1" value="2500" aria-label="Coins to lock, in TREM"><button class="out" data-j="vote" data-side="real" data-id="${esc(ev.event_id)}">Vote real</button><button class="out" data-j="vote" data-side="not_real" data-id="${esc(ev.event_id)}">Vote not real</button></div><p class="hint">Voting locks coins. If your side loses, you lose a fifth of what you locked.</p>` : ""}`;
}

function result(ev: Ev | undefined, c: Ctx): string {
  if (!ev || (ev.status !== "counted" && ev.status !== "rejected")) return `<p>Appears once your report is settled.</p>`;
  const again = `<div class="acts"><button class="out" data-j="again">Report another</button>${ev.challenger ? `<button class="out" data-j="claim" data-id="${esc(ev.event_id)}">Claim my vote payout</button>` : ""}<a class="out" href="#dispute">Watch a challenge play out</a></div>`;
  if (ev.status === "counted") {
    const m = BigInt(ev.minted), each = m / 5n;
    return `<p class="big-result"><b>${trem(m)} new TREM</b> were created and split between five relief accounts (${trem(each)} each). Your ${trem(c.params?.bond ?? "0", 0)} TREM deposit is back in your deposit balance.</p>
      ${ev.clipped ? `<p class="hint">A safety cap trimmed it: no week or month can create more than a fixed share of the supply.</p>` : ""}
      <p class="hint">${reportedIsFake(ev) ? "That report was made up, and nobody challenged it, so it counted. This is the weak spot, and the caps limit the damage. " : ""}You can see it in the event board and the meters below.</p>${again}`;
  }
  return `<p class="big-result"><b>Rejected.</b> Nothing was created.</p><p class="hint">A report that is shown to be false costs its author the deposit.</p>${again}`;
}
const reportedIsFake = (ev: Ev) => /^fake/i.test(ev.event_id);
export const label = (e: Ev) => `${esc(e.event_id)} · ${mag(e.mag_x10)} · ${esc(short(e.reporter))}`;
export type { State };
