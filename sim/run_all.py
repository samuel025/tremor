#!/usr/bin/env python3
"""Runs the grid and the five scenarios; writes results/sim/*. Offline and deterministic."""
import csv, itertools, json, statistics as st, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from simulate import *
OUT = ROOT / "results/sim"; OUT.mkdir(parents=True, exist_ok=True)
SEEDS_GRID, SEEDS_FINAL = list(range(100, 112)), list(range(100, 160))
mean = lambda xs: sum(xs) / len(xs)

def evaluate(base, week, month, slash, quorum, seeds):
    p = params(base, week, month, slash, quorum); r = {}
    s1 = run_s1(p); s2 = run_s2(p)
    r["s1_dilution"] = s1.passive_dilution(); r["s1_clipped_weeks"] = s1.clipped_weeks()
    r["t1_loss30"] = max(s1.worst_30d_loss(), s2.worst_30d_loss())
    r["s2_week"] = s2.worst_week_mint_share()
    s30 = [run_s3(p, 0.0, sd) for sd in seeds[:3]]
    r["s3_week_nowatch"] = max(x.worst_week_mint_share() for x in s30)
    r["s3_dilution_nowatch"] = mean([x.passive_dilution() for x in s30])
    r["s3_rej_half"] = mean([rejected_share(x, x.fake_ids) for x in (run_s3(p, 0.5, sd) for sd in seeds)])
    r["s5_count_30"] = mean([counted_share(x, x.real_ids) for x in (run_s5(p, 0.3, sd) for sd in seeds)])
    r["pass"] = (r["t1_loss30"] <= month / 1e6 and r["s1_clipped_weeks"] <= 0.25 and r["s3_week_nowatch"] <= week / 1e6 + 1e-12
                 and r["s2_week"] <= week / 1e6 + 1e-12 and r["s3_rej_half"] >= 0.9 and r["s5_count_30"] >= 0.9)
    return r

grid = list(itertools.product((2500, 5000, 10000), (10000, 15000, 30000), (30000, 50000, 100000), (10, 20, 40), (1000, 2000, 5000)))
rows = []
for c in grid:
    rows.append(dict(zip(("base_ppm", "week_ppm", "month_ppm", "slash_pct", "quorum_ppm"), c)) | evaluate(*c, SEEDS_GRID))
passing = [r for r in rows if r["pass"]]
dist = lambda r: abs(r["base_ppm"] - 5000) / 5000 + abs(r["week_ppm"] - 15000) / 15000 + abs(r["month_ppm"] - 50000) / 50000 + abs(r["slash_pct"] - 20) / 20 + abs(r["quorum_ppm"] - 2000) / 2000
key = lambda r: (round(r["s1_dilution"], 6), round(r["s2_week"], 6), round(r["s3_dilution_nowatch"], 6), dist(r))
chosen = min(passing, key=key) if passing else None
with open(OUT / "grid.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(sorted(rows, key=lambda r: (not r["pass"],) + key(r)))
json.dump(dict(chosen=chosen, n_pass=len(passing), n_grid=len(rows)), open(OUT / "chosen.json", "w"), indent=1)
print("grid", len(rows), "pass", len(passing)); print("chosen", chosen)
