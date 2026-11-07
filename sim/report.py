#!/usr/bin/env python3
"""Writes results/sim/<scenario>.csv, supply.svg and SUMMARY.md for the chosen parameters (reads chosen.json, grid.csv)."""
import csv, json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from simulate import *
OUT = ROOT / "results/sim"
ch = json.load(open(OUT / "chosen.json")); c = ch["chosen"]
P = params(c["base_ppm"], c["week_ppm"], c["month_ppm"], c["slash_pct"], c["quorum_ppm"])
DEF = params()
SEEDS = list(range(100, 160)); mean = lambda xs: sum(xs) / len(xs)
pct = lambda x, d=2: f"{100 * x:.{d}f}%"

def dump(name, s):
    with open(OUT / f"{name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(s.series[0])); w.writeheader(); w.writerows(s.series)

runs = {}
runs["scenario1_real"] = run_s1(P)
runs["scenario2_swarm"] = run_s2(P)
for wp in (0.0, 0.5, 1.0): runs[f"scenario3_liar_watch{int(wp*100)}"] = run_s3(P, wp, 100)
runs["scenario4_whale_block"] = run_s4(P, 0.45, "block", 100)
runs["scenario4_whale_fakes"] = run_s4(P, 0.45, "fake", 100)
runs["scenario5_selfish30_pen%d" % P.slash_pct] = run_s5(P, 0.3, 100)
for k, s in runs.items(): dump(k, s)

# ---- chart (hand-written SVG, no dependencies)
groups = {"1 Real quakes": ["scenario1_real"], "2 Swarm": ["scenario1_real", "scenario2_swarm"],
          "3 Liar (watch 0/50/100%)": [k for k in runs if "scenario3" in k], "4 Whale": ["scenario4_whale_block", "scenario4_whale_fakes"],
          "5 Selfish voters (30%)": [k for k in runs if "scenario5" in k]}
cols = ["#1b6ca8", "#c2410c", "#2f855a", "#7c3aed"]
W_, H_ = 1000, 640; svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W_} {H_}" font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="#fff"/>']
svg.append('<text x="20" y="24" font-size="16" fill="#222">Tremor supply over 60 real days, relative to initial supply (chosen parameters)</text>')
ymax = max(s.series[-1]["supply"] for s in runs.values()) / P.s0
for gi, (title, keys) in enumerate(groups.items()):
    x0, y0 = 20 + (gi % 3) * 325, 50 + (gi // 3) * 290; w, h = 290, 200
    svg.append(f'<text x="{x0}" y="{y0-6}" fill="#222" font-weight="bold">{title}</text><rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="none" stroke="#999"/>')
    for yv in (1.0, 1.025, 1.05, 1.075, ymax):
        yy = y0 + h - (yv - 1) / (ymax - 1) * h
        svg.append(f'<line x1="{x0}" x2="{x0+w}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="#ddd"/><text x="{x0+2}" y="{yy-2:.1f}" fill="#555">{yv:.3f}</text>')
    for ki, k in enumerate(keys):
        pts = " ".join(f"{x0 + d['day'] / 59 * w:.1f},{y0 + h - (d['supply'] / P.s0 - 1) / (ymax - 1) * h:.1f}" for d in runs[k].series)
        svg.append(f'<polyline fill="none" stroke="{cols[ki % 4]}" stroke-width="2" points="{pts}"/>')
        svg.append(f'<text x="{x0+6}" y="{y0+h+16+ki*14}" fill="{cols[ki % 4]}">{k.replace("scenario","s")}</text>')
    svg.append(f'<text x="{x0+w-40}" y="{y0+h+16}" fill="#555">day 60</text>')
svg.append("</svg>"); (OUT / "supply.svg").write_text("\n".join(svg))

# ---- tables
def s1row(p, label):
    s = run_s1(p); return f"| {label} | {pct(s.passive_dilution())} | {pct(s.worst_30d_loss())} | {pct(s.clipped_weeks(),1)} | {s.t.supply/U:,.0f} |"
r1 = runs["scenario1_real"]
mags = [m for _, m, _ in CAT]
L = ["# Simulation summary", "",
     f"Real catalog: {len(CAT)} events of M6.0+ in the committed 60-day window (2026-09-08 to 2026-11-07 UTC; M6.0-6.9: {sum(1 for m in mags if m<70)}, M7.0+: {sum(1 for m in mags if m>=70)}). "
     "One window is a small sample; a quieter or busier 60 days would give different numbers. Every number comes from the same integer reference that passes GV-1..GV-3.", "",
     "Hourly steps, seeds 100..159 (grid uses 100..111), nothing touches the network. Data: U.S. Geological Survey, ANSS ComCat.", "",
     "## Chosen parameters (proposal for the human to confirm)", "",
     f"base share {c['base_ppm']/1e4:.2f}% at M6.0 (2x at M7, 3x at M8, max 1.5%), weekly cap {c['week_ppm']/1e4:.1f}%, monthly cap {c['month_ppm']/1e4:.1f}%, wrong-vote penalty {c['slash_pct']}%, minimum turnout {c['quorum_ppm']/1e4:.2f}% of supply. "
     f"{ch['n_pass']} of {ch['n_grid']} grid combinations passed every threshold in docs/DECISIONS.md. Full grid: `grid.csv` (passing rows first).", "",
     "Why this one: the lowest passive-holder dilution among passing combinations (tie-breaks in DECISIONS.md). Caution: it passes the 25%-of-weeks cap-binding threshold exactly at the limit (2 of 8 weeks), so this choice has no safety margin on T2.", "",
     "## Scenario 1: real quakes, everyone honest", "",
     "| parameters | passive dilution (60d) | worst 30-day loss | weeks with a clipped mint | final supply (TREM) |", "|---|---|---|---|---|",
     s1row(P, "chosen"), s1row(DEF, "spec defaults (0.5% base)"), "",
     f"With the spec defaults the weekly cap binds in {pct(run_s1(DEF).clipped_weeks(),1)} of weeks, above the 25% threshold (T2), so the spec's own default parameters fail its own test on this window.", ""]
s2 = runs["scenario2_swarm"]
L += ["## Scenario 2: a 12-event swarm (M6.0-7.2 inside 36 h) added to the real catalog", "",
      f"Worst trailing-7-day mint: {pct(s2.worst_week_mint_share(),4)} of supply against a {c['week_ppm']/1e4:.1f}% cap; worst 30-day passive loss {pct(s2.worst_30d_loss())}. Final supply {s2.t.supply/U:,.0f} TREM "
      f"(real-only: {r1.t.supply/U:,.0f}). The monthly cap was already exhausted by the real events, so the swarm adds nothing: this is the cap doing its job, and it also means a real swarm would mint no extra relief.", ""]
base = r1.t.supply
L += ["## Scenario 3: a liar posts 10 fake M7.0 events in one week; 5 watchers each challenge a fake with probability p", "",
      "| p | fakes rejected (mean of 60 seeds) | extra supply from fakes vs real-only | liar's net bond change (TREM, mean) |", "|---|---|---|---|"]
for wp in (0.0, 0.5, 1.0):
    rs = [run_s3(P, wp, sd) for sd in SEEDS]
    extra = mean([(x.t.supply - base) / base for x in rs]); net = mean([(x.t.bal["liar"] + x.t.locked.get("liar", 0)) / U - 12 * P.bond / U for x in rs])
    L.append(f"| {int(wp*100)}% | {pct(mean([rejected_share(x, x.fake_ids) for x in rs]),1)} | {pct(extra,2)} | {net:,.0f} |")
L += ["", "With nobody watching the fakes mint until a cap stops them (at most the weekly cap in any 7 days). In these runs the real events had already used the monthly cap, so the extra from fakes is small or zero; a quiet month would let fakes mint up to the full caps. That is the stated worst case.", ""]
L += ["## Scenario 4: a holder with 40% of supply (honest voters hold 45%, each event 30-100% of them vote)", ""]
rb = [run_s4(P, 0.45, "block", sd) for sd in SEEDS]; rf = [run_s4(P, 0.45, "fake", sd) for sd in SEEDS]
wt = lambda x: (x.t.bal["whale"] + x.t.locked.get("whale", 0) + x.t.tok.get("whale", 0)) / U - 0.40 * P.s0 / U
L += [f"- Challenging and voting no on every real event: the whale blocks {pct(mean([rejected_share(x, x.real_ids) for x in rb]),1)} of real events (mean over 60 seeds). Whale net coins change: {mean([wt(x) for x in rb]):,.0f} TREM (it loses bonds when it is outvoted and gains penalties when it is not).",
      f"- Voting yes on 10 fakes that watchers challenge: {pct(mean([counted_share(x, x.fake_ids) for x in rf]),1)} of fakes still count. Whale net coins change: {mean([wt(x) for x in rf]):,.0f} TREM.",
      "- A majority holder can censor real events and can pass fakes, as the README must say plainly. The caps and the fixed relief list bound the damage; they do not prevent it.", ""]
L += ["## Scenario 5: selfish voters (voters hold 30% of supply; every real event is challenged)", "", "Share of challenged real events that still count, mean of 60 seeds.", "",
      "| selfish share of voting coins | penalty 5% | 10% | 20% | 40% |", "|---|---|---|---|---|"]
for f in (0.0, 0.3, 0.6):
    cells = []
    for pen in (5, 10, 20, 40):
        q = params(c["base_ppm"], c["week_ppm"], c["month_ppm"], pen, c["quorum_ppm"])
        cells.append(pct(mean([counted_share(x, x.real_ids) for x in (run_s5(q, f, sd) for sd in SEEDS)]), 1))
    L.append(f"| {int(f*100)}% | " + " | ".join(cells) + " |")
L += ["", "Voters here are not strategic: a fixed share votes no. The penalty matters only because slashing shrinks a losing side's stake over repeated events, and at 60% selfish the selfish side usually wins, so real events are blocked whatever the penalty. The mechanism assumes an honest majority. Even with 0% selfish voters not every real event counts: when disputes overlap, the honest group's coins are already locked in earlier votes (coins cannot vote twice), turnout can fall under the minimum, and the event is rejected with every bond refunded. The same effect explains why 100% watcher challenge rejects 98.5% rather than 100% of fakes in scenario 3. With many simultaneous disputes the design is weaker, and turnout needs to be high.", "",
      "## Top passing combinations", "", "| base | week | month | slash | quorum | s1 dilution | s1 clipped weeks |", "|---|---|---|---|---|---|---|"]
rows = [r for r in csv.DictReader(open(OUT / "grid.csv")) if r["pass"] == "True"][:6]
L += [f"| {int(r['base_ppm'])/1e4:.2f}% | {int(r['week_ppm'])/1e4:.1f}% | {int(r['month_ppm'])/1e4:.1f}% | {r['slash_pct']}% | {int(r['quorum_ppm'])/1e4:.2f}% | {pct(float(r['s1_dilution']))} | {pct(float(r['s1_clipped_weeks']),1)} |" for r in rows]
L += ["", "Charts: `supply.svg` (one panel per scenario). Series: `scenario*.csv` (daily supply, minted, passive holder share in ppm, weekly and monthly cap use)."]
(OUT / "SUMMARY.md").write_text("\n".join(L) + "\n")
print("\n".join(L))
