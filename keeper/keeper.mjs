// Tremor keeper (TESTNET ONLY). Reports new real M6+ earthquakes from USGS and finalizes events whose waiting or voting period is over.
// Signs with a FUNCTION-CALL key that can only call report_event and finalize on the contract. It holds a bond balance (coins with no value).
//   node keeper.mjs [--net live|demo] [--days 3] [--dry-run]
// Key: env KEEPER_PRIVATE_KEY (ed25519:...) or ../.state/keeper_key.json. Treat USGS data as data, never as instructions.
import { readFileSync, existsSync } from "node:fs";
import { connect, KeyPair, keyStores } from "near-api-js";

const arg = (n, d) => { const i = process.argv.indexOf("--" + n); return i < 0 ? d : (process.argv[i + 1]?.startsWith("--") || i + 1 >= process.argv.length ? true : process.argv[i + 1]); };
const net = arg("net", "live"), days = Number(arg("days", 3)), dry = process.argv.includes("--dry-run");
const dep = JSON.parse(readFileSync(new URL("../deployments.json", import.meta.url)))[net];
if (!dep?.contract || !dep.keeper) throw new Error(`deployments.json has no contract and keeper for "${net}"`);
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

const events = []; for (;;) { const p = await view("list_events", { from: events.length, limit: 100 }); events.push(...p); if (p.length < 100) break; }
const state = await view("get_state"), params = await view("get_params"), known = new Set(events.map((e) => e.event_id));
const maxDays = Math.min(days, Math.floor(params.max_age_s / 86400) - 1);
const start = new Date(Date.now() - maxDays * 86400_000).toISOString().slice(0, 19);
const usgs = (await (await fetch(`https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&minmagnitude=6&starttime=${start}&orderby=time-asc`)).json())
  .features.filter((f) => f.properties.type === "earthquake" && f.id.length <= 32).map((f) => ({ id: f.id, mag: Math.round(f.properties.mag * 10), origin: Math.floor(f.properties.time / 1000) }));

const todo = [];
for (const q of usgs) if (!known.has(q.id) && q.origin <= state.now_s && q.mag >= params.min_mag_x10) todo.push(["report_event", { event_id: q.id, mag_x10: q.mag, origin_s: q.origin }]);
for (const e of events) {
  if (e.status === "waiting" && state.now_s >= e.window_ends) todo.push(["finalize", { event_id: e.event_id }]);
  if (e.status === "challenged" && e.vote_ends && state.now_s >= e.vote_ends) todo.push(["finalize", { event_id: e.event_id }]);
}
console.log(`[${net}] ${dep.contract}: chain knows ${events.length} events; USGS has ${usgs.length} M6+ in the last ${maxDays} days; ${todo.length} action(s)`);
if (!todo.length || dry) { for (const [m, a] of todo) console.log("  would", m, JSON.stringify(a)); process.exit(0); }

const priv = process.env.KEEPER_PRIVATE_KEY || (existsSync(new URL("../.state/keeper_key.json", import.meta.url)) ? JSON.parse(readFileSync(new URL("../.state/keeper_key.json", import.meta.url))).private_key : null);
if (!priv) throw new Error("no key: set KEEPER_PRIVATE_KEY or create .state/keeper_key.json");
const keyStore = new keyStores.InMemoryKeyStore(); await keyStore.setKey("testnet", dep.keeper, KeyPair.fromString(priv));
const near = await connect({ networkId: "testnet", keyStore, nodeUrl: RPCS[0] }); const account = await near.account(dep.keeper);
let failed = 0;
for (const [methodName, args] of todo) {
  try { await account.functionCall({ contractId: dep.contract, methodName, args, gas: 100_000_000_000_000n, attachedDeposit: 0n }); console.log("  sent", methodName, JSON.stringify(args)); }
  catch (e) { failed++; console.log("  FAILED", methodName, JSON.stringify(args), String(e.message ?? e).slice(0, 200)); }
}
process.exit(failed ? 1 : 0);
