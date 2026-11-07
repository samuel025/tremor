import "./style.css";
import { CONTRACT, EXPLORER, POLL_MS } from "./config";
import { accessKeyCount, listEvents, view, type Ev, type Params, type State } from "./chain";
import { checkEvent, loadCatalog, recentM6, usgsPage, type Flag, type Quake } from "./usgs";
import { $, ago, countUp, duration, esc, mag, md, pct, reveal, short, trem } from "./util";
import { renderCharts } from "./charts";
import { initMap } from "./map";
import { ripples } from "./ripples";

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
    <a class="usgs" href="${usgsPage(e.event_id)}" target="_blank" rel="noopener">USGS page ↗</a></article>`;
}

function renderBoard(evs: Ev[], p: Params, s: State) {
  const board = $("#board");
  if (!evs.length) { board.innerHTML = `<div class="empty card">No events yet. The first report will appear here.</div>`; return; }
  board.innerHTML = [...evs].sort((a, b) => b.reported_at - a.reported_at).map((e) => card(e, p, s.supply)).join("");
  evs.forEach((e) => { const k = e.event_id; if (!flags.has(k)) checkEvent(k, e.mag_x10, e.origin_s).then((f) => { flags.set(k, f); renderBoardFlags(); }); });
}
let lastEvs: Ev[] = [], lastState: State | null = null;
function renderBoardFlags() { if (params && lastState) renderBoard(lastEvs, params, lastState); }

function tickCountdowns() { document.querySelectorAll<HTMLElement>(".cd").forEach((n) => { const r = Number(n.dataset.end) - nowS(); n.textContent = duration(r); if (r <= 0) n.classList.add("done"); }); }

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
    const rows = qs.map((q, i) => `<div class="row card slim${i >= 6 ? " extra" : ""}"${i >= 6 ? " hidden" : ""}><span class="mag sm">${mag(q.mag_x10)}</span><span>${esc(q.place || "Unnamed region")}</span><span class="note">${ago(nowS() - q.origin_s)} · USGS ${esc(q.status)}</span><a href="${usgsPage(q.id)}" target="_blank" rel="noopener">USGS ↗</a></div>`).join("");
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
    skew = s.now_s - Math.floor(Date.now() / 1000); lastEvs = evs; lastState = s;
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

$("#contract-link").setAttribute("href", EXPLORER + CONTRACT); $("#contract-link").textContent = CONTRACT;
ripples($<HTMLCanvasElement>("#ripples")); reveal();
refresh().then(initSim); setInterval(refresh, POLL_MS); setInterval(tickCountdowns, 1000);
loadCatalog().then((c) => initMap($("#mapcard"), c)).catch(() => ($("#mapcard").innerHTML = "<p class='note'>The catalog could not be loaded.</p>"));
