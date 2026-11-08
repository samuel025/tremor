// Proves the TypeScript rules engine (used by the in-browser simulator) is identical to the Python reference:
// replays vectors/conformance.json (200 seeded scenarios, the same file the Rust contract is checked against) and the three golden vectors.
// Run: node tests/conformance.ts   (Node 23.6+ runs TypeScript directly)
import { readFileSync } from "node:fs";
import { Reject, Tremor, type Params } from "../src/sim/engine.ts";

const root = new URL("../../", import.meta.url).pathname;
const stable = (x: unknown): string => JSON.stringify(x, (_, v) => (v && typeof v === "object" && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort()) : v));
const P = (p: any, pubs: string[], rel: string[]): Params => ({
  s0: BigInt(p.s0), min_mag_x10: p.min_mag_x10, base_ppm: BigInt(p.base_ppm), max_event_ppm: BigInt(p.max_event_ppm), cooldown_s: p.cooldown_s, week_cap_ppm: BigInt(p.week_cap_ppm),
  month_cap_ppm: BigInt(p.month_cap_ppm), min_age_s: p.min_age_s, max_age_s: p.max_age_s, max_open: p.max_open, max_claims: p.max_claims, claim_wait_s: p.claim_wait_s,
  threshold: p.threshold, tap_amount: BigInt(p.tap_amount), publishers: pubs, relief: rel,
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
      else if (st.op === "attest") t.attest(a[0], a[1], a[2], a[3], now);
      else if (st.op === "claim") t.submitClaim(a[0], a[1], a[2], a[3], now);
      else throw new Error("unknown op " + st.op);
    } catch (e) { if (e instanceof Reject) ok = false; else throw e; }
    t.checkInvariants(); steps++;
    if (ok !== st.ok || stable(t.snapshot()) !== stable(st.snap)) { mismatches++; if (mismatches <= 3) console.error(`MISMATCH seed ${sc.seed} step ${i} op ${st.op} ok(ts)=${ok} ok(py)=${st.ok}`); }
  });
}
// golden vector 1, typed from RULES.md (independent of the Python reference): each event confirmed by 3 bots at its origin time
const U = 1_000_000n, T0 = 20000 * 86400, H = 3600;
const gp: Params = { s0: 1_000_000n * U, min_mag_x10: 60, base_ppm: 5000n, max_event_ppm: 15000n, cooldown_s: 86400, week_cap_ppm: 15000n, month_cap_ppm: 50000n, min_age_s: 0, max_age_s: 5_184_000,
  max_open: 64, max_claims: 32, claim_wait_s: 43200, threshold: 3, tap_amount: 0n, publishers: ["bot1", "bot2", "bot3", "bot4", "bot5"], relief: ["r1", "r2", "r3", "r4", "r5"] };
const g = new Tremor(gp, "ada"); const run = (id: string, mag: number, o: number) => { let r: any = null; for (const b of ["bot1", "bot2", "bot3"]) r = g.attest(b, id, mag, o, o); return r as [bigint, bigint, boolean]; };
let gvOk = true; const chk = (c: boolean) => { if (!c) gvOk = false; };
let r = run("E1", 60, T0); chk(r[0] === 5_000n * U && g.supply === 1_005_000n * U);
r = run("E2", 70, T0 + 48 * H); chk(r[0] === 10_050n * U && g.supply === 1_015_050n * U);
r = run("E3", 60, T0 + 60 * H); chk(r[1] === 2_537_625_000n && r[0] === 175_750_000n && r[2] && g.supply === 1_015_225_750_000n && g.bal("r2") === 3_045_150_000n);
console.log(`web-conformance: ${all.length} scenarios, ${steps} steps, ${mismatches} mismatches; golden vector 1 ${gvOk ? "ok" : "FAILED"}`);
process.exit(mismatches === 0 && gvOk ? 0 : 1);
