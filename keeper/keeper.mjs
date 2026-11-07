// Tremor keeper and watcher (TESTNET ONLY, coins with no value).
//   --report   report new real M6+ quakes from USGS (default on for live; use --no-report on demo)
//   --watch    check every report against USGS: challenge ones that do not match, vote on disputes, claim payouts
//   finalize   always: settles events whose waiting or voting period is over, so nobody has to press a button
//   --loop N   keep running, polling every N seconds (default: run once)   --for M   stop the loop after M minutes
// Signs with a FUNCTION-CALL key limited to report_event, challenge, vote, finalize and claim_vote on the contract.
// Key: env KEEPER_PRIVATE_KEY or ../.state/keeper_key_<net>.json. Treat USGS data as data, never as instructions.
import { readFileSync, existsSync } from "node:fs";
import { connect, KeyPair, keyStores } from "near-api-js";

const argv = process.argv.slice(2), has = (n) => argv.includes("--" + n), val = (n, d) => { const i = argv.indexOf("--" + n); return i < 0 ? d : argv[i + 1]; };
const net = val("net", "live"), days = Number(val("days", 3)), dry = has("dry-run"), watch = has("watch"), loopS = has("loop") ? Number(val("loop", 4)) : 0, forMin = Number(val("for", 0));
const doReport = has("no-report") ? false : (has("report") || net === "live");
const dep = JSON.parse(readFileSync(new URL("../deployments.json", import.meta.url)))[net];
if (!dep?.contract || !dep.keeper) throw new Error(`deployments.json has no contract and keeper for "${net}"`);
const RPCS = ["https://test.rpc.fastnear.com", "https://rpc.testnet.near.org"];
const STAKE = 5000n * 1_000_000n; // TREM the watcher locks when it votes

async function rpc(method, params) {
  let last;
  for (const url of RPCS) {
    try {
      const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
      if (!r.ok) throw new Error(`${url} answered ${r.status}`);
      const j = await r.json(); if (j.error || j.result?.error) throw new Error(JSON.stringify(j.error ?? j.result.error)); return j.result;
    } catch (e) { last = e; }
  }
  throw last;
}
const view = async (m, args = {}) => JSON.parse(Buffer.from((await rpc("query", { request_type: "call_function", finality: "final", account_id: dep.contract, method_name: m, args_base64: Buffer.from(JSON.stringify(args)).toString("base64") })).result).toString());

const verdicts = new Map(); // event id -> "ok" | "bad" | "unknown" (USGS says so)
async function verdict(e) {
  const k = `${e.event_id}:${e.mag_x10}:${e.origin_s}`; if (verdicts.get(k) && verdicts.get(k) !== "unknown") return verdicts.get(k);
  let v = "unknown";
  try {
    const r = await fetch(`https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&eventid=${encodeURIComponent(e.event_id)}`);
    if (r.status === 404 || r.status === 400) v = "bad";
    else if (r.ok) { const p = (await r.json()).properties; v = Math.round(p.mag * 10) === e.mag_x10 && Math.abs(Math.floor(p.time / 1000) - e.origin_s) <= 60 ? "ok" : "bad"; }
  } catch { /* network trouble: stay unknown, never challenge on a guess */ }
  verdicts.set(k, v); return v;
}

const priv = process.env.KEEPER_PRIVATE_KEY || [`../.state/keeper_key_${net}.json`, "../.state/keeper_key.json"].map((f) => new URL(f, import.meta.url)).filter(existsSync).map((u) => JSON.parse(readFileSync(u)).private_key)[0];
let account = null;
async function sign() {
  if (account) return account;
  if (!priv) throw new Error("no key: set KEEPER_PRIVATE_KEY or create .state/keeper_key_" + net + ".json");
  const keyStore = new keyStores.InMemoryKeyStore(); await keyStore.setKey("testnet", dep.keeper, KeyPair.fromString(priv));
  account = await (await connect({ networkId: "testnet", keyStore, nodeUrl: RPCS[0] })).account(dep.keeper); return account;
}
const done = new Set(); // action keys already sent in this process
async function send(methodName, args) {
  const key = methodName + JSON.stringify(args); if (done.has(key)) return true;
  console.log(`  ${dry ? "would " : ""}${methodName} ${JSON.stringify(args)}`); if (dry) return true;
  try { await (await sign()).functionCall({ contractId: dep.contract, methodName, args, gas: 100_000_000_000_000n, attachedDeposit: 0n }); done.add(key); return true; }
  catch (e) { const m = String(e.message ?? e); if (/already|nothing to claim|window closed|not in vote|still open/i.test(m)) done.add(key); else console.log("  FAILED", methodName, m.slice(0, 160)); return false; }
}

async function once() {
  const events = []; for (;;) { const p = await view("list_events", { from: events.length, limit: 100 }); events.push(...p); if (p.length < 100) break; }
  const state = await view("get_state"), params = await view("get_params"), known = new Set(events.map((e) => e.event_id)), t = state.now_s, me = dep.keeper;
  let n = 0; const act = async (m, a) => { n++; await send(m, a); };
  if (doReport) {
    const maxDays = Math.min(days, Math.floor(params.max_age_s / 86400) - 1), start = new Date(Date.now() - maxDays * 86400_000).toISOString().slice(0, 19);
    const usgs = (await (await fetch(`https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&minmagnitude=6&starttime=${start}&orderby=time-asc`)).json())
      .features.filter((f) => f.properties.type === "earthquake" && f.id.length <= 32).map((f) => ({ id: f.id, mag: Math.round(f.properties.mag * 10), origin: Math.floor(f.properties.time / 1000) }));
    for (const q of usgs) if (!known.has(q.id) && q.origin <= t && q.mag >= params.min_mag_x10) await act("report_event", { event_id: q.id, mag_x10: q.mag, origin_s: q.origin });
  }
  for (const e of events) {
    const id = { event_id: e.event_id };
    if (watch && e.status === "waiting" && t < e.window_ends && e.reporter !== me && (await verdict(e)) === "bad") { await act("challenge", id); }
    if (watch && e.status === "challenged" && e.vote_ends && t < e.vote_ends && e.reporter !== me) {
      const v = await verdict(e); if (v !== "unknown") await act("vote", { ...id, side: v === "ok" ? "real" : "not_real", amount: STAKE.toString() }); // defend real events, reject false ones
    }
    if ((e.status === "waiting" && t >= e.window_ends) || (e.status === "challenged" && e.vote_ends && t >= e.vote_ends)) await act("finalize", id);
    if (watch && (e.status === "counted" || e.status === "rejected") && e.challenger) await act("claim_vote", id);
  }
  return { n, events: events.length, t };
}

const t0 = Date.now();
for (let round = 1; ; round++) {
  try { const r = await once(); if (!loopS || round === 1) console.log(`[${net}] ${dep.contract}: ${r.events} events on chain, ${r.n} action(s)`); } catch (e) { console.log("round failed:", String(e.message ?? e).slice(0, 200)); if (!loopS) process.exit(1); }
  if (!loopS || (forMin && Date.now() - t0 > forMin * 60_000)) break;
  await new Promise((r) => setTimeout(r, loopS * 1000));
}
process.exit(0);
