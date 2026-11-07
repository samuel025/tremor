#!/usr/bin/env python3
"""M1 simulation. Uses the same integer reference as the golden vectors (reference/tremor_ref.py).
Hourly steps over the committed 60-day window; fixed seeds. Never touches the network."""
import csv, random, sys, pathlib, itertools, json
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reference"))
from tremor_ref import *

U, H = UNIT, 3600
T0 = 1788825600  # 2026-09-08 00:00 UTC
HOURS = 60 * 24


def load_catalog(min_mag=60):
    rows = [l for l in open(ROOT / "data/usgs_60d.csv") if not l.startswith("#")]
    out = []
    for r in csv.DictReader(rows):
        if int(r["mag_x10"]) >= min_mag:
            out.append((r["event_id"], int(r["mag_x10"]), int(r["origin_s"])))
    return out


CAT = load_catalog()


def params(base=5000, week=15000, month=50000, slash=20, quorum=2000):
    return Params(base_ppm=base, week_cap_ppm=week, month_cap_ppm=month, slash_pct=slash,
                  quorum_ppm=quorum, max_age_s=90 * DAY)


class Sim:
    """groups: name -> fraction of S0 held (rest to 'launcher'). All group coins sit in bond balance."""
    def __init__(self, p, groups, seed, bond_counts=None):
        self.p, self.rng = p, random.Random(seed)
        self.t = Tremor(p, "launcher")
        self.act = {}  # hour -> [callable]
        self.pending = {}  # event -> due hour
        self.fake_ids, self.real_ids = set(), set()
        self.passive = "passive"
        groups = dict(groups); groups.setdefault("passive", 0.01)
        for g, f in groups.items():
            n = int(p.s0 * f)
            if n <= 0: continue
            self.t.ft_transfer("launcher", g, n)
            if g != "passive": self.t.deposit_bond(g, n)
        for g, k in (bond_counts or {}).items():  # extra bond funds from launcher
            self.t.ft_transfer("launcher", g, k * p.bond); self.t.deposit_bond(g, k * p.bond)
        self.series = []
        self.prev_minted = 0

    def at(self, hour, fn): self.act.setdefault(hour, []).append(fn)
    now = lambda self, h: T0 + h * H

    def post(self, hour, reporter, eid, mag, origin, fake=False, challenger=None, votes=None):
        """votes: callable(sim) -> list[(acct, side, amount)] evaluated at vote time."""
        (self.fake_ids if fake else self.real_ids).add(eid)
        def rep(h):
            try: self.t.report_event(reporter, eid, mag, origin, self.now(h))
            except Reject: return
            self.pending[eid] = h + self.p.window_s // H
        self.at(hour, rep)
        if challenger:
            def ch(h):
                if eid not in self.t.ev: return
                try: self.t.challenge(challenger, eid, self.now(h))
                except Reject: return
                self.pending[eid] = h + self.p.vote_s // H
                def vt(h2):
                    for a, side, n in votes(self):
                        n = min(n, self.t.bal.get(a, 0))
                        if n > 0:
                            try: self.t.vote(a, eid, side, n, self.now(h2))
                            except Reject: pass
                self.at(h + 1, vt)
            self.at(hour + 1, ch)

    def run(self):
        p, t = self.p, self.t
        S0 = p.s0
        for h in range(HOURS + 6 * 24):  # extra days let late events settle; series only for the 60 days
            for fn in self.act.get(h, []): fn(h)
            for eid, due in list(self.pending.items()):
                if h >= due:
                    try: t.finalize(eid, self.now(h))
                    except Reject: continue
                    del self.pending[eid]
                    for a in list(t.ev[eid].votes): t.claim_vote(a, eid, self.now(h))
            if h % 24 == 23 and h < HOURS:
                d = h // 24; st = t.state(self.now(h))
                minted_total = t.supply - S0
                self.series.append(dict(day=d, supply=t.supply, minted_today=minted_total - self.prev_minted,
                    passive_share_ppm=(S0 // 100) * 10**6 // t.supply,
                    week_use_pct=round(100 * st["m7"] / max(1, t.supply * p.week_cap_ppm // 10**6), 2),
                    month_use_pct=round(100 * st["m30"] / max(1, t.supply * p.month_cap_ppm // 10**6), 2)))
                self.prev_minted = minted_total
        t.check_invariants()
        return self

    # ---- metrics
    def passive_dilution(self):  # total loss of a passive holder's share over the window
        return 1 - (self.p.s0 // 100) * 100 / self.t.supply

    def worst_30d_loss(self):
        sh = [10**6 * (self.p.s0 // 100) / s["supply"] for s in self.series]
        base = [10**6 * 0.01] + sh
        return max(1 - base[i] / base[max(0, i - 30)] for i in range(1, len(base)))

    def worst_week_mint_share(self):
        # max over days of coins minted in the trailing 7 days / supply at the end of that day (the cap is relative to supply at mint time, which is <= this)
        mint = [s["minted_today"] for s in self.series]; sup = [s["supply"] for s in self.series]
        worst = 0
        for i in range(len(mint)):
            lo = max(0, i - 6)
            worst = max(worst, sum(mint[lo:i + 1]) / sup[i])
        return worst

    def clipped_weeks(self):
        wk = {}
        for l in self.t.log:
            if l[0] == "event_counted" and l[3]:
                wk[(l[4] - T0) // (7 * DAY)] = 1
        return sum(1 for w in wk if w < 8) / 8


def real_posts(sim, reporter="rep", challenger=None, votes=None, events=None):
    for eid, mag, origin in (events or CAT):
        hr = (origin - T0 + H - 1) // H + 1
        sim.post(max(1, hr), reporter, eid, mag, origin, challenger=challenger, votes=votes)


def swarm_events(seed):
    r = random.Random(seed); start = T0 + 30 * DAY
    return [(f"swarm{i:02d}", r.randrange(60, 73), start + r.randrange(0, 36 * H)) for i in range(12)]


# ---------------- scenarios
BONDS = {"rep": 40, "liar": 12, "grief": 40}
W = ["w0", "w1", "w2", "w3", "w4"]


def run_s1(p, seed=1):
    s = Sim(p, {}, seed, BONDS); real_posts(s); return s.run()


def run_s2(p, seed=2):
    s = Sim(p, {}, seed, BONDS); ev = sorted(CAT + swarm_events(seed), key=lambda e: e[2]); real_posts(s, events=ev); return s.run()


def run_s3(p, watch_p, seed):
    """liar posts 10 fakes inside week 3; 5 watchers challenge each w.p. watch_p; honest group votes 'not'."""
    s = Sim(p, {"hon": 0.20, "liarv": 0.02}, seed, dict(BONDS, **{w: 6 for w in W}))
    real_posts(s)
    r = s.rng
    honest = lambda sim: [("hon", "not", int(sim.t.bal["hon"] * r.uniform(.3, 1))), ("liarv", "real", sim.t.bal["liarv"])]
    for i in range(10):
        hr = 21 * 24 + r.randrange(0, 7 * 24); org = T0 + hr * H - r.randrange(1, 6) * H
        ch = [w for w in W if r.random() < watch_p]
        s.post(hr, "liar", f"fake{i:02d}", 70, org, fake=True, challenger=ch[0] if ch else None, votes=honest)
    return s.run()


def run_s4(p, hon_hold, variant, seed):
    """whale 40%: variant 'block' challenges every real event and votes no; 'fake' votes yes on 10 fakes (watchers challenge)."""
    s = Sim(p, {"whale": 0.40, "hon": hon_hold}, seed, BONDS); r = s.rng
    if variant == "block":
        v = lambda sim: [("whale", "not", sim.t.bal["whale"] - 3 * sim.p.bond), ("hon", "real", int(sim.t.bal["hon"] * r.uniform(.3, 1)))]
        real_posts(s, challenger="whale", votes=v)
    else:
        real_posts(s)
        v = lambda sim: [("whale", "real", sim.t.bal["whale"] - 3 * sim.p.bond), ("hon", "not", int(sim.t.bal["hon"] * r.uniform(.3, 1)))]
        for i in range(10):
            hr = 21 * 24 + r.randrange(0, 7 * 24)
            s.post(hr, "liar", f"fake{i:02d}", 70, T0 + hr * H - 2 * H, fake=True, challenger="grief", votes=v)
    return s.run()


def run_s5(p, selfish_frac, seed):
    """voters hold 30% of supply; selfish_frac of them vote 'no' on real events; every real event is challenged."""
    s = Sim(p, {"hon": 0.30 * (1 - selfish_frac), "self": 0.30 * selfish_frac}, seed, BONDS); r = s.rng
    v = lambda sim: [("hon", "real", int(sim.t.bal["hon"] * r.uniform(.3, 1))), ("self", "not", int(sim.t.bal.get("self", 0) * r.uniform(.3, 1)))]
    real_posts(s, challenger="grief", votes=v)
    return s.run()


def counted_share(s, ids): return sum(1 for e in ids if s.t.ev.get(e) and s.t.ev[e].status == "counted") / max(1, len(ids))
def rejected_share(s, ids): return sum(1 for e in ids if s.t.ev.get(e) and s.t.ev[e].status == "rejected") / max(1, len(ids))
