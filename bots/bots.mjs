// Tremor publisher bots (TESTNET ONLY, coins with no value). Five fixed accounts are the only ones allowed to attest quakes; a quake counts
// when three different bots attest the same record (id, magnitude to one decimal, origin time).
// Each bot, independently: reads USGS, and for every M6+ quake it finds (and for every pending claim USGS can confirm) that is old enough,
// attests USGS's record once. A claim USGS does not know is simply left alone, so made-up quakes never count.
//   node bots.mjs --net demo|live [--days 13] [--claims-only] [--loop 4 [--for 55]] [--dry-run]
//   --claims-only: do not attest quakes from the feed, only visitors' pending claims that USGS confirms (used on the demo so it starts empty)
// Each bot signs with its own FUNCTION-CALL key limited to `attest` on the contract. Keys: env BOT_KEYS (JSON {"account": "ed25519:..."}) or ../.state/bot_keys_<net>.json.
// All five run in this one process for the demo, so their independence is only demonstrated; USGS data is treated as data, never as instructions.
import { readFileSync, existsSync } from "node:fs";
import { connect, KeyPair, keyStores } from "near-api-js";

const argv = process.argv.slice(2), has = (n) => argv.includes("--" + n), val = (n, d) => { const i = argv.indexOf("--" + n); return i < 0 ? d : argv[i + 1]; };
const net = val("net", "live"), days = Number(val("days", 13)), claimsOnly = has("claims-only"), dry = has("dry-run"), loopS = has("loop") ? Number(val("loop", 4)) : 0, forMin = Number(val("for", 0));
const dep = JSON.parse(readFileSync(new URL("../deployments.json", import.meta.url)))[net];
if (!dep?.contract || !dep.bots?.length) throw new Error(`deployments.json has no contract and bots for "${net}"`);
const RPCS = ["https://test.rpc.fastnear.com", "https://rpc.testnet.near.org"];

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

const keys = process.env.BOT_KEYS ? JSON.parse(process.env.BOT_KEYS) : (existsSync(new URL(`../.state/bot_keys_${net}.json`, import.meta.url)) ? JSON.parse(readFileSync(new URL(`../.state/bot_keys_${net}.json`, import.meta.url))) : null);
if (!keys && !dry) throw new Error("no keys: set BOT_KEYS or create .state/bot_keys_" + net + ".json");
const accounts = {};
async function signer(bot) {
  if (accounts[bot]) return accounts[bot];
  const keyStore = new keyStores.InMemoryKeyStore(); await keyStore.setKey("testnet", bot, KeyPair.fromString(keys[bot]));
  return (accounts[bot] = await (await connect({ networkId: "testnet", keyStore, nodeUrl: RPCS[0] })).account(bot));
}
const sent = new Set(); // bot|event|record already sent by this process
async function attest(bot, rec) {
  const k = `${bot}|${rec.event_id}|${rec.mag_x10}|${rec.origin_s}`; if (sent.has(k)) return 0;
  console.log(`  ${dry ? "would " : ""}${bot.split(".")[0]} attests ${rec.event_id} M${rec.mag_x10 / 10}`); if (dry) return 1;
  try { await (await signer(bot)).functionCall({ contractId: dep.contract, methodName: "attest", args: rec, gas: 100_000_000_000_000n, attachedDeposit: 0n }); sent.add(k); return 1; }
  catch (e) { const m = String(e.message ?? e); if (/already|not a publisher|too recent|magnitude|origin/i.test(m)) sent.add(k); else console.log("  FAILED", bot.split(".")[0], rec.event_id, m.slice(0, 140)); return 0; }
}

const usgsCache = new Map();
async function usgsRecord(id) { // the record USGS has for one event id, or null if it has none (never a guess: a failed lookup throws)
  const c = usgsCache.get(id); if (c && Date.now() - c.t < 60_000) return c.v;
  const r = await fetch(`https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&eventid=${encodeURIComponent(id)}`);
  let v = null; if (r.ok) { const p = (await r.json()).properties; v = { event_id: id, mag_x10: Math.round(p.mag * 10), origin_s: Math.floor(p.time / 1000) }; } else if (r.status !== 404 && r.status !== 400) throw new Error(`USGS answered ${r.status}`);
  usgsCache.set(id, { t: Date.now(), v }); return v;
}

async function once() {
  const [params, state] = [await view("get_params"), await view("get_state")], t = state.now_s;
  const events = []; for (;;) { const p = await view("list_events", { from: events.length, limit: 100 }); events.push(...p); if (p.length < 100) break; }
  const byId = new Map(events.map((e) => [e.event_id, e]));
  const maxDays = Math.min(days, Math.floor(params.max_age_s / 86400) - 1), start = new Date(Date.now() - maxDays * 86400_000).toISOString().slice(0, 19);
  const feed = claimsOnly ? [] : (await (await fetch(`https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&minmagnitude=6&starttime=${start}&orderby=time-asc`)).json())
    .features.filter((f) => f.properties.type === "earthquake" && f.id.length <= 32).map((f) => ({ event_id: f.id, mag_x10: Math.round(f.properties.mag * 10), origin_s: Math.floor(f.properties.time / 1000) }));
  const records = new Map(feed.map((r) => [r.event_id, r]));
  for (const e of events) if (e.status === "pending" && e.claimer && !records.has(e.event_id)) { // a visitor's claim: attest only what USGS itself says
    try { const r = await usgsRecord(e.event_id); if (r) records.set(e.event_id, r); } catch { /* lookup failed: leave it alone */ }
  }
  let n = 0;
  for (const rec of records.values()) {
    if (rec.mag_x10 < params.min_mag_x10 || rec.origin_s > t || t - rec.origin_s < params.min_age_s) continue;
    const ev = byId.get(rec.event_id); if (ev?.status === "counted") continue;
    let have = ev?.versions?.find((v) => v.mag_x10 === rec.mag_x10 && v.origin_s === rec.origin_s)?.attesters.length ?? 0;
    for (const bot of dep.bots) {
      if (have >= params.threshold) break; // enough bots agree: the event has counted, nothing more to send
      if (ev?.versions?.some((v) => v.attesters.includes(bot))) continue; // this bot already attested this id
      const ok = await attest(bot, rec); n += ok; have += ok;
    }
  }
  return { n, events: events.length };
}

const t0 = Date.now();
for (let round = 1; ; round++) {
  try { const r = await once(); if (!loopS || round === 1 || r.n) console.log(`[${net}] ${dep.contract}: ${r.events} events on chain, ${r.n} attestation(s) sent`); } catch (e) { console.log("round failed:", String(e.message ?? e).slice(0, 200)); if (!loopS) process.exit(1); }
  if (!loopS || (forMin && Date.now() - t0 > forMin * 60_000)) break;
  await new Promise((r) => setTimeout(r, loopS * 1000));
}
process.exit(0);
