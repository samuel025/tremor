#!/usr/bin/env python3
"""Seeded random scenarios -> vectors/conf-<n>.json (inputs plus the Python reference's state after every step).
The Rust core replays them and must match exactly (make conformance)."""
import json, pathlib, random, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reference"))
from tremor_ref import *
U = UNIT
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
POOL = "pool"  # an account the launcher funds; tap() pays starter coins out of it
ACCTS = ["a0", "a1", "a2", "a3", "a4", "a5"]; EIDS = [f"ev{i}" for i in range(10)] + ["", "x" * 40]


def make(seed):
    r = random.Random(seed)
    p = Params(s0=r.choice([10**9, 10**12]), base_ppm=r.choice([2500, 5000, 10000]), max_event_ppm=15000,
               cooldown_s=r.choice([300, 1000]), week_cap_ppm=r.choice([10000, 15000, 30000]),
               month_cap_ppm=r.choice([30000, 50000]), bond=r.choice([10**6, 5 * 10**6]),
               window_s=r.choice([100, 200]), vote_s=r.choice([150, 300]), slash_pct=r.choice([10, 20, 100]),
               quorum_ppm=r.choice([1000, 20000, 200000]), max_age_s=5000, tap_amount=r.choice([0, 10**5, 10**6]),
               relief=("r1", "r2", "r3", "r4", "r5"))
    t = Tremor(p, "a0"); now = 20000 * DAY + r.randrange(0, 3 * DAY)
    steps = []
    for a in ACCTS[1:] + ACCTS:  # fund everyone so flows can run: transfers from a0, then bond deposits
        if a in t.bal or a in ACCTS[1:] and a not in t.tok:
            op, args = "transfer", ["a0", a, p.s0 // r.choice([8, 20, 200])]; t.ft_transfer(*args)
        else:
            op, args = "deposit", [a, t.tok[a] // r.choice([2, 3, 10])]; t.deposit_bond(*args)
        t.check_invariants(); steps.append(dict(op=op, args=args, now=now, ok=True, snap=t.snapshot()))
    t.ft_transfer("a0", POOL, p.s0 // r.choice([200, 2000])); steps.append(dict(op="transfer", args=["a0", POOL, t.tok[POOL]], now=now, ok=True, snap=t.snapshot()))
    for _ in range(r.randrange(60, 160)):
        now += r.choice([0, 1, 5, 10, 20, 30, 45, 60, 90, 120, 250, 400, 3000, DAY // 2]) if r.random() < 0.3 else r.choice([0, 1, 3, 8, 15])
        a = r.choice(ACCTS); eid = r.choice(EIDS); big = p.s0 // r.choice([2, 50, 500, 5000])
        op = r.choices(["transfer", "deposit", "withdraw", "report", "challenge", "vote", "finalize", "claim", "tap"],
                       [2, 2, 1, 5, 5, 12, 6, 6, 3])[0]
        good = {"challenge": [k for k, e in t.ev.items() if e.status == "waiting" and now < e.reported_at + p.window_s],
                "vote": [k for k, e in t.ev.items() if e.status == "challenged" and now < e.challenged_at + p.vote_s],
                "finalize": [k for k, e in t.ev.items() if e.status in ("waiting", "challenged")],
                "claim": [k for k, e in t.ev.items() if e.votes and e.status in ("counted", "rejected")]}.get(op, [])
        if good and r.random() < 0.85: eid = r.choice(good)
        if op == "vote": big = max(1, t.supply // r.choice([20, 100, 400, 1000, 5000]))
        if op == "transfer": args = [a, r.choice(ACCTS), r.randrange(0, big)]
        elif op == "deposit": args = [a, r.randrange(0, big)]
        elif op == "withdraw": args = [a, r.randrange(0, big // 2 + 1)]
        elif op == "report": args = [a, eid, r.choice([55, 60, 61, 65, 70, 70, 85, 101]), now - r.choice([0, 5, 90, 1000, 1000, 4000, 9000, -50])]
        elif op == "challenge": args = [a, eid]
        elif op == "vote": args = [a, eid, r.choice(["real", "not"]), r.randrange(0, big)]
        elif op == "finalize": args = [eid]
        elif op == "tap": args = [a]
        else: args = [a, eid]
        try:
            m = {"transfer": lambda: t.ft_transfer(*args), "deposit": lambda: t.deposit_bond(*args),
                 "withdraw": lambda: t.withdraw_bond(*args), "report": lambda: t.report_event(*args, now),
                 "challenge": lambda: t.challenge(*args, now), "vote": lambda: t.vote(*args, now),
                 "finalize": lambda: t.finalize(*args, now), "claim": lambda: t.claim_vote(*args, now),
                 "tap": lambda: t.tap(args[0], POOL)}
            m[op](); ok = True
        except Reject: ok = False
        t.check_invariants()
        steps.append(dict(op=op, args=args, now=now, ok=ok, snap=t.snapshot()))
    return dict(seed=seed, params=dict(s0=p.s0, min_mag_x10=p.min_mag_x10, base_ppm=p.base_ppm, max_event_ppm=p.max_event_ppm, cooldown_s=p.cooldown_s,
        week_cap_ppm=p.week_cap_ppm, month_cap_ppm=p.month_cap_ppm, bond=p.bond, window_s=p.window_s, vote_s=p.vote_s,
        slash_pct=p.slash_pct, quorum_ppm=p.quorum_ppm, max_age_s=p.max_age_s, tap_amount=p.tap_amount), launcher="a0",
        relief=list(p.relief), steps=steps)


if __name__ == "__main__":
    out = ROOT / "vectors" / "conformance.json"
    sc = [make(1000 + i) for i in range(N)]
    cnt = {}
    for s in sc:
        for st in s["steps"]: cnt[(st["op"], st["ok"])] = cnt.get((st["op"], st["ok"]), 0) + 1
    out.write_text(json.dumps(sc, separators=(",", ":")))
    print(N, "scenarios;", sum(len(s["steps"]) for s in sc), "steps;", sorted(cnt.items()))
