// Proves the TypeScript rules engine (used by the in-browser simulator) is identical to the Python reference:
// replays vectors/conformance.json (200 seeded scenarios, the same file the Rust contract is checked against) and the three golden vectors.
// Run: node tests/conformance.ts   (Node 23.6+ runs TypeScript directly)
import { readFileSync } from "node:fs";
import { Reject, Tremor, type Params } from "../src/sim/engine.ts";

const root = new URL("../../", import.meta.url).pathname;
const stable = (x: unknown): string => JSON.stringify(x, (_, v) => (v && typeof v === "object" && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort()) : v));
const P = (p: any, pubs: string[], rel: string[]): Params => ({
  s0: BigInt(p.s0), min_mag_x10: p.min_mag_x10, min_alert: p.min_alert, base_ppm: BigInt(p.base_ppm), max_event_ppm: BigInt(p.max_event_ppm), cooldown_s: p.cooldown_s, week_cap_ppm: BigInt(p.week_cap_ppm),
  month_cap_ppm: BigInt(p.month_cap_ppm), min_age_s: p.min_age_s, max_age_s: p.max_age_s, max_open: p.max_open, max_claims: p.max_claims, claim_wait_s: p.claim_wait_s,
  threshold: p.threshold, match_ppm: BigInt(p.match_ppm), match_day_ppm: BigInt(p.match_day_ppm), match_month_ppm: BigInt(p.match_month_ppm), match_account_max: BigInt(p.match_account_max), tap_amount: BigInt(p.tap_amount), publishers: pubs, relief: rel,
});

let steps = 0, mismatches = 0;
const all = JSON.parse(readFileSync(root + "vectors/conformance.json", "utf8")) as any[];
for (const sc of all) {
  const t = new Tremor(P(sc.params, sc.publishers, sc.relief), sc.launcher);
  sc.steps.forEach((st: any, i: number) => {
    const a = st.args, now = st.now; let ok = true;
    try {
      if (st.op === "transfer") t.ftTransfer(a[0], a[1], BigInt(a[2]));
      else if (st.op === "tap") t.tap(a[0], "pool");
      else if (st.op === "fund") t.fundMatch(a[0], BigInt(a[1]), now);
      else if (st.op === "give") t.give(a[0], BigInt(a[1]), now);
      else if (st.op === "attest") t.attest(a[0], a[1], a[2], a[3], now, a[4]);
      else if (st.op === "claim") t.submitClaim(a[0], a[1], a[2], a[3], now, a[4]);
      else throw new Error("unknown op " + st.op);
    } catch (e) { if (e instanceof Reject) ok = false; else throw e; }
    t.checkInvariants(); steps++;
    if (ok !== st.ok || stable(t.snapshot()) !== stable(st.snap)) { mismatches++; if (mismatches <= 3) console.error(`MISMATCH seed ${sc.seed} step ${i} op ${st.op} ok(ts)=${ok} ok(py)=${st.ok}`); }
  });
}
// golden vector 1, typed from RULES.md (independent of the Python reference): each event confirmed by 3 bots at its origin time
const U = 1_000_000n, T0 = 20000 * 86400, H = 3600;
const gp: Params = { s0: 1_000_000n * U, min_mag_x10: 60, min_alert: 2, base_ppm: 5000n, max_event_ppm: 15000n, cooldown_s: 86400, week_cap_ppm: 15000n, month_cap_ppm: 50000n, min_age_s: 0, max_age_s: 5_184_000,
  max_open: 64, max_claims: 32, claim_wait_s: 43200, threshold: 3, match_ppm: 0n, match_day_ppm: 0n, match_month_ppm: 0n, match_account_max: 0n, tap_amount: 0n, publishers: ["bot1", "bot2", "bot3", "bot4", "bot5"], relief: ["r1", "r2", "r3", "r4", "r5"] };
const g = new Tremor(gp, "ada"); const run = (id: string, mag: number, o: number) => { let r: any = null; for (const b of ["bot1", "bot2", "bot3"]) r = g.attest(b, id, mag, o, o); return r as [bigint, bigint, boolean]; };
let gvOk = true; const chk = (c: boolean) => { if (!c) gvOk = false; };
let r = run("E1", 60, T0); chk(r[0] === 5_000n * U && g.supply === 1_005_000n * U);
r = run("E2", 70, T0 + 48 * H); chk(r[0] === 10_050n * U && g.supply === 1_015_050n * U);
r = run("E3", 60, T0 + 60 * H); chk(r[1] === 2_537_625_000n && r[0] === 175_750_000n && r[2] && g.supply === 1_015_225_750_000n && g.bal("r2") === 3_045_150_000n);
const D = 86400, relief5 = ["relief1", "relief2", "relief3", "relief4", "relief5"];
const refused = (f: () => unknown) => { try { f(); return false; } catch (e) { return e instanceof Reject; } };
// golden vector 5, typed from RULES.md: a gift is topped up by 10% from the reserve; nothing is created
{
  const v = new Tremor({ ...gp, relief: relief5, match_ppm: 100_000n, match_day_ppm: 5000n, match_month_ppm: 20000n, match_account_max: 10_000n * U }, "ada");
  v.fundMatch("ada", 50_000n * U, T0);
  chk(v.give("ada", 1_000n * U, T0 + 1) === 100n * U && v.reserve === 49_900n * U && v.bal("relief1") === 220n * U && v.supply === 1_000_000n * U);
  chk(v.give("ada", 12_000_003n, T0 + 2) === 1_200_000n && v.reserve === 49_898_800_000n && v.bal("relief1") === 222_640_003n && v.bal("relief2") === 222_640_000n);
  chk(refused(() => v.fundMatch("relief1", 1n, T0 + 3)) && refused(() => v.give("stranger", 1n, T0 + 4)) && refused(() => v.fundMatch("ada", 0n, T0 + 5)));
  let q5: any = null; for (const b of ["bot1", "bot2", "bot3"]) q5 = v.attest(b, "E1", 60, T0 + 10, T0 + 10);
  chk(q5[0] === 5_000n * U && v.supply === 1_005_000n * U && v.reserve === 49_898_800_000n && v.bal("relief1") === 1_222_640_003n && v.bal("relief2") === 1_222_640_000n);
  v.checkInvariants();
}
// golden vector 6, typed from RULES.md: only quakes with expected human impact count; three bots must agree on the alert level too
{
  const w = new Tremor({ ...gp, base_ppm: 5000n }, "ada"), e6 = (f: () => unknown) => { try { f(); return false; } catch (e) { return e instanceof Reject; } };
  chk(e6(() => w.attest("bot1", "g1", 60, T0, T0 + 5, 1)) && e6(() => w.submitClaim("judge", "g2", 60, T0, T0 + 5, 1)) && e6(() => w.attest("bot1", "g3", 60, T0, T0 + 5, 0)) && e6(() => w.attest("bot1", "g3", 60, T0, T0 + 5, 5)) && w.ev.size === 0);
  for (const [b, al, dt] of [["bot1", 3, 5], ["bot2", 3, 6], ["bot3", 2, 7]] as [string, number, number][]) chk(w.attest(b, "a2", 60, T0, T0 + dt, al) === null);
  chk(w.supply === 1_000_000n * U);
  const r6 = w.attest("bot4", "a2", 60, T0, T0 + 8, 3); chk(!!r6 && r6[0] === 5_000n * U && w.supply === 1_005_000n * U && e6(() => w.attest("bot5", "a2", 60, T0, T0 + 9, 3)));
}
// golden vector 7, typed from RULES.md: a daily budget, a 30-day budget and a window that slides
{
  const x = new Tremor({ ...gp, relief: relief5, match_ppm: 1_000_000n, match_day_ppm: 5000n, match_month_ppm: 20000n, match_account_max: 1_000_000n * U }, "ada");
  x.fundMatch("ada", 100_000n * U, T0);
  const steps: [number, bigint, bigint][] = [[1, 4000n, 4000n], [2, 3000n, 1000n], [3, 1n, 0n], [D + 1, 5000n, 5000n], [2 * D + 1, 5000n, 5000n], [3 * D + 1, 5000n, 5000n], [4 * D + 1, 5000n, 0n], [30 * D + 1, 5000n, 5000n]];
  for (const [dt, gift, matched] of steps) chk(x.give("ada", gift * U, T0 + dt) === matched * U);
  chk(x.matchedTotal === 25_000n * U && x.reserve === 75_000n * U && x.supply === 1_000_000n * U && x.given.get("ada") === 32_001n * U && x.bal("relief1") === 11_400_200_000n);
  x.checkInvariants();
}
// golden vector 8, typed from RULES.md: a per-account allowance, an empty reserve, a refill by anyone
{
  const y = new Tremor({ ...gp, relief: relief5, match_ppm: 100_000n, match_day_ppm: 100_000n, match_month_ppm: 100_000n, match_account_max: 500n * U }, "ada");
  y.fundMatch("ada", 800n * U, T0); y.ftTransfer("ada", "bob", 10_000n * U); y.ftTransfer("ada", "carol", 10_000n * U);
  const gifts: [string, bigint, bigint][] = [["bob", 4000n, 400n], ["bob", 4000n, 100n], ["bob", 1000n, 0n], ["carol", 4000n, 300n], ["carol", 1000n, 0n]];
  gifts.forEach(([who, gift, matched], i) => chk(y.give(who, gift * U, T0 + 3 + i) === matched * U));
  chk(y.reserve === 0n); y.fundMatch("bob", U, T0 + 8); chk(y.give("carol", 100n * U, T0 + 9) === U);
  chk(y.reserve === 0n && y.matchedTotal === 801n * U && y.fundedTotal === 801n * U && y.supply === 1_000_000n * U && y.bal("relief1") === 2_980_200_000n);
  y.checkInvariants();
}
console.log(`web-conformance: ${all.length} scenarios, ${steps} steps, ${mismatches} mismatches; golden vectors 1, 5, 6, 7 and 8 ${gvOk ? "ok" : "FAILED"}`);
process.exit(mismatches === 0 && gvOk ? 0 : 1);
