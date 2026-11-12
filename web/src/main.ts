import "./style.css";
import { EXPLORER, POLL_MS } from "./config";
import { DEP, NET, loadDeployments } from "./deployment";
// the wallet library is large, so it loads on demand
const wallet = () => import("./wallet");
const send = async (m: string, a: object, d = "0") => (await wallet()).send(m, a, d);
import { accessKeyCount, giverRounds, listEvents, listGivers, registered, unconfirmed, view, type Ev, type Params, type State } from "./chain";
import { alertName, checkEvent, loadCatalog, recentM6, usgsPage, type Flag, type Quake } from "./usgs";
import { $, ago, countUp, duration, esc, mag, md, pct, reveal, short, trem } from "./util";
import { renderCharts } from "./charts";
import { botChips, renderJourney, type Ctx } from "./journey";
import { initDecide } from "./decide";
import { initSimulator } from "./simulator";
import { initMap } from "./map";
import { Seismo } from "./seismo";
import { ampFor, shake } from "./shake";

let params: Params | null = null, skew = 0;
const flags = new Map<string, Flag>();
const nowS = () => Math.floor(Date.now() / 1000) + skew;

function banner(msg: string | null) { const b = $("#banner"); b.hidden = !msg; if (msg) b.textContent = msg; }

function renderChips(s: State) {
  countUp($("#c-supply"), Number(BigInt(s.supply) / 10_000n) / 100, (n) => n.toLocaleString("en-US", { maximumFractionDigits: 0 }));
  countUp($("#c-7d"), Number(BigInt(s.minted_7d) / 10_000n) / 100, (n) => n.toLocaleString("en-US", { maximumFractionDigits: 0 }));
  countUp($("#c-open"), s.pending_events, (n) => String(Math.round(n)));
}

function meter(prefix: "wk" | "mo", minted: string, left: string, label: string) {
  const m = BigInt(minted), l = BigInt(left), total = m + l, used = total ? Number((m * 10000n) / total) / 10000 : 0;
  $(`#${prefix}-t`).textContent = `${trem(m, 0)} of ${trem(total, 0)} TREM used`;
  requestAnimationFrame(() => ($(`#${prefix}-bar`).style.width = Math.max(1.5, used * 100) + "%"));
  const window_ = prefix === "wk" ? "7" : "30";
  const full = used >= 0.95
    ? ` <b>The allowance is nearly full.</b> This happens when the bots count several older quakes at once (for example after the contract starts, or after the bots were off): the cap goes by when coins are created, not when the quake happened, so they all land in the same ${prefix === "wk" ? "week" : "month"}. Quakes counted now are cut to almost nothing until older days leave the ${window_}-day window. It is the cap doing its job, not a fault.`
    : "";
  $(`#${prefix}-n`).innerHTML = `${pct(used)} of the ${esc(label)} allowance is used. ${trem(l, 0)} TREM can still be created.${full}`;
}

function renderMeters(s: State, p: Params) {
  meter("wk", s.minted_7d, s.week_left, `${(p.week_cap_ppm / 1e4).toFixed(1)}% weekly`);
  meter("mo", s.minted_30d, s.month_left, `${(p.month_cap_ppm / 1e4).toFixed(1)}% monthly`);
  const ratio = Number(BigInt(s.supply) * 10000n / BigInt(s.initial_supply)) / 10000;
  $("#sp-t").textContent = `${trem(s.supply, 0)} TREM · ${pct(ratio - 1, 2)} above the ${trem(s.initial_supply, 0)} start`;
  requestAnimationFrame(() => ($("#sp-bar").style.width = Math.min(100, (ratio - 1) / (p.month_cap_ppm / 1e6) * 100) + "%"));
}

function flagHtml(id: string): string {
  const f = flags.get(id);
  if (!f) return `<span class="flag unknown">Checking USGS…</span>`;
  return `<span class="flag ${f.kind}">${f.kind === "match" ? "✓" : f.kind === "unknown" ? "…" : "⚠"} ${esc(f.text)}</span>`;
}

let me: string | null = null;
function stateOf(e: Ev): { key: string; text: string } {
  if (e.status === "counted") return { key: "counted", text: "Counted" };
  if (unconfirmed(e, nowS())) return { key: "rejected", text: "Not confirmed" };
  return { key: "waiting", text: e.attestations > 0 ? "Bots are confirming" : "Waiting for the bots" };
}

function card(e: Ev, p: Params): string {
  const st = stateOf(e);
  let line = "";
  if (e.status === "counted") line = `<b>+${trem(e.minted)} TREM</b> created for the relief list${e.clipped ? " <span class='clip'>cut by a cap</span>" : ""}`;
  else if (st.key === "rejected") line = "No bot found it in the USGS record: nothing was created";
  else line = `${e.attestations} of ${e.needed} bots agree${e.claim_open_until ? ` · claim open for <b class="cd" data-end="${e.claim_open_until}">${duration(e.claim_open_until - nowS())}</b>` : ""}`;
  const by = e.claimer ? `claimed by ${esc(short(e.claimer))}` : "found by the bots";
  return `<article class="ev ${st.key}"><header><span class="mag">${mag(e.mag_x10)}</span><span class="pill st-${st.key}">${st.text}</span></header>
    <p class="meta"><code>${esc(e.event_id)}</code> · ${by} ${ago(nowS() - e.created_at)}${e.alert ? ` · USGS expected impact: ${alertName(e.alert)}` : ""}</p>${flagHtml(e.event_id)}${botChips(e, p)}
    <p class="line">${line}</p>
    <a class="usgs" href="${usgsPage(e.event_id)}" target="_blank" rel="noopener">USGS page ↗</a></article>`;
}

let boardSig = "";
function renderBoard(evs: Ev[], p: Params) {
  const board = $("#board");
  const sig = (me ?? "") + JSON.stringify(evs) + [...flags.entries()].map(([k, f]) => k + f.kind).join() + Math.floor(nowS() / 60);
  if (sig === boardSig) return; // unchanged: keep the DOM so card animations do not restart every poll
  boardSig = sig;
  if (!evs.length) { board.innerHTML = `<div class="empty card"><b>No quake has counted on Live yet.</b> A quake appears here only when the USGS expects it to affect people (alert level yellow or higher) and the bots have picked it up, which can take days. To see the whole flow now, use the simulation above or the recorded bot run under <a href="#evidence-run">Evidence</a>.</div>`; return; }
  board.innerHTML = [...evs].sort((a, b) => b.created_at - a.created_at).map((e) => card(e, p)).join("");
  evs.forEach((e) => { const k = e.event_id; if (!flags.has(k) && e.mag_x10) checkEvent(k, e.mag_x10, e.origin_s, e.alert ?? 0).then((f) => { flags.set(k, f); renderBoardFlags(); }); });
}
let lastEvs: Ev[] = [], lastState: State | null = null;
function renderBoardFlags() { if (params && lastState) renderBoard(lastEvs, params); }

function tickCountdowns() { document.querySelectorAll<HTMLElement>(".cd").forEach((n) => { const r = Number(n.dataset.end) - nowS(); n.textContent = duration(r); if (r <= 0 && !n.classList.contains("done")) { n.classList.add("done"); boardSig = ""; renderBoardFlags(); renderJourneyNow(); } }); }

async function renderRelief(p: Params) {
  const bals = await Promise.all(p.relief_accounts.map((a) => view<string>("ft_balance_of", { account_id: a })));
  $("#relief-list").innerHTML = p.relief_accounts.map((a, i) => `<div><small>${esc(short(a))}</small><b>${trem(bals[i], 0)}</b> <small>TREM received</small></div>`).join("");
}

async function renderUnreported(evs: Ev[], p: Params) {
  const host = $("#unrep");
  try {
    const known = new Set(evs.map((e) => e.event_id));
    const all = (await recentM6(Math.min(60, Math.floor(p.max_age_s / 86400)))).filter((q: Quake) => !known.has(q.id));
    const bar = p.min_alert ?? 1, qs = all.filter((q: Quake) => q.alert >= bar), below = all.length - qs.length; // the rest are below the impact bar (or have no alert yet) and cannot count
    unreported = qs; checkingQuakes = false; renderJourneyNow();
    const rows = qs.map((q, i) => `<div class="row card slim${i >= 6 ? " extra" : ""}"${i >= 6 ? " hidden" : ""}><span class="mag sm">${mag(q.mag_x10)}</span><span>${esc(q.place || "Unnamed region")}</span><span class="note">${ago(nowS() - q.origin_s)} · USGS ${esc(q.status)}</span><a href="${usgsPage(q.id)}" target="_blank" rel="noopener">USGS ↗</a></div>`).join("");
    host.innerHTML = (qs.length ? rows + (qs.length > 6 ? `<button class="btn" id="more">Show all ${qs.length}</button>` : "") : `<div class="card slim">Every USGS event of M6+ with expected impact of ${alertName(bar)} or higher in the last 60 days has been reported.</div>`) + (below ? `<p class="note">${below} other M6+ quake${below > 1 ? "s" : ""} in that time ${below > 1 ? "are" : "is"} below the impact bar (or USGS has not published an alert level yet), so ${below > 1 ? "they do" : "it does"} not count.</p>` : "");
    const more = host.querySelector<HTMLButtonElement>("#more");
    if (more) more.onclick = () => { host.querySelectorAll<HTMLElement>(".extra").forEach((n) => (n.hidden = false)); more.remove(); };
  } catch { checkingQuakes = false; host.innerHTML = `<div class="card slim">Could not reach USGS right now.</div>`; }
}

function renderParams(p: Params) {
  const rows: [string, string][] = [
    ["Initial supply", `${trem(p.s0, 0)} TREM`], ["Minimum magnitude", `M${(p.min_mag_x10 / 10).toFixed(1)}`], ...(p.min_alert ? [["Minimum expected impact (USGS PAGER alert)", `${alertName(p.min_alert)} or higher`] as [string, string]] : []),
    ["Bots that decide (fixed at launch)", `${p.publisher_accounts.length}`], ["Bots that must agree", `${p.threshold} of ${p.publisher_accounts.length}`],
    ["A quake must be this old before bots confirm it", duration(p.min_age_s)],
    ["Mint at M6.0 (×2 at M7, ×3 at M8)", `${(p.base_ppm / 1e4).toFixed(2)}% of supply`], ["Most one event can mint", `${(p.max_event_ppm / 1e4).toFixed(1)}% of supply`],
    ...(p.match_ppm ? [["Donation match (from the reserve, never minted)", `${(p.match_ppm / 1e4).toFixed(0)}% of each gift`] as [string, string], ["Most the match adds in a day / over 30 days", `${(p.match_day_ppm! / 1e4).toFixed(1)}% / ${(p.match_month_ppm! / 1e4).toFixed(1)}% of supply`] as [string, string], ["Most the match adds for one account, ever", `${trem(p.match_account_max ?? "0", 0)} TREM`] as [string, string]] : []),
    ["Cooldown (aftershocks mint less)", duration(p.cooldown_s)], ["Weekly cap", `${(p.week_cap_ppm / 1e4).toFixed(1)}% of supply`], ["Monthly cap", `${(p.month_cap_ppm / 1e4).toFixed(1)}% of supply`],
    ["Oldest quake that can count", duration(p.max_age_s)], ["Open visitor claims at once", `${p.max_claims}`],
  ];
  $("#params-t").innerHTML = rows.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join("");
}

async function refresh() {
  try {
    const [s, evs] = await Promise.all([view<State>("get_state"), listEvents()]);
    if (!params) { params = await view<Params>("get_params"); renderParams(params); renderRelief(params); }
    skew = s.now_s - Math.floor(Date.now() / 1000); lastEvs = evs; lastState = s; state0 = s; renderWallet();
    banner(null); renderJourneyNow(); renderChips(s); renderMeters(s, params); renderBoard(evs, params); renderUnreported(evs, params); renderRelief(params);
    if (s.given_total !== undefined) renderGivers(s);
    if (s.reserve !== undefined && params.match_ppm) {
      $("#match-card").hidden = false;
      $("#match-t").textContent = `${trem(s.reserve, 0)} TREM left in the reserve`;
      $("#match-n").innerHTML = `When someone gives coins to the relief list, the reserve adds ${(params.match_ppm / 1e4).toFixed(0)}% on top of the gift. The match is never newly created: it comes from coins people put into the reserve (${trem(s.funded_total ?? "0", 0)} TREM so far), and ${trem(s.matched_total ?? "0", 0)} TREM has been matched. It goes to the relief accounts, not to the giver. Limits: at most ${(params.match_day_ppm! / 1e4).toFixed(1)}% of supply a day (${trem(s.match_day_left ?? "0", 0)} TREM left today) and ${(params.match_month_ppm! / 1e4).toFixed(1)}% over 30 days (${trem(s.match_month_left ?? "0", 0)} TREM left), and ${trem(params.match_account_max ?? "0", 0)} TREM for any one account, ever. When the reserve is empty, gifts still go through, just without a match. Anyone can add coins to it; nobody can take them out.`;
    }
    accessKeyCount().then((n) => { $("#keys-line").innerHTML = `<b>${n}</b> access key${n === 1 ? "" : "s"}`; }).catch(() => ($("#keys-line").textContent = "unavailable"));
  } catch (e) { banner("Could not read the testnet contract right now. This page is read-only and will retry. " + (e instanceof Error ? e.message.slice(0, 120) : "")); }
}

// The givers board: only on a contract deployed with give(); the section stays hidden otherwise.
// Recognition tiers by total given. They are labels, not powers: the starter coins are 5,000, so Gold needs more than the free coins.
const tier = (given: string): { key: string; name: string } | null => { const t = BigInt(given) / 1_000_000n; return t >= 5000n ? { key: "gold", name: "Gold" } : t >= 1000n ? { key: "silver", name: "Silver" } : t >= 100n ? { key: "bronze", name: "Bronze" } : null; };
async function renderGivers(s: State) {
  const gs = await listGivers(); if (!gs) return;
  const rounds = await giverRounds().catch(() => new Map<string, number>());
  $("#givers").hidden = false;
  const total = BigInt(s.given_total ?? "0"), minted = BigInt(s.supply) - BigInt(s.initial_supply);
  const head = `<p class="big-n"><b>${trem(total)}</b> TREM given by ${gs.length} account${gs.length === 1 ? "" : "s"}</p><p class="note">Quakes have created ${trem(minted)} TREM for the relief list. Gifts are on top of that, and come out of the givers' own coins. The board ranks by amount, so a large holder can top it; it is a record, not a power.</p>`;
  const bonus = s.matched_total !== undefined && params?.match_ppm ? `<p class="note"><b>Gifts are matched.</b> The reserve has added ${trem(s.matched_total, 0)} TREM to gifts so far, and ${trem(s.reserve ?? "0", 0)} TREM is left. Givers get recognition, not a payout: the match goes to relief.</p>` : "";
  const key = `<p class="note">Tiers by total given: Bronze 100 TREM, Silver 1,000, Gold 5,000. <b>Quake rounds</b> counts how many times the account gave after at least one new quake had counted since its previous gift.</p>`;
  const rows = gs.slice(0, 20).map((g, i) => `<tr><td>${i + 1}</td><td>${esc(g.account_id)}${g.account_id === me ? " <b>(you)</b>" : ""}</td><td>${(() => { const t = tier(g.given); return t ? `<span class="tier ${t.key}">${t.name}</span>` : ""; })()}</td><td>${trem(g.given)} TREM</td><td>${rounds.get(g.account_id) ?? 0}</td></tr>`).join("");
  $("#givers-card").innerHTML = head + bonus + key + (gs.length ? `<div class="tbl"><table><thead><tr><th>#</th><th>Account</th><th>Tier</th><th>Given</th><th>Quake rounds</th></tr></thead><tbody>${rows}</tbody></table></div>${gs.length > 20 ? `<p class="note">Showing the first 20 of ${gs.length}.</p>` : ""}` : `<p class="note">Nobody has given yet. Connect a wallet above, take the free starter coins, and be the first.</p>`);
}

async function initSim() {
  try {
    const ch = await (await fetch("sim/chosen.json")).json(); const c = ch.chosen;
    $("#sim-sub").textContent = `The rules ran against 60 real days of USGS data and eight scenarios (honest bots, a swarm, bad bots, offline bots, claim spam, holders giving, the donation match, the impact bar). ${ch.n_pass} of ${ch.n_grid} parameter combinations passed every threshold we wrote down first; we kept the rules we had already confirmed.`;
    $("#sim-cards").innerHTML = [
      ["Chosen rules", `${(c.base_ppm / 1e4).toFixed(2)}% base · ${(c.week_ppm / 1e4).toFixed(1)}% weekly · ${(c.month_ppm / 1e4).toFixed(0)}% monthly cap`, "Picked from the grid by the simulation, then confirmed"],
      ["A passive holder, 60 real days", `${pct(c.s1_dilution, 2)} diluted`, `Only quakes USGS expects to affect people count: 5 of the 28 M6+ quakes. Caps bound in ${pct(c.s1_clipped_weeks, 0)} of weeks.`],
      ["Trust sits in the bots", "3 of 5 must agree", "Two bad bots mint nothing; three can mint fakes, but only up to the caps. Three offline bots mint nothing."],
    ].map(([a, b, d]) => `<div class="card stat reveal"><small>${esc(a)}</small><b>${esc(b)}</b><p class="note">${esc(d)}</p></div>`).join("");
    await renderCharts($("#charts"), Number(BigInt(params?.s0 ?? "1000000000000")));
    $("#summary").innerHTML = md(await (await fetch("sim/SUMMARY.md")).text());
    reveal();
  } catch { $("#sim-sub").textContent = "Simulation results could not be loaded."; }
}

$("#lookup").addEventListener("submit", async (ev) => {
  ev.preventDefault(); const out = $("#lookup-out"), id = ($("#acct") as HTMLInputElement).value.trim();
  if (!/^[a-z0-9._-]{2,64}$/.test(id)) { out.textContent = "Enter a valid account name, like name.testnet."; return; }
  out.textContent = "Looking up…";
  try { const b = await view<string>("ft_balance_of", { account_id: id }); out.innerHTML = `<b>${esc(id)}</b>: ${trem(b)} TREM.`; }
  catch { out.textContent = "That account has no Tremor balance, or the lookup failed."; }
});

initTabs();
reveal();
start();
initMotion();
loadCatalog().then(async (c) => {
  initHero(c);
  try { const ch = await (await fetch("sim/chosen.json")).json(); const rs = await fetch("results.json").then((r) => (r.ok ? r.json() : null)).catch(() => null);
    await initSimulator($("#sim-host"), c, ch.chosen, rs?.web_conformance?.steps); } catch { $("#sim-host").innerHTML = "<p class='note'>The simulation could not be loaded.</p>"; }
  return initMap($("#mapcard"), c);
}).catch(() => ($("#mapcard").innerHTML = "<p class='note'>The catalog could not be loaded.</p>"));

// ---- earthquake motion -------------------------------------------------------------------------------------------------
const esc2 = esc;
function initMotion() {
  // 1. nav trace: a thin seismogram that shakes with how fast you scroll
  const nav = new Seismo($<HTMLCanvasElement>("#navtrace"), { speed: 70, color: "rgba(112,112,112,.75)", baseline: 0.06 });
  nav.start();
  let lastY = scrollY, lastT = performance.now();
  addEventListener("scroll", () => {
    const t = performance.now(), v = Math.abs(scrollY - lastY) / Math.max(1, t - lastT) * 1000; lastY = scrollY; lastT = t;
    nav.setExternal(Math.min(1, v / 2500));
  }, { passive: true });
  setInterval(() => { if (performance.now() - lastT > 120) nav.setExternal(0); }, 120);
}

function initHero(cat: Quake[]) {
  const big = cat.filter((q) => q.mag_x10 >= 60).sort((a, b) => a.origin_s - b.origin_s);
  if (!big.length) return;
  const cap = $("#quake-cap"), hero = $("#hero"), main = $("main");
  const parts = [$(".shake-a"), $(".shake-b")];
  const caption = (q: Quake) => { cap.innerHTML = `<b>${esc2(mag(q.mag_x10))}</b> · ${esc2(q.place || "unnamed region")} · USGS expected impact: ${esc2(alertName(q.alert))}${q.alert >= 2 ? " (counts)" : " (does not count)"} · replayed from the committed catalog`; };
  const onS = (amp: number) => { const a = 2 + amp * 9; parts.forEach((el, i) => shake(el, a * (i ? 0.8 : 1))); shake(main, a * 0.35, 1400); };
  const seismo = new Seismo($<HTMLCanvasElement>("#seismo"), { speed: 110, color: "#1d1d1f", grid: "#e6e6e8", labels: true, onS });
  let i = Math.floor(Math.random() * big.length), timer: number | undefined;
  const fire = (q: Quake) => { caption(q); seismo.burst(q.mag_x10); };
  const next = () => { fire(big[i++ % big.length]); };
  const loop = () => { timer = window.setTimeout(() => { if (!document.hidden) next(); loop(); }, 9000); };
  new IntersectionObserver(([e]) => {
    if (e.isIntersecting) { seismo.start(); if (!timer) { timer = window.setTimeout(() => { next(); loop(); }, 1200); } }
    else { seismo.stop(); clearTimeout(timer); timer = undefined; }
  }).observe(hero);
  $("#feel").addEventListener("click", () => { const q = big[Math.floor(Math.random() * big.length)]; fire(q); window.setTimeout(() => shake(main, ampFor(q.mag_x10) * 0.6, 1800), 1400); });
  if (reducedMotionNote()) caption(big[0]);
}
function reducedMotionNote() { return matchMedia("(prefers-reduced-motion: reduce)").matches; }

// ---- deployments, wallet and actions ---------------------------------------------------------------------------------------
const toastEl = () => $("#toast");
let toastTimer: number | undefined;
function toast(msg: string, ms = 6000) { const t = toastEl(); t.textContent = msg; t.hidden = false; clearTimeout(toastTimer); toastTimer = window.setTimeout(() => (t.hidden = true), ms); }

function renderSteps() {
  $("#modebar").innerHTML = `<div class="mode warn slim"><div><b>The real contract is slow.</b><p>A quake is confirmed once it is ${duration(params?.min_age_s ?? 21600)} old, and the bots run every 20 minutes, so a result takes hours. For an instant feel, use the simulation above.</p></div></div>`;
}

// what we know about the connected account, and the guided path built from it
const mine = { tok: 0n, tapped: false, reg: false, given: 0n };
let unreported: Quake[] = [], checkingQuakes = true;
let ignoreBefore = Number((() => { try { return sessionStorage.getItem("tremor-ignore"); } catch { return 0; } })() ?? 0);
function renderJourneyNow() {
  const c: Ctx = { me, params, state: state0, evs: lastEvs, now: nowS(), tok: mine.tok, tapped: mine.tapped, unreported, net: NET, ignoreBefore, checking: checkingQuakes, realQuake: (() => { const e = me ? lastEvs.filter((x) => x.claimer === me && x.created_at > ignoreBefore).sort((a, b) => b.created_at - a.created_at)[0] : undefined; return e ? flags.get(e.event_id)?.kind === "match" : undefined; })() };
  const host = $("#journey-host");
  const active = document.activeElement as HTMLElement | null;
  if (active && host.contains(active) && active.tagName === "INPUT") return; // do not rebuild under someone who is typing
  host.innerHTML = renderJourney(c);
}
async function loadMine() {
  if (!me) { Object.assign(mine, { tok: 0n, tapped: false, reg: false, given: 0n }); renderWallet(); renderJourneyNow(); return; }
  try {
    const [bal, tapped, reg] = await Promise.all([view<string>("ft_balance_of", { account_id: me }), view<boolean>("has_tapped", { account_id: me }), registered(me)]);
    Object.assign(mine, { tok: BigInt(bal), tapped, reg });
    mine.given = BigInt(await view<string>("given_of", { account_id: me }).catch(() => "0"));
  } catch { /* keep the last known values */ }
  renderWallet(); renderJourneyNow();
}

function renderWallet() {
  const bar = $("#wallet-card");
  if (!me) {
    bar.innerHTML = `<div class="ab"><div><b>Your wallet</b><p class="note first">Not connected. Connect a free testnet wallet (Meteor, switched to <b>testnet</b>) to use the three actions below. Nothing here has any value.</p></div><button class="blue big" data-j="connect">Connect wallet</button></div>`;
  } else {
    bar.innerHTML = `<div class="ab"><div><small>Connected as</small><b class="acc">${esc(me)}</b></div><div class="two"><div><small>Your coins</small><b>${trem(mine.tok)}</b><span>TREM</span></div>${mine.given > 0n ? `<div><small>Given so far</small><b>${trem(mine.given)}</b><span>TREM</span></div>` : ""}</div><button class="out" id="w-out">Disconnect</button></div>`;
  }
  // 1. coins
  const tapOn = params && BigInt(params.tap_amount) > 0n;
  $("#coins-body").innerHTML = !me ? `<p class="note first">Connect a wallet first.</p>` :
    `<p class="note first">${tapOn ? `Every account can take ${trem(params!.tap_amount, 0)} free starter TREM, once. They come from a pool the launcher filled, and no new coins are created. You need coins only to give or to see dilution; claiming a quake needs none.` : "Starter coins are not offered on this contract."}</p>
     ${tapOn ? `<div class="acts"><button class="blue" id="w-tap" ${mine.tapped ? "disabled" : ""}>${mine.tapped ? "Starter coins taken ✓" : `Get ${trem(params!.tap_amount, 0)} starter TREM`}</button></div>` : ""}`;
  // 2. give (the relief list itself is static in the page and filled by renderRelief)
  const giveOn = state0?.given_total !== undefined, fundOn = state0?.reserve !== undefined;
  const ml = $("#match-line");
  ml.innerHTML = state0?.reserve !== undefined && params?.match_ppm ? `<b>Gifts are topped up ${(params.match_ppm / 1e4).toFixed(0)}%</b> from a reserve of existing coins (${trem(state0.reserve, 0)} TREM left). The extra goes to the relief accounts, not to you.` : "";
  const host = $("#give-body");
  const active = document.activeElement as HTMLElement | null;
  if (active && host.contains(active) && active.tagName === "INPUT") return; // do not rebuild under someone who is typing
  host.innerHTML = !me ? `<p class="note">Connect a wallet to give.</p>` : !giveOn ? "" : mine.tok <= 0n ? `<p class="note">You hold no coins yet: take the starter coins in step 1.</p>` :
    `<div class="acts"><input id="w-give" type="number" min="1" step="1" value="${mine.tok >= 100_000_000n ? 100 : 1}" aria-label="TREM to give"><span class="note nm">TREM</span><button class="blue" id="w-givebtn">Give to the relief list</button></div>
     <p class="note" id="w-giveprev">Giving sends your own coins to the five relief accounts. It cannot be undone.</p>
     ${fundOn ? `<details class="mk"><summary>Add coins to the matching reserve instead</summary><div class="acts"><input id="w-fund" type="number" min="1" step="1" value="10" aria-label="TREM to put in the reserve"><span class="note nm">TREM</span><button class="out" id="w-fundbtn">Put coins in the reserve</button></div><p class="note">Optional. These coins can only leave the reserve as matches added to gifts: nobody can take them back, including you.</p></details>` : ""}`;
}
let state0: State | null = null;

async function act(label: string, fn: () => Promise<unknown>) {
  try { toast(`${label}: approve it in your wallet…`, 20000); await fn(); toast(`${label}: sent. Refreshing…`); }
  catch (e) { toast(`${label} did not go through: ${(e instanceof Error ? e.message : String(e)).slice(0, 160)}`, 9000); return; }
  for (const ms of [2500, 5000, 9000, 15000]) setTimeout(() => { refresh(); loadMine(); }, ms);
}

// ---- tabs and navigation ---------------------------------------------------------------------------------------------------
// Two tabbed sections (Live and Evidence). A tab can be opened by a link like #live-quakes or #evidence-run; #real (an old link) opens the wallet tab.
type TabBar = HTMLElement & { showTab?: (k: string) => void };
function initTabs() {
  document.querySelectorAll<TabBar>("[data-tabs]").forEach((bar) => {
    const group = bar.dataset.tabs!;
    const show = (k: string) => {
      bar.querySelectorAll<HTMLButtonElement>("button").forEach((b) => { const on = b.dataset.tab === k; b.classList.toggle("on", on); b.setAttribute("aria-selected", String(on)); });
      document.querySelectorAll<HTMLElement>(`[data-panel^="${group}:"]`).forEach((p) => (p.hidden = p.dataset.panel !== `${group}:${k}`));
    };
    bar.showTab = show;
    bar.addEventListener("click", (e) => { const b = (e.target as HTMLElement).closest<HTMLButtonElement>("button"); if (b) show(b.dataset.tab!); });
    show(bar.querySelector("button")!.dataset.tab!);
  });
  const go = () => {
    const h = location.hash === "#real" || location.hash === "#live-relief" ? "#live-wallet" : location.hash, m = h.match(/^#(live|evidence)-(\w+)$/); if (!m) return;
    const bar = document.querySelector<TabBar>(`[data-tabs="${m[1]}"]`); if (!bar?.querySelector(`[data-tab="${m[2]}"]`)) return;
    bar.showTab!(m[2]); setTimeout(() => document.getElementById(m[1])?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  };
  addEventListener("hashchange", go); go();
  // the nav link for the section being read is underlined
  const links = [...document.querySelectorAll<HTMLAnchorElement>(".gnav nav a")], secs = links.map((a) => document.querySelector<HTMLElement>(a.getAttribute("href")!));
  const spy = () => { let on = -1; secs.forEach((s, i) => { if (s && s.getBoundingClientRect().top < innerHeight * 0.35) on = i; }); links.forEach((a, i) => a.classList.toggle("on", i === on)); };
  addEventListener("scroll", spy, { passive: true }); spy();
}
document.addEventListener("input", async (ev) => {   // show what the reserve would add to the gift being typed
  const el = ev.target as HTMLInputElement; if (el.id !== "w-give" || !me || !params?.match_ppm) return;
  const n = Math.floor(Number(el.value)); const out = document.getElementById("w-giveprev"); if (!out) return;
  if (!(n > 0)) { out.textContent = "Enter a whole number of TREM."; return; }
  try { const m = BigInt(await view<string>("match_preview", { account_id: me, amount: String(BigInt(n) * 1_000_000n) })); out.innerHTML = m > 0n ? `Your gift of <b>${n.toLocaleString("en-US")}</b> TREM would be topped up by <b>${trem(m)}</b> TREM from the reserve, so the relief accounts receive ${trem(BigInt(n) * 1_000_000n + m)} TREM. The extra is not newly created and does not go to you.` : `The reserve would add nothing to this gift (it is empty, or a budget or your allowance is used up). The gift itself goes through.`; } catch { /* keep the text */ }
});
document.addEventListener("click", (ev) => {
  const t = ev.target as HTMLElement; const el = t.closest<HTMLElement>("button,a[data-j]"); if (!el) return;
  const j = el.dataset.j;
  if (j) {
    ev.preventDefault();
    if (j === "connect") return void wallet().then((w) => w.connectWallet());
    if (j === "tap") return void registered(me!).then((reg) => act("Starter coins", () => send("tap", {}, reg ? "0" : "1250000000000000000000")));
    if (j === "claim") return void act("Claim", () => send("submit_claim", { event_id: el.dataset.id, mag_x10: Number(el.dataset.mag), origin_s: Number(el.dataset.origin), alert: Number(el.dataset.alert) }));
    if (j === "fake") return void act("Claim", () => send("submit_claim", { event_id: "fake-" + Math.floor(100 + Math.random() * 900), mag_x10: 74, origin_s: nowS() - 120, alert: 2 }));
    if (j === "again") { ignoreBefore = nowS(); try { sessionStorage.setItem("tremor-ignore", String(ignoreBefore)); } catch { /* ignore */ } return void renderJourneyNow(); }
    return;
  }
  if (el.id === "w-out") return void wallet().then((w) => w.disconnectWallet()).then(() => { me = null; loadMine(); boardSig = ""; renderBoardFlags(); });
  if (el.id === "w-tap") return void registered(me!).then((reg) => act("Starter coins", () => send("tap", {}, reg ? "0" : "1250000000000000000000")));
  if (el.id === "w-fundbtn") { const n = Math.floor(Number(($("#w-fund") as HTMLInputElement).value));
    if (!(n > 0) || BigInt(n) * 1_000_000n > mine.tok) return void toast("Enter a whole number of TREM, no more than you hold.");
    return void act("Reserve", () => send("fund_match", { amount: String(BigInt(n) * 1_000_000n) }, "1")); }
  if (el.id === "w-givebtn") { const n = Math.floor(Number(($("#w-give") as HTMLInputElement).value));
    if (!(n > 0) || BigInt(n) * 1_000_000n > mine.tok) return void toast("Enter a whole number of TREM, no more than you hold.");
    return void act("Gift", () => send("give", { amount: String(BigInt(n) * 1_000_000n) }, "1")); }
  if (el.id === "w-fake") { const id = ($("#w-fid") as HTMLInputElement).value.trim(), m = Math.round(Number(($("#w-fmag") as HTMLInputElement).value) * 10);
    return void act("Claim", () => send("submit_claim", { event_id: id, mag_x10: m, origin_s: nowS() - 120, alert: 2 })); }
});

async function start() {
  await loadDeployments();
  for (const id of ["#contract-link", "#contract-link2"]) { $(id).setAttribute("href", EXPLORER + DEP.contract); $(id).textContent = DEP.contract; }
  renderSteps(); renderWallet(); renderJourneyNow(); initDecide($("#decide-host"));
  if (new URLSearchParams(location.search).has("transactionHashes")) { toast("Transaction sent from your wallet. Refreshing…"); const u = new URL(location.href); u.searchParams.delete("transactionHashes"); history.replaceState(null, "", u); }
  wallet().then((w) => w.initWallet(DEP.contract, (a) => { me = a; loadMine(); boardSig = ""; if (lastState) renderBoardFlags(); })).catch(() => ($("#wallet-card").innerHTML = "<b>Your wallet</b><p class='note first'>The wallet library could not start in this browser.</p>"));
  await refresh(); renderSteps(); loadMine(); initSim(); setInterval(() => { if (!document.hidden) refresh(); }, POLL_MS); setInterval(() => { if (!document.hidden) tickCountdowns(); }, 1000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) { refresh(); loadMine(); } }); // catch up once on return
}
