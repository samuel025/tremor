import "./style.css";
import { EXPLORER, POLL_MS } from "./config";
import { DEP, NET, loadDeployments, switchNet } from "./deployment";
// the wallet library is large, so it loads on demand
const wallet = () => import("./wallet");
const send = async (m: string, a: object, d = "0") => (await wallet()).send(m, a, d);
import { accessKeyCount, listEvents, registered, view, type Ev, type Params, type State } from "./chain";
import { checkEvent, loadCatalog, recentM6, usgsPage, type Flag, type Quake } from "./usgs";
import { $, ago, countUp, duration, esc, mag, md, pct, reveal, short, trem } from "./util";
import { renderCharts } from "./charts";
import { initMap } from "./map";
import { Seismo } from "./seismo";
import { ampFor, shake } from "./shake";

let params: Params | null = null, skew = 0;
const flags = new Map<string, Flag>();
const nowS = () => Math.floor(Date.now() / 1000) + skew;
const STATUS_TEXT: Record<Ev["status"], string> = { waiting: "Waiting", challenged: "Challenged", counted: "Counted", rejected: "Rejected" };

function banner(msg: string | null) { const b = $("#banner"); b.hidden = !msg; if (msg) b.textContent = msg; }

function renderChips(s: State) {
  countUp($("#c-supply"), Number(BigInt(s.supply) / 10_000n) / 100, (n) => n.toLocaleString("en-US", { maximumFractionDigits: 0 }));
  countUp($("#c-7d"), Number(BigInt(s.minted_7d) / 10_000n) / 100, (n) => n.toLocaleString("en-US", { maximumFractionDigits: 0 }));
  countUp($("#c-open"), s.open_events, (n) => String(Math.round(n)));
}

function meter(prefix: "wk" | "mo", minted: string, left: string, label: string) {
  const m = BigInt(minted), l = BigInt(left), total = m + l, used = total ? Number((m * 10000n) / total) / 10000 : 0;
  $(`#${prefix}-t`).textContent = `${trem(m, 0)} of ${trem(total, 0)} TREM used`;
  requestAnimationFrame(() => ($(`#${prefix}-bar`).style.width = Math.max(1.5, used * 100) + "%"));
  $(`#${prefix}-n`).textContent = `${pct(used)} of the ${label} allowance is used. ${trem(l, 0)} TREM can still be created.`;
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

function dispute(e: Ev, p: Params, supply: string): string {
  const real = BigInt(e.real_locked), no = BigInt(e.not_real_locked), turn = real + no, tot = turn || 1n;
  const need = (BigInt(supply) * BigInt(p.quorum_ppm)) / 1_000_000n;
  const left = e.vote_ends && e.status === "challenged" ? `<span>Time left <b class="cd" data-end="${e.vote_ends}">${duration(e.vote_ends - nowS())}</b></span>` : "";
  return `<div class="dispute"><div class="dh"><b>Dispute</b>${left}</div>
    <div class="split" role="img" aria-label="Coins locked: ${trem(real, 0)} real, ${trem(no, 0)} not real"><i class="yes" style="width:${Number((real * 1000n) / tot) / 10}%"></i><i class="no" style="width:${Number((no * 1000n) / tot) / 10}%"></i></div>
    <div class="dl"><span><i class="sw yes"></i>Real ${trem(real, 0)}</span><span><i class="sw no"></i>Not real ${trem(no, 0)}</span></div>
    <p class="note">Turnout ${trem(turn, 0)} of ${trem(need, 0)} TREM needed. Each side posted a ${trem(p.bond, 0)} TREM bond${e.status === "rejected" || e.status === "counted" ? `; the wrong side lost its bond${BigInt(e.pot) > 0n ? ` (${trem(e.pot, 0)} TREM still unclaimed)` : ""}` : ""}.</p></div>`;
}

let me: string | null = null;
function actions(e: Ev, p: Params): string {
  if (!me) return "";
  const t = nowS(), id = esc(e.event_id), b: string[] = [];
  if (e.status === "waiting" && t < e.window_ends && e.reporter !== me) b.push(`<button class="out" data-act="challenge" data-id="${id}">Challenge (${trem(p.bond, 0)} TREM bond)</button>`);
  if (e.status === "challenged" && e.vote_ends && t < e.vote_ends) b.push(`<span class="vote"><input type="number" min="1" value="2500" aria-label="Coins to lock, in TREM"><button class="out" data-act="vote" data-side="real" data-id="${id}">Vote real</button><button class="out" data-act="vote" data-side="not_real" data-id="${id}">Vote not real</button></span>`);
  if ((e.status === "waiting" && t >= e.window_ends) || (e.status === "challenged" && e.vote_ends && t >= e.vote_ends)) b.push(`<button class="blue" data-act="finalize" data-id="${id}">Finalize</button>`);
  if ((e.status === "counted" || e.status === "rejected") && e.challenger) b.push(`<button class="out" data-act="claim" data-id="${id}">Claim my vote payout</button>`);
  return b.length ? `<div class="acts">${b.join("")}</div>` : "";
}

function card(e: Ev, p: Params, supply: string): string {
  const disputed = e.challenger !== null;
  let line = "";
  if (e.status === "waiting") line = e.window_ends <= nowS()
    ? `Waiting window is over. Anyone can finalize it now.`
    : `Waiting window ends in <b class="cd" data-end="${e.window_ends}">${duration(e.window_ends - nowS())}</b>`;
  else if (e.status === "challenged") line = `Challenged by ${esc(short(e.challenger ?? ""))}. Holders are voting.`;
  else if (e.status === "counted") line = `<b>+${trem(e.minted)} TREM</b> created for the relief list${e.clipped ? " <span class='clip'>cut by a cap</span>" : ""}`;
  else line = "Rejected: nothing was created";
  return `<article class="ev ${e.status}"><header><span class="mag">${mag(e.mag_x10)}</span><span class="pill st-${e.status}">${STATUS_TEXT[e.status]}</span></header>
    <p class="meta"><code>${esc(e.event_id)}</code> · reported by ${esc(short(e.reporter))} ${ago(nowS() - e.reported_at)}</p>${flagHtml(e.event_id)}
    <p class="line">${line}</p>${disputed ? dispute(e, p, supply) : ""}
    ${actions(e, p)}<a class="usgs" href="${usgsPage(e.event_id)}" target="_blank" rel="noopener">USGS page ↗</a></article>`;
}

let boardSig = "";
function renderBoard(evs: Ev[], p: Params, s: State) {
  const board = $("#board");
  const sig = (me ?? "") + JSON.stringify(evs) + [...flags.entries()].map(([k, f]) => k + f.kind).join() + Math.floor(nowS() / 60);
  if (sig === boardSig) return; // unchanged: keep the DOM so card animations do not restart every poll
  boardSig = sig;
  if (!evs.length) { board.innerHTML = `<div class="empty card">No events yet. The first report will appear here.</div>`; return; }
  board.innerHTML = [...evs].sort((a, b) => b.reported_at - a.reported_at).map((e) => card(e, p, s.supply)).join("");
  evs.forEach((e) => { const k = e.event_id; if (!flags.has(k)) checkEvent(k, e.mag_x10, e.origin_s).then((f) => { flags.set(k, f); renderBoardFlags(); }); });
}
let lastEvs: Ev[] = [], lastState: State | null = null;
function renderBoardFlags() { if (params && lastState) renderBoard(lastEvs, params, lastState); }

function tickCountdowns() { document.querySelectorAll<HTMLElement>(".cd").forEach((n) => { const r = Number(n.dataset.end) - nowS(); n.textContent = duration(r); if (r <= 0 && !n.classList.contains("done")) { n.classList.add("done"); boardSig = ""; renderBoardFlags(); } }); }

async function renderRelief(p: Params) {
  const bals = await Promise.all(p.relief_accounts.map((a) => view<string>("ft_balance_of", { account_id: a })));
  const max = bals.reduce((m, b) => (BigInt(b) > m ? BigInt(b) : m), 1n);
  $("#relief-list").innerHTML = p.relief_accounts.map((a, i) => `<div class="card rl"><b>${esc(short(a))}</b><span class="amt">${trem(bals[i])} <small>TREM received</small></span><div class="bar thin"><i style="width:${Number((BigInt(bals[i]) * 100n) / max)}%"></i></div></div>`).join("");
}

async function renderUnreported(evs: Ev[], p: Params) {
  const host = $("#unrep");
  try {
    const known = new Set(evs.map((e) => e.event_id));
    const qs = (await recentM6(Math.floor(p.max_age_s / 86400))).filter((q: Quake) => !known.has(q.id));
    const rows = qs.map((q, i) => `<div class="row card slim${i >= 6 ? " extra" : ""}"${i >= 6 ? " hidden" : ""}><span class="mag sm">${mag(q.mag_x10)}</span><span>${esc(q.place || "Unnamed region")}</span><span class="note">${ago(nowS() - q.origin_s)} · USGS ${esc(q.status)}</span><a href="${usgsPage(q.id)}" target="_blank" rel="noopener">USGS ↗</a>${me ? `<button class="out" data-report="${esc(q.id)}" data-mag="${q.mag_x10}" data-origin="${q.origin_s}">Report</button>` : ""}</div>`).join("");
    host.innerHTML = qs.length ? rows + (qs.length > 6 ? `<button class="btn" id="more">Show all ${qs.length}</button>` : "") : `<div class="card slim">Every USGS event of M6+ in the last 60 days has been reported.</div>`;
    const more = host.querySelector<HTMLButtonElement>("#more");
    if (more) more.onclick = () => { host.querySelectorAll<HTMLElement>(".extra").forEach((n) => (n.hidden = false)); more.remove(); };
  } catch { host.innerHTML = `<div class="card slim">Could not reach USGS right now.</div>`; }
}

function renderParams(p: Params) {
  const rows: [string, string][] = [
    ["Initial supply", `${trem(p.s0, 0)} TREM`], ["Minimum magnitude", `M${(p.min_mag_x10 / 10).toFixed(1)}`],
    ["Mint at M6.0 (×2 at M7, ×3 at M8)", `${(p.base_ppm / 1e4).toFixed(2)}% of supply`], ["Most one event can mint", `${(p.max_event_ppm / 1e4).toFixed(1)}% of supply`],
    ["Cooldown (aftershocks mint less)", duration(p.cooldown_s)], ["Weekly cap", `${(p.week_cap_ppm / 1e4).toFixed(1)}% of supply`], ["Monthly cap", `${(p.month_cap_ppm / 1e4).toFixed(1)}% of supply`],
    ["Report / challenge bond", `${trem(p.bond, 0)} TREM each`], ["Waiting window (demo)", duration(p.window_s)], ["Voting period (demo)", duration(p.vote_s)],
    ["Wrong-vote penalty", `${p.slash_pct}% of locked coins`], ["Minimum turnout", `${(p.quorum_ppm / 1e4).toFixed(2)}% of supply`], ["Oldest reportable event", duration(p.max_age_s)],
  ];
  $("#params-t").innerHTML = rows.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join("");
}

async function refresh() {
  try {
    const [s, evs] = await Promise.all([view<State>("get_state"), listEvents()]);
    if (!params) { params = await view<Params>("get_params"); renderParams(params); renderRelief(params); }
    skew = s.now_s - Math.floor(Date.now() / 1000); lastEvs = evs; lastState = s; state0 = s;
    banner(null); renderChips(s); renderMeters(s, params); renderBoard(evs, params, s); renderUnreported(evs, params); renderRelief(params);
    accessKeyCount().then((n) => { $("#keys-line").innerHTML = `<b>${n}</b> access key${n === 1 ? "" : "s"}`; }).catch(() => ($("#keys-line").textContent = "unavailable"));
  } catch (e) { banner("Could not read the testnet contract right now. This page is read-only and will retry. " + (e instanceof Error ? e.message.slice(0, 120) : "")); }
}

async function initSim() {
  try {
    const ch = await (await fetch("sim/chosen.json")).json(); const c = ch.chosen;
    $("#sim-sub").textContent = `Before any contract code, the rules ran against 60 real days of USGS data and five scenarios. ${ch.n_pass} of ${ch.n_grid} parameter combinations passed every threshold we wrote down first; this is the one we chose.`;
    $("#sim-cards").innerHTML = [
      ["Chosen rules", `${(c.base_ppm / 1e4).toFixed(2)}% base · ${(c.week_ppm / 1e4).toFixed(1)}% weekly · ${(c.month_ppm / 1e4).toFixed(0)}% monthly cap`, `${c.slash_pct}% penalty · ${(c.quorum_ppm / 1e4).toFixed(1)}% minimum turnout`],
      ["A passive holder, 60 real days", `${pct(c.s1_dilution, 2)} diluted`, `Caps bound in ${pct(c.s1_clipped_weeks, 0)} of weeks, right at our 25% limit`],
      ["Fakes when watchers challenge", `${pct(c.s3_rej_half, 0)} rejected`, `With half the watchers challenging; the liar loses bonds`],
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
  try { const [b, bb] = await Promise.all([view<string>("ft_balance_of", { account_id: id }), view<string>("bond_balance_of", { account_id: id })]); out.innerHTML = `<b>${esc(id)}</b>: ${trem(b)} TREM in the wallet, ${trem(bb)} TREM in the bond balance.`; }
  catch { out.textContent = "That account has no Tremor balance, or the lookup failed."; }
});

reveal();
start();
initMotion();
loadCatalog().then((c) => { initHero(c); return initMap($("#mapcard"), c); }).catch(() => ($("#mapcard").innerHTML = "<p class='note'>The catalog could not be loaded.</p>"));

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
  const caption = (q: Quake) => { cap.innerHTML = `<b>${esc2(mag(q.mag_x10))}</b> · ${esc2(q.place || "unnamed region")} · replayed from the committed USGS catalog`; };
  const onS = (amp: number) => { const a = 2 + amp * 9; parts.forEach((el, i) => shake(el, a * (i ? 0.8 : 1))); shake(main, a * 0.35, 1400); };
  const seismo = new Seismo($<HTMLCanvasElement>("#seismo"), { speed: 110, color: "#1d1d1f", grid: "#e6e6e8", labels: true, onS });
  let i = Math.floor(Math.random() * big.length), timer: number | undefined;
  const fire = (q: Quake) => { caption(q); seismo.burst(q.mag_x10); };
  const next = () => { fire(big[i++ % big.length]); };
  const loop = () => { timer = window.setTimeout(() => { next(); loop(); }, 9000); };
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
const win = () => (params ? `${duration(params.window_s)} to challenge, ${duration(params.vote_s)} to vote` : "");

function renderSteps() {
  const demo = NET === "demo";
  $("#steps").innerHTML = [
    "Connect a free testnet wallet. It only gets a key that can call Tremor, nothing else.",
    `Take your ${params ? trem(params.tap_amount, 0) : "5,000"} starter TREM (once per account; it mints nothing, it comes from a pool the launcher filled).`,
    `Deposit some into your bond balance: a report or challenge locks ${params ? trem(params.bond, 0) : "1,000"} TREM.`,
    "Report a real quake from the list above, or report a made-up one to see how it gets caught.",
    `Wait out the window (${win()}). Someone can challenge it; holders then lock coins on “real” or “not real”.`,
    "Finalize it, then claim your vote payout. A counted event mints new coins to the five relief accounts.",
  ].map((t) => `<li>${esc(t)}</li>`).join("");
  $("#netnote").innerHTML = demo
    ? `Viewing the <b>Demo</b> contract: ${win()}, so a whole round takes about five minutes. <a href="#" data-net="live">Switch to Live</a> for the real timing.`
    : `Viewing the <b>Live</b> contract: real timing (${win()}), kept busy by a bot that reports real quakes. <a href="#" data-net="demo">Switch to Demo</a> to try a whole round in about five minutes.`;
}

async function renderWallet() {
  const card = $("#wallet-card");
  if (!me) {
    card.innerHTML = `<h3>Your wallet</h3><p class="note">Not connected. You need a testnet account: it is free: create one in the Meteor wallet (switch it to testnet). The coins have no value.</p><button class="btn" id="w-connect">Connect wallet</button>`;
    return;
  }
  card.innerHTML = `<h3>${esc(me)}</h3><p class="note">Reading your balances…</p>`;
  try {
    const [bal, bond, tapped, reg] = await Promise.all([view<string>("ft_balance_of", { account_id: me }), view<string>("bond_balance_of", { account_id: me }), view<boolean>("has_tapped", { account_id: me }), registered(me)]);
    const tapOn = params && BigInt(params.tap_amount) > 0n;
    card.innerHTML = `<h3>${esc(me)}</h3>
      <div class="two"><div><small>In your wallet</small><b>${trem(bal)}</b><span>TREM</span></div><div><small>Bond balance</small><b>${trem(bond)}</b><span>TREM</span></div></div>
      <div class="acts">${tapOn ? `<button class="blue" id="w-tap" ${tapped ? "disabled" : ""}>${tapped ? "Starter coins taken" : `Get ${trem(params!.tap_amount, 0)} starter TREM`}</button>` : ""}
      <span class="vote"><input id="w-amt" type="number" min="1" value="${params ? Number(BigInt(params.bond) / 1_000_000n) * 2 : 2000}" aria-label="TREM"><button class="out" id="w-dep">Deposit to bond balance</button><button class="out" id="w-wd">Withdraw</button></span></div>
      <p class="note">${reg ? "" : "Your first action asks for a tiny storage deposit (0.00125 NEAR) so the contract can hold your coins. "}A pool of ${state0 ? trem(state0.tap_pool, 0) : "–"} TREM is left in the tap.</p>
      <details class="mk"><summary>Report a made-up quake (to watch it get caught)</summary><div class="vote"><input id="w-fid" value="fake-${Math.floor(100 + Math.random() * 900)}" aria-label="Event id" spellcheck="false"><input id="w-fmag" type="number" step="0.1" min="6" max="10" value="7.4" aria-label="Magnitude"><button class="out" id="w-fake">Report it</button></div></details>
      <button class="out" id="w-out">Disconnect</button>`;
  } catch { card.innerHTML = `<h3>${esc(me)}</h3><p class="note">Could not read your balances right now.</p><button class="out" id="w-out">Disconnect</button>`; }
}
let state0: State | null = null;

async function act(label: string, fn: () => Promise<unknown>) {
  try { toast(`${label}: approve it in your wallet…`, 20000); await fn(); toast(`${label}: sent. Refreshing…`); }
  catch (e) { toast(`${label} did not go through: ${(e instanceof Error ? e.message : String(e)).slice(0, 160)}`, 9000); return; }
  setTimeout(() => { refresh(); renderWallet(); }, 4000); setTimeout(() => { refresh(); renderWallet(); }, 10000);
}
const base = (trems: string) => (BigInt(Math.round(Number(trems) * 1000)) * 1000n).toString();

document.addEventListener("click", (ev) => {
  const t = ev.target as HTMLElement; const el = t.closest<HTMLElement>("button,a[data-net]"); if (!el) return;
  if (el.dataset.net && el.tagName === "A") { ev.preventDefault(); switchNet(el.dataset.net as "live" | "demo"); return; }
  if (el.dataset.net) { switchNet(el.dataset.net as "live" | "demo"); return; }
  if (el.id === "w-connect") return void wallet().then((w) => w.connectWallet());
  if (el.id === "w-out") return void wallet().then((w) => w.disconnectWallet()).then(() => { me = null; renderWallet(); boardSig = ""; renderBoardFlags(); });
  if (el.id === "w-tap") return void registered(me!).then((reg) => act("Starter coins", () => send("tap", {}, reg ? "0" : "1250000000000000000000")));
  if (el.id === "w-dep") return void act("Deposit", () => send("deposit_bond", { amount: base(($("#w-amt") as HTMLInputElement).value) }, "1"));
  if (el.id === "w-wd") return void act("Withdraw", () => send("withdraw_bond", { amount: base(($("#w-amt") as HTMLInputElement).value) }, "1"));
  if (el.id === "w-fake") { const id = ($("#w-fid") as HTMLInputElement).value.trim(), m = Math.round(Number(($("#w-fmag") as HTMLInputElement).value) * 10);
    return void act("Report", () => send("report_event", { event_id: id, mag_x10: m, origin_s: nowS() - 120 })); }
  if (el.dataset.report) return void act("Report", () => send("report_event", { event_id: el.dataset.report, mag_x10: Number(el.dataset.mag), origin_s: Number(el.dataset.origin) }));
  const id = el.dataset.id; if (!el.dataset.act || !id) return;
  if (el.dataset.act === "challenge") return void act("Challenge", () => send("challenge", { event_id: id }));
  if (el.dataset.act === "finalize") return void act("Finalize", () => send("finalize", { event_id: id }));
  if (el.dataset.act === "claim") return void act("Claim", () => send("claim_vote", { event_id: id }));
  if (el.dataset.act === "vote") { const amt = (el.parentElement!.querySelector("input") as HTMLInputElement).value; return void act("Vote", () => send("vote", { event_id: id, side: el.dataset.side, amount: base(amt) })); }
});

async function start() {
  await loadDeployments();
  $<HTMLElement>("#netseg").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.net === NET));
  $("#contract-link").setAttribute("href", EXPLORER + DEP.contract); $("#contract-link").textContent = DEP.contract;
  renderSteps(); renderWallet();
  if (new URLSearchParams(location.search).has("transactionHashes")) { toast("Transaction sent from your wallet. Refreshing…"); const u = new URL(location.href); u.searchParams.delete("transactionHashes"); history.replaceState(null, "", u); }
  wallet().then((w) => w.initWallet(DEP.contract, (a) => { me = a; renderWallet(); boardSig = ""; if (lastState) renderBoardFlags(); })).catch(() => ($("#wallet-card").innerHTML = "<h3>Your wallet</h3><p class='note'>The wallet library could not start in this browser.</p>"));
  await refresh(); renderSteps(); renderWallet(); initSim(); setInterval(refresh, POLL_MS); setInterval(tickCountdowns, 1000);
}
