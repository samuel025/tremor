// The in-browser simulation: the same rules code as the contract (src/sim/engine.ts, proven identical to the Python reference by
// tests/conformance.ts), driven by five simulated bots. Nothing here is on-chain.
import { Tremor, DAY, Reject, SCALE, type Params } from "./sim/engine.ts";
import { alertName, type Quake } from "./usgs.ts";
import { esc, mag, trem } from "./util.ts";

type Mode = "honest" | "bad" | "offline";
const BOTS = ["bot1", "bot2", "bot3", "bot4", "bot5"], RELIEF = ["relief1", "relief2", "relief3", "relief4", "relief5"];
const PLAN: Record<string, Mode[]> = {
  low: ["honest", "honest", "honest", "honest", "honest"], real: ["honest", "honest", "honest", "honest", "honest"], fake: ["honest", "honest", "honest", "honest", "honest"],
  bad2: ["bad", "bad", "honest", "honest", "honest"], bad3: ["bad", "bad", "bad", "honest", "honest"], off3: ["offline", "offline", "offline", "honest", "honest"],
};
const YOU = "you", START = 5_000_000_000n; // the visitor holds 5,000 simulated TREM, like the Live starter coins
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function initSimulator(host: HTMLElement, catalog: Quake[], chosen: { base_ppm: number; week_ppm: number; month_ppm: number }, steps?: number) {
  const quakes = catalog.filter((q) => q.mag_x10 >= 60).sort((a, b) => b.origin_s - a.origin_s);
  const byId = new Map(quakes.map((q) => [q.id, q]));
  const params: Params = { s0: 1_000_000_000_000n, min_mag_x10: 60, min_alert: 2, base_ppm: BigInt(chosen.base_ppm), max_event_ppm: 15000n, cooldown_s: DAY, week_cap_ppm: BigInt(chosen.week_ppm), month_cap_ppm: BigInt(chosen.month_ppm),
    min_age_s: 0, max_age_s: 90 * DAY, max_open: 64, max_claims: 32, claim_wait_s: 3600, threshold: 3, calm_ppm: 100n, giver_share_ppm: 200000n, giver_cap_ppm: 5000n, tap_amount: 0n, publishers: BOTS, relief: RELIEF };
  let sim: Tremor, now: number, modes: Mode[], claimNo = 0, last: { id: string; fake: boolean; chips: string[]; msg: string; tone: "ok" | "warn" | "info" } | null = null, busy = false;
  const reset = () => { sim = new Tremor(params, "launcher"); now = (quakes[0]?.origin_s ?? Math.floor(Date.now() / 1000)) + 3600; sim.ftTransfer("launcher", YOU, START, now); modes = [...PLAN.real]; claimNo = 0; last = null; };
  reset();

  const meter = (label: string, used: bigint, total: bigint, note: string) => {
    const pct = total > 0n ? Number((used * 10000n) / total) / 100 : 0;
    return `<div class="smeter"><div class="mh"><b>${label}</b><span>${note}</span></div><div class="bar"><i style="width:${Math.max(1.5, pct)}%"></i></div></div>`;
  };

  function render() {
    const st = sim.state(now), used = (id: string) => sim.ev.has(id);
    const options = quakes.map((q) => `<option value="${esc(q.id)}"${used(q.id) ? " disabled" : ""}>${mag(q.mag_x10)} · ${esc(q.place || "unnamed region")} · ${new Date(q.origin_s * 1000).toISOString().slice(0, 10)} · impact ${alertName(q.alert)}${q.alert >= 2 ? "" : " (too low to count)"}${used(q.id) ? " (used)" : ""}</option>`).join("");
    const sel = (host.querySelector<HTMLSelectElement>("#sim-q")?.value) ?? quakes.find((q) => !used(q.id) && q.alert >= 2)?.id ?? "__fake";
    const events = [...sim.ev.entries()].reverse().slice(0, 5);
    host.innerHTML = `
      <div class="card simbanner"><b>This is a simulation, running in your browser.</b><p>It uses the same rules code as the contract, checked against ${steps ? steps.toLocaleString("en-US") : "thousands of"} steps of the reference implementation. Nothing here is on the blockchain. The real contract is further down, on Live.</p></div>
      <div class="grid2 simgrid">
        <div class="card">
          <h3>1. Pick a quake</h3>
          <select id="sim-q" aria-label="Quake">${options}<option value="__fake">Make one up (M7.4, not in the USGS)</option></select>
          <button class="blue big" id="sim-claim" ${busy ? "disabled" : ""}>Tell the contract about it</button>
          <h3>2. Set up the five bots</h3>
          ${BOTS.map((_, i) => `<div class="botrow"><span class="bot">${i + 1}</span><span class="bn">Bot ${i + 1}</span><span class="seg mini" data-bot="${i}">${(["honest", "bad", "offline"] as Mode[]).map((m) => `<button data-m="${m}" class="${modes[i] === m ? "on" : ""}">${m === "honest" ? "Honest" : m === "bad" ? "Bad" : "Offline"}</button>`).join("")}</span></div>`).join("")}
          <p class="note"><b>Honest</b> bots attest only quakes the USGS has. <b>Bad</b> bots attest anything. <b>Offline</b> bots do nothing. A quake counts when <b>three</b> bots attest the same record, and only if the USGS expects at least <b>yellow</b> impact on people (its PAGER alert level, an estimate, not a count). Quakes with a lower level never count.</p>
          <h3>Or try a scenario</h3>
          <div class="acts"><button class="out" data-sc="real">A real quake</button><button class="out" data-sc="low">A quake with low expected impact</button><button class="out" data-sc="fake">A made-up quake</button><button class="out" data-sc="bad2">Two bad bots</button><button class="out" data-sc="bad3">Three bad bots</button><button class="out" data-sc="off3">Three bots offline</button></div>
          <h3>3. Hold coins: quakes cost you a little, calm days pay you a little</h3>
          <p class="note">You hold <b>${trem(sim.bal(YOU), 4)}</b> simulated TREM, which is <b>${(Number((sim.bal(YOU) * 100_000_000n) / sim.supply) / 1e6).toFixed(4)}%</b> of the supply. Each counted quake makes that share a little smaller. Each full day with no counted quake creates ${(Number(params.calm_ppm) / 1e4).toFixed(2)}% of the supply for holders (not for the relief accounts). It is separate from the weekly and monthly caps, which limit quake mints. Your coin count grows; your share barely moves, because nearly every coin is paid the same.</p>
          <div class="acts"><button class="out" id="sim-day">Let a calm day pass</button><span class="note">Calm days paid so far: <b>${sim.calmDays}</b>, ${trem(sim.divTotal)} TREM for holders.</span></div>
          <p class="note">You can also give: it sends your own coins to the five relief accounts, creates nothing, and gives you no say in what counts. Givers earn a bonus: ${(Number(params.giver_share_ppm) / 1e4).toFixed(0)}% of each calm day's dividend is set aside for them, and each coin given can earn up to ${(Number(params.giver_cap_ppm) / 1e4).toFixed(1)}% a day, so give, then let a few calm days pass.</p>
          <div class="acts"><button class="out" data-give="100">Give 100 TREM</button><button class="out" data-give="1000">Give 1,000 TREM</button>${sim.given.get(YOU) ? `<span class="note">You have given <b>${trem(sim.given.get(YOU)!)}</b> TREM.</span>` : ""}</div>
          <div class="acts"><button class="out" id="sim-skip">Skip ahead a week</button><button class="out" id="sim-reset">Start over</button></div>
        </div>
        <div class="card">
          <h3>What happened</h3>
          <div class="simstatus">${last ? `<p class="pick"><b>${esc(last.id)}</b></p><span class="bots">${last.chips.join("")}</span><p class="big-result simmsg ${last.tone}">${last.msg}</p>` : `<p class="note">Pick a quake and press the button, or choose a scenario. You will see each bot decide, and the coins appear.</p>`}</div>
          ${meter("This week", st.m7, st.m7 + st.weekLeft, `${trem(st.m7, 0)} of ${trem(st.m7 + st.weekLeft, 0)} TREM allowed`)}
          ${meter("This month", st.m30, st.m30 + st.monthLeft, `${trem(st.m30, 0)} of ${trem(st.m30 + st.monthLeft, 0)} TREM allowed`)}
          <p class="note">Supply: <b>${trem(sim.supply, 0)}</b> TREM (started at ${trem(params.s0, 0)}).</p>
          <h3>The five relief accounts</h3>
          <div class="reliefmini">${RELIEF.map((r, i) => `<div><small>Relief ${i + 1}</small><b>${trem(sim.bal(r))}</b></div>`).join("")}</div>
          ${events.length ? `<h3>Quakes so far</h3><ul class="simlog">${events.map(([id, e]) => `<li><b>${esc(id)}</b> ${e.status === "counted" ? `counted, +${trem(e.minted)} TREM${e.clipped ? " (cut by a cap)" : ""}` : "waiting for bots"}</li>`).join("")}</ul>` : ""}
        </div>
      </div>`;
    const s = host.querySelector<HTMLSelectElement>("#sim-q")!; if ([...s.options].some((o) => o.value === sel && !o.disabled)) s.value = sel;
  }

  async function claimAndRun(value: string) {
    if (busy) return; busy = true;
    let id: string, magx: number, origin: number, fake = false, alert = 2;
    if (value === "__fake" || !byId.has(value)) { fake = true; id = `fake-${100 + ++claimNo}`; magx = 74; origin = now - 120; }
    else { const q = byId.get(value)!; id = q.id; magx = q.mag_x10; origin = q.origin_s; alert = q.alert; }
    try { sim.submitClaim(`visitor-${++claimNo}`, id, magx, origin, now, alert); }
    catch (e) {
      const low = e instanceof Reject && /impact/.test(e.message);
      last = { id, fake, chips: [], tone: low ? "info" : "warn", msg: low ? `<b>The contract refused it.</b> The USGS expects ${alertName(alert)} impact on people for this quake, below the yellow bar, so it can never count, even if every bot attested it. Nothing was created. (The alert is a USGS estimate, not a count of people.)` : e instanceof Reject ? `The contract refused it: ${e.message}.` : "Something went wrong." };
      busy = false; render(); return;
    }
    const near = [...sim.ev.values()].some((e) => e.status === "counted" && Math.abs(e.origin_s - origin) < DAY); // within a day of an earlier counted quake: the cooldown scales it down
    const chips: string[] = BOTS.map((_, i) => `<span class="bot">${i + 1}</span>`);
    let agree = 0;
    last = { id, fake, chips: [...chips], msg: "The bots are checking…", tone: "info" }; render();
    for (let i = 0; i < BOTS.length; i++) {
      await sleep(650);
      const m = modes[i]; const rec = byId.get(id);
      let did: "yes" | "no" | "off" = "no";
      if (m === "offline") did = "off";
      else if (m === "bad") did = "yes";
      else if (rec && !fake) did = "yes"; // an honest bot attests only what the USGS record says
      if (did === "yes") {
        const useRec = m === "honest" && rec ? { mag: rec.mag_x10, origin: rec.origin_s, alert: rec.alert } : { mag: magx, origin, alert };
        try { const r = sim.attest(BOTS[i], id, useRec.mag, useRec.origin, now, useRec.alert); agree++; chips[i] = `<span class="bot yes" title="attested">✓</span>`; if (r) break; } catch { chips[i] = `<span class="bot" title="refused">–</span>`; }
      } else chips[i] = `<span class="bot ${did === "off" ? "off" : "no"}" title="${did === "off" ? "offline" : "found nothing in the USGS"}">${did === "off" ? "×" : "–"}</span>`;
      last = { id, fake, chips: [...chips], msg: "The bots are checking…", tone: "info" }; render();
    }
    const e = sim.ev.get(id)!, st = sim.state(now);
    if (e.status === "counted") {
      const each = e.minted / 5n; const cool = near ? " It is smaller than a lone quake would be: it fell within a day of an earlier one, so the cooldown scaled it down." : "";
      last = { id, fake, chips, tone: fake ? "warn" : "ok", msg: fake
        ? `<b>Three bad bots made a quake that does not exist count: +${trem(e.minted)} TREM.</b> This is the weak spot of the design. The caps still limit the damage (this week can still create ${trem(st.weekLeft, 0)} TREM).${cool}`
        : `<b>Counted: +${trem(e.minted)} TREM</b> created and split between the five relief accounts (${trem(each)} each), because three bots agreed.${e.clipped ? " A safety cap trimmed it." : ""}${cool}` };
    } else {
      const off = modes.filter((m) => m === "offline").length;
      last = { id, fake, chips, tone: "info", msg: fake && agree === 0 ? "<b>Not confirmed.</b> No honest bot can find this quake in the USGS record, so none attested it. Nothing was created."
        : `<b>Not confirmed:</b> only ${agree} of the 3 needed bots attested it, so nothing was created.${off ? ` ${off} bot${off > 1 ? "s are" : " is"} offline.` : ""}` };
    }
    busy = false; render();
  }

  host.addEventListener("click", (ev) => {
    const t = (ev.target as HTMLElement).closest<HTMLElement>("button"); if (!t || busy) return;
    if (t.id === "sim-claim") return void claimAndRun(host.querySelector<HTMLSelectElement>("#sim-q")!.value);
    if (t.id === "sim-reset") { reset(); return render(); }
    if (t.id === "sim-skip" || t.id === "sim-day") {
      const week = t.id === "sim-skip", before = sim.calmDays; now += (week ? 7 : 1) * DAY;
      const made = sim.roll(now), mine = sim.given.get(YOU) ?? 0n, bonus = (mine * (sim.gacc - (sim.gpaid.get(YOU) ?? 0n))) / SCALE; // the giver bonus part of what you are owed
      let got = 0n; try { got = sim.claimDividend(YOU, now); } catch { /* nothing to claim */ }
      const days = sim.calmDays - before;
      const paid = days ? ` ${days} calm day${days > 1 ? "s" : ""} paid a dividend: ${trem(made)} TREM created for holders, and <b>${trem(got, 4)} TREM</b> of it is yours${bonus > 0n ? `, of which <b>${trem(bonus, 4)} TREM</b> is your giver bonus` : ""}.` : " No dividend was paid: a quake was counted that day.";
      last = { id: week ? "A week passes" : "A day passes", fake: false, chips: [], tone: days ? "ok" : "info", msg: (week ? "The weekly allowance resets, so new quakes can mint again. The monthly allowance stays." : "No quake was claimed, so the day is settled when the next one starts.") + paid };
      return render();
    }
    if (t.dataset.give) {
      const n = BigInt(t.dataset.give) * 1_000_000n;
      try { const total = sim.give(YOU, n, now); last = { id: "A gift", fake: false, chips: [], tone: "ok", msg: `<b>You gave ${trem(n)} TREM.</b> Each relief account received ${trem(n / 5n)}. The supply did not change and the caps did not move: a gift is your own coins, not new ones. Your total given is ${trem(total)} TREM.` }; }
      catch (e) { last = { id: "A gift", fake: false, chips: [], tone: "warn", msg: e instanceof Reject ? "The contract refused it: you do not hold that many coins." : "Something went wrong." }; }
      return render();
    }
    if (t.dataset.m) { const i = Number((t.parentElement as HTMLElement).dataset.bot); modes[i] = t.dataset.m as Mode; return render(); }
    if (t.dataset.sc) {
      const sc = t.dataset.sc; modes = [...PLAN[sc]];
      const next = quakes.find((q) => !sim.ev.has(q.id) && q.alert >= 2), low = quakes.find((q) => !sim.ev.has(q.id) && q.alert < 2);
      if (sc === "low") { if (!low) { last = { id: "No more low-impact quakes", fake: false, chips: [], tone: "info", msg: "Every low-impact quake in the catalog has been tried. Press “Start over”." }; return render(); } return void claimAndRun(low.id); }
      if ((sc === "real" || sc === "off3") && !next) { last = { id: "All counting quakes used", fake: false, chips: [], tone: "info", msg: "Every quake in the catalog that can count has been used. Press “Start over”." }; return render(); }
      return void claimAndRun(sc === "real" || sc === "off3" ? next!.id : "__fake");
    }
  });
  render();
}
