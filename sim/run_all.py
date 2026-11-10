#!/usr/bin/env python3
"""Runs the grid and writes results/sim/grid.csv and chosen.json. Offline and deterministic."""
import csv, itertools, json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from simulate import *
OUT = ROOT / "results/sim"; OUT.mkdir(parents=True, exist_ok=True)
SEEDS = list(range(100, 112)); mean = lambda xs: sum(xs) / len(xs)


def evaluate(base, week, month, calm):
    p = params(base, week, month, calm); r = {}
    s1, s2 = run_s1(p), run_s2(p)
    r["s1_dilution"] = s1.passive_dilution(); r["s1_clipped_weeks"] = s1.clipped_weeks(); r["t1_loss30"] = max(s1.worst_30d_loss(), s2.worst_30d_loss()); r["s2_week"] = s2.worst_week_mint_share()
    s3 = [run_s3(p, 3, sd) for sd in SEEDS[:4]]
    r["s3_week_3bad"] = max(x.worst_week_mint_share() for x in s3); r["s3_extra_3bad"] = mean([x.passive_dilution() for x in s3])
    r["s3_fakes_2bad"] = max(sum(1 for e in x.fake_ids if x.t.ev.get(e) and x.t.ev[e].status == "counted") for x in (run_s3(p, 2, sd) for sd in SEEDS[:4]))
    r["s4_real_counted_2off"] = min(x.counted(x.real_ids) for x in (run_s4(p, 2, sd) for sd in SEEDS[:4]))
    r["c1_week_dividend"] = max(s1.worst_week_dividend_share(), s2.worst_week_dividend_share())
    r["pass"] = (r["c1_week_dividend"] <= 7 * calm / 1e6 + 1e-12 and r["t1_loss30"] <= month / 1e6 and r["s1_clipped_weeks"] <= 0.25 and r["s3_week_3bad"] <= week / 1e6 + 1e-12 and r["s2_week"] <= week / 1e6 + 1e-12
                 and r["s3_fakes_2bad"] == 0 and r["s4_real_counted_2off"] == 1.0)
    return r


# ---- the calm-day dividend: candidates checked with the confirmed parameters (rule written in docs/DECISIONS.md before this ran)
CONFIRMED = (2500, 15000, 50000); cands = []
for calm in (0, 50, 100, 200):
    r = evaluate(*CONFIRMED, calm); s = run_s1(params(*CONFIRMED, calm))
    cands.append(dict(calm_ppm=calm) | r | dict(calm_days=s.t.calm_days, holders_minted=s.t.div_total, relief_minted=s.t.supply - s.p.s0 - s.t.div_total, final_supply=s.t.supply))
off = run_s1(params(*CONFIRMED, 0))
for c in cands:  # C3 (docs/DECISIONS.md): no quake mint and no relief balance is smaller than with the dividend off, and quake mints in total grow no faster than supply
    s = run_s1(params(*CONFIRMED, c["calm_ppm"])); grow = s.t.supply / off.t.supply
    q = lambda x: [l[2] for l in x.t.log if l[0] == "event_counted"]
    c["c3"] = all(a <= b for a, b in zip(q(off), q(s))) and all(s.t.tok[r] >= off.t.tok[r] for r in s.p.relief) and sum(q(s)) <= sum(q(off)) * grow
    c["pass"] = c["pass"] and c["c3"]
ok = [c["calm_ppm"] for c in cands if c["pass"] and c["calm_ppm"] > 0]
CALM = 100 if 100 in ok else (max(ok) if ok else None)
json.dump(dict(candidates=cands, chosen_calm_ppm=CALM), open(OUT / "calm.json", "w"), indent=1)
print("calm candidates", [(c["calm_ppm"], c["pass"], round(c["s1_clipped_weeks"], 3)) for c in cands], "chosen", CALM)
if CALM is None: sys.exit("no calm-day dividend candidate passes T1..T5: stopping, nothing changed")

grid = list(itertools.product((2500, 5000, 10000), (10000, 15000, 30000), (30000, 50000, 100000)))
rows = [dict(zip(("base_ppm", "week_ppm", "month_ppm"), c)) | evaluate(*c, CALM) for c in grid]
passing = [r for r in rows if r["pass"]]
dist = lambda r: abs(r["base_ppm"] - 5000) / 5000 + abs(r["week_ppm"] - 15000) / 15000 + abs(r["month_ppm"] - 50000) / 50000
key = lambda r: (round(r["s1_dilution"], 6), round(r["s2_week"], 6), dist(r))
chosen = min(passing, key=key) if passing else None
with open(OUT / "grid.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(sorted(rows, key=lambda r: (not r["pass"],) + key(r)))
json.dump(dict(chosen=chosen, n_pass=len(passing), n_grid=len(rows)), open(OUT / "chosen.json", "w"), indent=1)
print("grid", len(rows), "pass", len(passing)); print("chosen", chosen)
