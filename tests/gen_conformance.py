#!/usr/bin/env python3
"""Seeded random scenarios -> vectors/conformance.json (inputs plus the Python reference's state after every step).
The Rust contract logic replays them and must match exactly (make conformance)."""
import json, pathlib, random, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reference"))
from tremor_ref import *
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
POOL = "pool"  # an account the launcher funds; tap() pays starter coins out of it
USERS = ["a0", "a1", "a2", "a3", "a4", "a5"]; PUBS = ["p1", "p2", "p3", "p4", "p5"]
EIDS = [f"ev{i}" for i in range(10)] + ["", "x" * 40]


def make(seed, long=False):
    r = random.Random(seed)
    p = Params(s0=r.choice([10**9, 10**12]), base_ppm=r.choice([2500, 5000, 10000]), max_event_ppm=15000, cooldown_s=r.choice([300, 1000]),
               week_cap_ppm=r.choice([10000, 15000, 30000]), month_cap_ppm=r.choice([30000, 50000]), min_age_s=r.choice([0, 0, 40]), max_age_s=5000,
               max_open=r.choice([3, 8, 64]), max_claims=r.choice([2, 5, 32]), claim_wait_s=r.choice([100, 1000]), threshold=r.choice([2, 3, 3, 4]),
               tap_amount=r.choice([0, 10**5, 10**6]), calm_ppm=r.choice([100, 1000] if long else [0, 100, 1000, 5000]), publishers=tuple(PUBS), relief=("r1", "r2", "r3", "r4", "r5"))
    t = Tremor(p, "a0"); now = 20000 * DAY + r.randrange(0, 3 * DAY)
    steps = []
    t.ft_transfer("a0", POOL, p.s0 // r.choice([200, 2000]), now); steps.append(dict(op="transfer", args=["a0", POOL, t.tok[POOL]], now=now, ok=True, snap=t.snapshot()))
    for _ in range(r.randrange(12, 20) if long else r.randrange(80, 200)):
        now += r.choice([0, 1, 5, 10, 20, 30, 45, 60, 90, 120, 250, 400, 3000]) if r.random() < 0.4 else r.choice([0, 1, 3, 8, 15])
        if r.random() < 0.04: now += r.choice([450 * DAY] if long else [DAY, DAY, 2 * DAY, 9 * DAY])  # days pass, so calm-day dividends are settled (450: more than one call is needed)
        op = r.choices(["attest", "claim", "tap", "transfer", "give", "claim_div"], [14, 5, 3, 3, 2, 3])[0]
        eid = r.choice(EIDS); mag = r.choice([55, 60, 61, 65, 70, 70, 85, 101]); origin = now - r.choice([0, 5, 45, 90, 1000, 1000, 4000, 6000, -50])
        pend = [k for k, e in t.ev.items() if e.status == "pending"]
        if op == "attest":
            who = r.choice(PUBS + ["a1"]) if r.random() < 0.9 else "a2"
            if pend and r.random() < 0.75:  # usually back an existing pending event, mostly with the same record
                eid = r.choice(pend); e = t.ev[eid]
                if r.random() < 0.85:
                    mag, origin = r.choice(sorted(e.versions)) if e.versions else (mag, origin)
                free = [x for x in PUBS if x not in e.attested]
                if free and r.random() < 0.85: who = r.choice(free)
            args = [who, eid, mag, origin]
        elif op == "claim": args = [r.choice(USERS), eid, mag, origin]
        elif op == "tap": args = [r.choice(USERS)]
        elif op == "claim_div": args = [r.choice(USERS + ["r1", POOL])]
        elif op == "give": args = [r.choice(USERS + ["r1", POOL]), r.choice([0, 1, 4, 7, 12345, r.randrange(0, p.s0 // r.choice([50, 5000]))])]
        else: args = [r.choice(USERS), r.choice(USERS), r.randrange(0, p.s0 // r.choice([2, 50, 500]))]
        try:
            {"attest": lambda: t.attest(*args, now), "claim": lambda: t.submit_claim(*args, now), "tap": lambda: t.tap(args[0], POOL, now),
             "transfer": lambda: t.ft_transfer(*args, now), "claim_div": lambda: t.claim_dividend(args[0], now), "give": lambda: t.give(*args, now)}[op](); ok = True
        except Reject: ok = False
        t.check_invariants()
        steps.append(dict(op=op, args=args, now=now, ok=ok, snap=t.snapshot()))
    params = dict(s0=p.s0, min_mag_x10=p.min_mag_x10, base_ppm=p.base_ppm, max_event_ppm=p.max_event_ppm, cooldown_s=p.cooldown_s, week_cap_ppm=p.week_cap_ppm,
                  month_cap_ppm=p.month_cap_ppm, min_age_s=p.min_age_s, max_age_s=p.max_age_s, max_open=p.max_open, max_claims=p.max_claims,
                  claim_wait_s=p.claim_wait_s, threshold=p.threshold, tap_amount=p.tap_amount, calm_ppm=p.calm_ppm)
    return dict(seed=seed, params=params, launcher="a0", publishers=list(p.publishers), relief=list(p.relief), steps=steps)


if __name__ == "__main__":
    out = ROOT / "vectors" / "conformance.json"
    sc = [make(1000 + i) for i in range(N)] + [make(5000 + i, long=True) for i in range(2)]  # two short scenarios with 450-day gaps
    cnt = {}
    for s in sc:
        for st in s["steps"]: cnt[(st["op"], st["ok"])] = cnt.get((st["op"], st["ok"]), 0) + 1
    out.write_text(json.dumps(sc, separators=(",", ":")))
    counted = sum(1 for s in sc for e in s["steps"][-1]["snap"]["events"].values() if e[0] == "counted")
    print(len(sc), "scenarios;", sum(len(s["steps"]) for s in sc), "steps;", "events counted at the end:", counted, ";", sorted(cnt.items()))
