#!/usr/bin/env python3
"""Simulation under the bot model. Uses the same integer reference as the golden vectors (reference/tremor_ref.py).
Hourly steps over the committed 60-day window; fixed seeds. Never touches the network."""
import csv, random, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reference"))
from tremor_ref import *

U, H = UNIT, 3600
T0 = 1788825600  # 2026-09-08 00:00 UTC
HOURS = 60 * 24
BOTS = ["bot1", "bot2", "bot3", "bot4", "bot5"]


def load_catalog(min_mag=60):
    rows = [l for l in open(ROOT / "data/usgs_60d.csv") if not l.startswith("#")]
    return [(r["event_id"], int(r["mag_x10"]), int(r["origin_s"])) for r in csv.DictReader(rows) if int(r["mag_x10"]) >= min_mag]


CAT = load_catalog()


def params(base=5000, week=15000, month=50000):
    return Params(base_ppm=base, week_cap_ppm=week, month_cap_ppm=month, min_age_s=H, max_age_s=90 * DAY, publishers=tuple(BOTS), threshold=3)


class Sim:
    def __init__(self, p, seed):
        self.p, self.rng = p, random.Random(seed)
        self.t = Tremor(p, "launcher"); self.t.ft_transfer("launcher", "passive", p.s0 // 100)
        self.act = {}; self.series = []; self.prev_minted = 0
        self.refused = {}  # reason -> count, for attempts the contract refused

    def at(self, hour, fn): self.act.setdefault(hour, []).append(fn)
    now = lambda self, h: T0 + h * H

    def try_(self, fn, key):
        try: return fn()
        except Reject as e: self.refused[key] = self.refused.get(key, 0) + 1

    def bots_attest(self, bots, eid, mag, origin, first_hour):
        """each listed bot attests this record at its own lag (1 h to 3 h after the origin, never before the event is old enough)"""
        for b in bots:
            h = first_hour + self.rng.randrange(0, 3)
            self.at(h, lambda hh, b=b: self.try_(lambda: self.t.attest(b, eid, mag, origin, self.now(hh)), "attest"))

    def real_events(self, events, bots):
        for eid, mag, origin in events:
            self.bots_attest(bots, eid, mag, origin, max(1, (origin - T0 + H - 1) // H + 1))

    def run(self):
        S0 = self.p.s0
        for h in range(HOURS + 72):
            for fn in self.act.get(h, []): fn(h)
            if h % 24 == 23 and h < HOURS:
                d = h // 24; st = self.t.state(self.now(h)); minted_total = self.t.supply - S0
                self.series.append(dict(day=d, supply=self.t.supply, minted_today=minted_total - self.prev_minted, passive_share_ppm=(S0 // 100) * 10**6 // self.t.supply,
                    week_use_pct=round(100 * st["m7"] / max(1, self.t.supply * self.p.week_cap_ppm // 10**6), 2), month_use_pct=round(100 * st["m30"] / max(1, self.t.supply * self.p.month_cap_ppm // 10**6), 2)))
                self.prev_minted = minted_total
        self.t.check_invariants(); return self

    # ---- metrics
    def passive_dilution(self): return 1 - (self.p.s0 // 100) * 100 / self.t.supply

    def worst_30d_loss(self):
        sh = [10**6 * 0.01] + [10**6 * (self.p.s0 // 100) / s["supply"] for s in self.series]
        return max(1 - sh[i] / sh[max(0, i - 30)] for i in range(1, len(sh)))

    def worst_week_mint_share(self):  # trailing-7-day minting / supply at the end of that day (the cap is relative to supply at mint time, which is <= this)
        mint = [s["minted_today"] for s in self.series]; sup = [s["supply"] for s in self.series]
        return max(sum(mint[max(0, i - 6):i + 1]) / sup[i] for i in range(len(mint)))

    def clipped_weeks(self):
        wk = {}
        for l in self.t.log:
            if l[0] == "event_counted" and l[3]: wk[(l[4] - T0) // (7 * DAY)] = 1
        return sum(1 for w in wk if w < 8) / 8

    def counted(self, ids): return sum(1 for e in ids if self.t.ev.get(e) and self.t.ev[e].status == "counted") / max(1, len(ids))


def swarm_events(seed):
    r = random.Random(seed); start = T0 + 30 * DAY
    return [(f"swarm{i:02d}", r.randrange(60, 73), start + r.randrange(0, 36 * H)) for i in range(12)]


def run_s1(p, seed=1):
    s = Sim(p, seed); s.real_events(CAT, BOTS); s.real_ids = [e for e, _, _ in CAT]; return s.run()


def run_s2(p, seed=2):
    ev = sorted(CAT + swarm_events(seed), key=lambda e: e[2]); s = Sim(p, seed); s.real_events(ev, BOTS); s.real_ids = [e for e, _, _ in ev]; return s.run()


def run_s3(p, bad, seed):
    """`bad` bots (1..bad) all attest the same 10 made-up M7.0 quakes inside week 3; the other bots only attest real events."""
    s = Sim(p, seed); s.real_events(CAT, BOTS); s.real_ids = [e for e, _, _ in CAT]; s.fake_ids = []
    r = s.rng
    for i in range(10):
        hr = 21 * 24 + r.randrange(0, 7 * 24); origin = T0 + hr * H - 2 * H - r.randrange(0, 4) * H; eid = f"fake{i:02d}"; s.fake_ids.append(eid)
        s.bots_attest(BOTS[:bad], eid, 70, origin, hr)
    return s.run()


def run_s4(p, offline, seed):
    """the first `offline` bots never attest anything (down for the whole 60 days)"""
    s = Sim(p, seed); s.real_events(CAT, BOTS[offline:]); s.real_ids = [e for e, _, _ in CAT]; return s.run()


def run_s5(p, seed=5, spammers=80):
    """A spammer tries to fill the open-claim limit with made-up claims all through the window while honest bots confirm the real catalog.
    Each spammer account may hold one open claim, so many accounts are needed; claims stay open for claim_wait_s."""
    s = Sim(p, seed); s.real_events(CAT, BOTS); s.real_ids = [e for e, _, _ in CAT]; s.fake_ids = []; s.max_open_claims = 0; r = s.rng
    for k in range(HOURS):
        for j in range(6):  # six spam claims every hour from rotating accounts
            eid = f"spam{k:04d}{j}"; s.fake_ids.append(eid)
            def claim(h, eid=eid, who=f"spam{r.randrange(spammers)}"):
                s.try_(lambda: s.t.submit_claim(who, eid, 70, s.now(h) - 100, s.now(h)), "claim")
                s.max_open_claims = max(s.max_open_claims, len(s.t._open_claims(s.now(h))))
            s.at(k, claim)
    return s.run()


def counted_extra(s, base): return (s.t.supply - base) / base
