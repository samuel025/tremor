// Tremor rules engine in TypeScript: a line-for-line port of reference/tremor_ref.py (RULES.md is the source of truth).
// Exact integer arithmetic with BigInt; every division floors. Used by the in-browser simulator, and proven identical to the Python
// reference by tests/conformance.ts on the same 200 seeded scenarios the Rust contract is checked against.
export const DAY = 86400;
const MILLION = 1_000_000n;

export class Reject extends Error {}

export interface Params {
  s0: bigint; min_mag_x10: number; base_ppm: bigint; max_event_ppm: bigint; cooldown_s: number; week_cap_ppm: bigint; month_cap_ppm: bigint;
  min_age_s: number; max_age_s: number; max_open: number; max_claims: number; claim_wait_s: number; threshold: number; tap_amount: bigint;
  publishers: string[]; relief: string[];
}

export interface Version { mag: number; origin: number; who: Set<string> }
export interface Ev {
  created_at: number; claimer: string | null; versions: Map<string, Version>; attested: Set<string>;
  status: "pending" | "counted"; mag_x10: number; origin_s: number; minted: bigint; clipped: boolean;
}
const vkey = (mag: number, origin: number) => `${mag}:${origin}`;

export const sharePpm = (p: Params, mag: number): bigint => {
  const steps = BigInt(Math.max(0, mag - 50)); const v = (p.base_ppm * steps) / 10n;
  return v < p.max_event_ppm ? v : p.max_event_ppm;
};
export const cooldownGap = (origin: number, recent: number[], cooldown: number): number => Math.min(cooldown, ...recent.map((o) => Math.abs(origin - o)));

export function mintAmount(p: Params, supply: bigint, mag: number, gap: number, m7: bigint, m30: bigint): [bigint, bigint, boolean] {
  const raw = (supply * sharePpm(p, mag) * BigInt(gap)) / (MILLION * BigInt(p.cooldown_s));
  const wkAll = (supply * p.week_cap_ppm) / MILLION, moAll = (supply * p.month_cap_ppm) / MILLION;
  const wk = wkAll > m7 ? wkAll - m7 : 0n, mo = moAll > m30 ? moAll - m30 : 0n;
  let m = raw; if (wk < m) m = wk; if (mo < m) m = mo;
  return [m, raw, m < raw];
}
export function split(mint: bigint): bigint[] { const each = mint / 5n; return [each + (mint % 5n), each, each, each, each]; }

export class Tremor {
  p: Params; tok = new Map<string, bigint>(); supply: bigint; ev = new Map<string, Ev>(); recent: number[] = []; buckets = new Map<number, bigint>(); tapped = new Set<string>();
  log: { kind: string; id: string; who?: string; minted?: bigint; clipped?: boolean; attestations?: number; now: number }[] = [];
  constructor(p: Params, launcher: string) {
    if (p.week_cap_ppm <= 0n || p.month_cap_ppm <= 0n || p.base_ppm <= 0n || p.max_event_ppm <= 0n || p.cooldown_s <= 0) throw new Reject("caps and shares must be nonzero");
    if (new Set(p.relief).size !== 5 || p.relief.length !== 5) throw new Reject("need 5 distinct relief accounts");
    if (new Set(p.publishers).size !== 5 || p.publishers.length !== 5) throw new Reject("need 5 distinct publishers");
    if (p.threshold < 1 || p.threshold > 5) throw new Reject("threshold must be 1..5");
    this.p = p; this.supply = p.s0; this.tok.set(launcher, p.s0);
    for (const a of p.relief) if (!this.tok.has(a)) this.tok.set(a, 0n);
  }
  bal = (a: string): bigint => this.tok.get(a) ?? 0n;

  ftTransfer(f: string, t: string, n: bigint): void {
    if (n <= 0n || this.bal(f) < n) throw new Reject("insufficient balance");
    this.tok.set(f, this.bal(f) - n); this.tok.set(t, this.bal(t) + n);
  }
  tap(a: string, pool: string): void {
    if (this.p.tap_amount === 0n) throw new Reject("tap disabled");
    if (a === pool || this.tapped.has(a)) throw new Reject("already tapped");
    if (this.bal(pool) < this.p.tap_amount) throw new Reject("tap pool empty");
    this.tok.set(pool, this.bal(pool) - this.p.tap_amount); this.tok.set(a, this.bal(a) + this.p.tap_amount); this.tapped.add(a);
  }
  mintedLast(now: number, days: number): bigint {
    const d = Math.floor(now / DAY); let s = 0n;
    for (const [k, v] of this.buckets) if (k <= d && k + days > d) s += v;
    return s;
  }
  state(now: number) {
    const m7 = this.mintedLast(now, 7), m30 = this.mintedLast(now, 30);
    const wk = (this.supply * this.p.week_cap_ppm) / MILLION, mo = (this.supply * this.p.month_cap_ppm) / MILLION;
    return { supply: this.supply, m7, m30, weekLeft: wk > m7 ? wk - m7 : 0n, monthLeft: mo > m30 ? mo - m30 : 0n };
  }
  private count(eid: string, mag: number, origin: number, now: number): [bigint, bigint, boolean] {
    const e = this.ev.get(eid)!;
    const gap = cooldownGap(origin, this.recent, this.p.cooldown_s);
    const [m, raw, clipped] = mintAmount(this.p, this.supply, mag, gap, this.mintedLast(now, 7), this.mintedLast(now, 30));
    split(m).forEach((n, i) => this.tok.set(this.p.relief[i], this.bal(this.p.relief[i]) + n));
    this.supply += m;
    const day = Math.floor(now / DAY); this.buckets.set(day, (this.buckets.get(day) ?? 0n) + m);
    this.recent = [...this.recent, origin].slice(-16);
    e.status = "counted"; e.minted = m; e.clipped = clipped; e.mag_x10 = mag; e.origin_s = origin;
    this.log.push({ kind: "event_counted", id: eid, minted: m, clipped, now });
    return [m, raw, clipped];
  }
  private check(eid: string, mag: number, origin: number, now: number, freshOk = false): void {
    const p = this.p;
    if (mag < p.min_mag_x10 || mag > 100) throw new Reject("magnitude out of range");
    if (origin > now) throw new Reject("origin in the future");
    if (now - origin > p.max_age_s) throw new Reject("origin too old");
    if (!freshOk && now - origin < p.min_age_s) throw new Reject("too recent");
    if (!eid || eid.length > 32 || !/^[\x00-\x7f]*$/.test(eid)) throw new Reject("bad event id");
  }
  private openPending(now: number): number {
    let n = 0;
    for (const e of this.ev.values()) if (e.status === "pending" && e.claimer === null && now - Math.min(...[...e.versions.values()].map((v) => v.origin)) <= this.p.max_age_s) n++;
    return n;
  }
  openClaims(now: number): Ev[] { return [...this.ev.values()].filter((e) => e.status === "pending" && e.claimer !== null && now < e.created_at + this.p.claim_wait_s); }

  submitClaim(a: string, eid: string, mag: number, origin: number, now: number): void {
    this.check(eid, mag, origin, now, true);
    if (this.ev.has(eid)) throw new Reject("event id already exists");
    const open = this.openClaims(now);
    if (open.some((e) => e.claimer === a)) throw new Reject("you already have an open claim");
    if (open.length >= this.p.max_claims) throw new Reject("too many open claims");
    const e: Ev = { created_at: now, claimer: a, versions: new Map(), attested: new Set(), status: "pending", mag_x10: 0, origin_s: 0, minted: 0n, clipped: false };
    e.versions.set(vkey(mag, origin), { mag, origin, who: new Set() }); this.ev.set(eid, e);
    this.log.push({ kind: "claim_submitted", id: eid, who: a, now });
  }
  attest(pub: string, eid: string, mag: number, origin: number, now: number): [bigint, bigint, boolean] | null {
    if (!this.p.publishers.includes(pub)) throw new Reject("not a publisher");
    this.check(eid, mag, origin, now);
    let e = this.ev.get(eid);
    if (e && e.status === "counted") throw new Reject("already counted");
    if (e && e.attested.has(pub)) throw new Reject("already attested");
    if (!e) {
      if (this.openPending(now) >= this.p.max_open) throw new Reject("too many pending events");
      e = { created_at: now, claimer: null, versions: new Map(), attested: new Set(), status: "pending", mag_x10: 0, origin_s: 0, minted: 0n, clipped: false }; this.ev.set(eid, e);
    }
    const k = vkey(mag, origin); const v = e.versions.get(k) ?? { mag, origin, who: new Set<string>() }; e.versions.set(k, v);
    v.who.add(pub); e.attested.add(pub);
    this.log.push({ kind: "attested", id: eid, who: pub, attestations: v.who.size, now });
    if (v.who.size >= this.p.threshold) return this.count(eid, mag, origin, now);
    return null;
  }

  checkInvariants(): void {
    let minted = 0n; for (const e of this.ev.values()) minted += e.minted;
    if (this.supply !== this.p.s0 + minted) throw new Error("supply = S0 + mints");
    let all = 0n; for (const v of this.tok.values()) all += v; if (all !== this.supply) throw new Error("balances = supply");
    for (const e of this.ev.values()) {
      if (e.minted !== 0n && e.status !== "counted") throw new Error("minted but not counted");
      if (e.status === "counted" && (e.versions.get(vkey(e.mag_x10, e.origin_s))?.who.size ?? 0) < this.p.threshold) throw new Error("counted without enough attestations");
    }
    for (const k of this.buckets.keys()) {
      if (this.mintedLast(k * DAY, 7) > (this.supply * this.p.week_cap_ppm) / MILLION) throw new Error("weekly cap");
      if (this.mintedLast(k * DAY, 30) > (this.supply * this.p.month_cap_ppm) / MILLION) throw new Error("monthly cap");
    }
  }

  /** Same shape as the Python snapshot (numbers instead of big integers), for the conformance test. */
  snapshot() {
    const nz = (m: Map<string | number, bigint>) => Object.fromEntries([...m.entries()].filter(([, v]) => v !== 0n).sort((a, b) => (String(a[0]) < String(b[0]) ? -1 : 1)).map(([k, v]) => [String(k), Number(v)]));
    const events: Record<string, unknown> = {};
    for (const [id, e] of [...this.ev.entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1))) {
      const versions = [...e.versions.values()].sort((a, b) => a.mag - b.mag || a.origin - b.origin).map((v) => [v.mag, v.origin, [...v.who].sort()]);
      events[id] = [e.status, Number(e.minted), e.clipped, e.claimer ?? "", e.created_at, versions];
    }
    return { supply: Number(this.supply), tok: nz(this.tok), buckets: nz(this.buckets as Map<string | number, bigint>), recent: [...this.recent], tapped: [...this.tapped].sort(), events };
  }
}
