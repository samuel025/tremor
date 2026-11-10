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
  threshold: p.threshold, calm_ppm: BigInt(p.calm_ppm), giver_share_ppm: BigInt(p.giver_share_ppm), giver_cap_ppm: BigInt(p.giver_cap_ppm), tap_amount: BigInt(p.tap_amount), publishers: pubs, relief: rel,
});

let steps = 0, mismatches = 0;
const all = JSON.parse(readFileSync(root + "vectors/conformance.json", "utf8")) as any[];
for (const sc of all) {
  const t = new Tremor(P(sc.params, sc.publishers, sc.relief), sc.launcher);
  sc.steps.forEach((st: any, i: number) => {
    const a = st.args, now = st.now; let ok = true;
    try {
      if (st.op === "transfer") t.ftTransfer(a[0], a[1], BigInt(a[2]), now);
      else if (st.op === "tap") t.tap(a[0], "pool", now);
      else if (st.op === "claim_div") t.claimDividend(a[0], now);
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
  max_open: 64, max_claims: 32, claim_wait_s: 43200, threshold: 3, calm_ppm: 0n, giver_share_ppm: 0n, giver_cap_ppm: 0n, tap_amount: 0n, publishers: ["bot1", "bot2", "bot3", "bot4", "bot5"], relief: ["r1", "r2", "r3", "r4", "r5"] };
const g = new Tremor(gp, "ada"); const run = (id: string, mag: number, o: number) => { let r: any = null; for (const b of ["bot1", "bot2", "bot3"]) r = g.attest(b, id, mag, o, o); return r as [bigint, bigint, boolean]; };
let gvOk = true; const chk = (c: boolean) => { if (!c) gvOk = false; };
let r = run("E1", 60, T0); chk(r[0] === 5_000n * U && g.supply === 1_005_000n * U);
r = run("E2", 70, T0 + 48 * H); chk(r[0] === 10_050n * U && g.supply === 1_015_050n * U);
r = run("E3", 60, T0 + 60 * H); chk(r[1] === 2_537_625_000n && r[0] === 175_750_000n && r[2] && g.supply === 1_015_225_750_000n && g.bal("r2") === 3_045_150_000n);
// golden vector 5, typed from RULES.md: calm days pay holders, a quake day pays nothing
const D = 86400; const v = new Tremor({ ...gp, calm_ppm: 100n, relief: ["relief1", "relief2", "relief3", "relief4", "relief5"] }, "ada");
const refused = (f: () => unknown) => { try { f(); return false; } catch (e) { return e instanceof Reject; } };
v.ftTransfer("ada", "bob", 100_000n * U, T0);
chk(v.claimDividend("bob", T0 + 2 * D + 10) === 20_001_000n && v.supply === 1_000_200_010_000n && v.divPot === 180_009_000n);
chk(v.claimDividend("ada", T0 + 2 * D + 10) === 180_009_000n && v.bal("ada") === 900_180_009_000n && v.divPot === 0n);
chk(refused(() => v.claimDividend("ada", T0 + 2 * D + 11)) && refused(() => v.claimDividend("relief1", T0 + 2 * D + 12)));
let q5: any = null; for (const b of ["bot1", "bot2", "bot3"]) q5 = v.attest(b, "E1", 60, T0 + 2 * D + 20, T0 + 2 * D + 20);
chk(q5[0] === 5_001_000_050n && v.supply === 1_005_201_010_050n && v.bal("relief1") === 1_000_200_010n);
chk(refused(() => v.claimDividend("bob", T0 + 3 * D + 5)));
chk(v.claimDividend("bob", T0 + 4 * D + 5) === 10_052_010n && v.supply === 1_005_301_530_151n && v.bal("bob") === 100_030_053_010n && v.calmDays === 3);
v.checkInvariants();
// golden vector 6, typed from RULES.md: only quakes with expected human impact count; three bots must agree on the alert level too
{
  const w = new Tremor({ ...gp, base_ppm: 5000n }, "ada"), e6 = (f: () => unknown) => { try { f(); return false; } catch (e) { return e instanceof Reject; } };
  chk(e6(() => w.attest("bot1", "g1", 60, T0, T0 + 5, 1)) && e6(() => w.submitClaim("judge", "g2", 60, T0, T0 + 5, 1)) && e6(() => w.attest("bot1", "g3", 60, T0, T0 + 5, 0)) && e6(() => w.attest("bot1", "g3", 60, T0, T0 + 5, 5)) && w.ev.size === 0);
  for (const [b, al, dt] of [["bot1", 3, 5], ["bot2", 3, 6], ["bot3", 2, 7]] as [string, number, number][]) chk(w.attest(b, "a2", 60, T0, T0 + dt, al) === null);
  chk(w.supply === 1_000_000n * U);
  const r6 = w.attest("bot4", "a2", 60, T0, T0 + 8, 3); chk(!!r6 && r6[0] === 5_000n * U && w.supply === 1_005_000n * U && e6(() => w.attest("bot5", "a2", 60, T0, T0 + 9, 3)));
}
// golden vectors 7 and 8, typed from RULES.md: the giver bonus (20% of the dividend, each coin given may earn at most 0.5% a day)
{
  const bp = { ...gp, calm_ppm: 100n, giver_share_ppm: 200000n, giver_cap_ppm: 5000n };
  const x = new Tremor(bp, "ada"); x.ftTransfer("ada", "bob", 100_000n * U, T0); x.give("ada", 10_000n * U, T0 + 1);
  chk(x.claimDividend("bob", T0 + 2 * D + 10) === 16_162_424n && x.supply === 1_000_200_010_000n && x.bal("bob") === 100_016_162_424n && x.divPot === 183_847_576n);
  chk(x.claimDividend("ada", T0 + 2 * D + 11) === 143_845_575n + 40_002_000n && x.bal("ada") === 890_183_847_575n && x.divPot === 1n && x.bonusTotal === 40_002_000n);
  const y = new Tremor(bp, "ada"); y.give("ada", 100n * U, T0);
  chk(y.claimDividend("ada", T0 + D + 5) > 0n && y.supply === 1_000_100_000_000n && y.bal("ada") === 999_999_999_999n && y.divPot === 1n && y.bonusTotal === 500_000n);
  x.checkInvariants(); y.checkInvariants();
}
console.log(`web-conformance: ${all.length} scenarios, ${steps} steps, ${mismatches} mismatches; golden vectors 1, 5, 6, 7 and 8 ${gvOk ? "ok" : "FAILED"}`);
process.exit(mismatches === 0 && gvOk ? 0 : 1);
