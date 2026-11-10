#!/usr/bin/env python3
"""Writes results/sim/<scenario>.csv, supply.svg and SUMMARY.md for the chosen parameters (reads chosen.json, grid.csv)."""
import csv, json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from simulate import *
OUT = ROOT / "results/sim"; ch = json.load(open(OUT / "chosen.json")); c = ch["chosen"]
CJ = json.load(open(OUT / "calm.json")); CALM = CJ["chosen_calm_ppm"]
P = params(c["base_ppm"], c["week_ppm"], c["month_ppm"], CALM); DEF = params(5000, calm=CALM)
SEEDS = list(range(100, 120)); mean = lambda xs: sum(xs) / len(xs); pct = lambda x, d=2: f"{100 * x:.{d}f}%"
fakes_counted = lambda s: sum(1 for e in s.fake_ids if e in s.t.ev and s.t.ev[e].status == "counted")

def dump(name, s):
    with open(OUT / f"{name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(s.series[0])); w.writeheader(); w.writerows(s.series)

runs = {"scenario1_real": run_s1(P), "scenario2_swarm": run_s2(P), "scenario3_badbots_k2": run_s3(P, 2, 100), "scenario3_badbots_k3": run_s3(P, 3, 100),
        "scenario4_offline_m2": run_s4(P, 2, 100), "scenario4_offline_m3": run_s4(P, 3, 100), "scenario5_claimspam": run_s5(P, 100)}
give_runs = {m: run_s6(P, m, 100) for m in GIVE_MODES}
for m, s in give_runs.items(): runs[f"scenario6_give_{m}"] = s
for k, s in runs.items(): dump(k, s)

# ---- chart (hand-written SVG, no dependencies)
groups = {"1 Real quakes": ["scenario1_real"], "2 Swarm": ["scenario1_real", "scenario2_swarm"], "3 Bad bots (2 / 3 of 5)": ["scenario3_badbots_k2", "scenario3_badbots_k3"],
          "4 Bots offline (2 / 3 of 5)": ["scenario4_offline_m2", "scenario4_offline_m3"], "5 Claim spam": ["scenario5_claimspam"], "6 Giving (supply is unchanged)": ["scenario6_give_none", "scenario6_give_many_small"]}
cols = ["#1d1d1f", "#b64400", "#86868b"]; W_, H_ = 1000, 640
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W_} {H_}" font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="#fff"/>',
       '<text x="20" y="24" font-size="16" fill="#222">Tremor supply over 60 real days, relative to initial supply (chosen parameters)</text>']
ymax = max(s.series[-1]["supply"] for s in runs.values()) / P.s0
for gi, (title, keys) in enumerate(groups.items()):
    x0, y0 = 20 + (gi % 3) * 325, 50 + (gi // 3) * 290; w, h = 290, 200
    svg.append(f'<text x="{x0}" y="{y0-6}" fill="#222" font-weight="bold">{title}</text><rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="none" stroke="#999"/>')
    for yv in (1.0, 1.025, 1.05, 1.075, ymax):
        yy = y0 + h - (yv - 1) / (ymax - 1) * h
        svg.append(f'<line x1="{x0}" x2="{x0+w}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="#ddd"/><text x="{x0+2}" y="{yy-2:.1f}" fill="#555">{yv:.3f}</text>')
    for ki, k in enumerate(keys):
        pts = " ".join(f"{x0 + d['day'] / 59 * w:.1f},{y0 + h - (d['supply'] / P.s0 - 1) / (ymax - 1) * h:.1f}" for d in runs[k].series)
        svg.append(f'<polyline fill="none" stroke="{cols[ki % 3]}" stroke-width="2" points="{pts}"/><text x="{x0+6}" y="{y0+h+16+ki*14}" fill="{cols[ki % 3]}">{k.replace("scenario","s")}</text>')
svg.append("</svg>"); (OUT / "supply.svg").write_text("\n".join(svg))

# ---- tables
def s1row(p, label):
    s = run_s1(p); return f"| {label} | {pct(s.passive_dilution())} | {pct(s.worst_30d_loss())} | {pct(s.clipped_weeks(),1)} | {s.t.supply/U:,.0f} |"
r1 = runs["scenario1_real"]; s2 = runs["scenario2_swarm"]
L = ["# Simulation summary", "",
     f"Real catalog: {len(ALL6)} events of M6.0+ in the committed 60-day window (2026-09-08 to 2026-11-07 UTC). Only quakes whose USGS PAGER alert level (an estimate of expected human impact) is yellow or higher count: {len(CAT)} of the {len(ALL6)} "
     f"({', '.join(f'{n} {k}' for k, n in sorted({k: sum(1 for e, _, _ in ALL6 if ALERT[e] == v) for k, v in LEVEL.items()}.items(), key=lambda kv: LEVEL[kv[0]]))}). Scenarios 1 to 7 use those {len(CAT)}; scenario 8 sends all {len(ALL6)} to the contract. "
     "One window is a small sample. Every number comes from the same integer reference that passes the golden vectors. Five fixed bots, three must agree; bots attest 1 to 3 hours after a quake.", "",
     "Hourly steps, seeds 100..119 (grid uses 100..111), nothing touches the network. Data: U.S. Geological Survey, ANSS ComCat.", "",
     "## Chosen parameters", "",
     f"base share {c['base_ppm']/1e4:.2f}% at M6.0 (2x at M7, 3x at M8, max 1.5%), weekly cap {c['week_ppm']/1e4:.1f}%, monthly cap {c['month_ppm']/1e4:.1f}%, calm-day dividend {CALM/1e4:.2f}% of supply for holders after each full day with no counted quake (outside the caps, which bound quake mints; every scenario below has it switched on). "
     f"{ch['n_pass']} of {ch['n_grid']} grid combinations passed every threshold in docs/DECISIONS.md. The grid's own pick (lowest passive-holder dilution) is base {ch['grid_pick']['base_ppm']/1e4:.2f}%, weekly {ch['grid_pick']['week_ppm']/1e4:.1f}%, monthly {ch['grid_pick']['month_ppm']/1e4:.1f}%; the confirmed values above are kept because they still pass. Full grid: `grid.csv` (passing rows first).", "",
     "## Scenario 1: real quakes, five honest bots", "", "| parameters | passive dilution (60d) | worst 30-day loss | weeks with a clipped mint | final supply (TREM) |", "|---|---|---|---|---|",
     s1row(P, "chosen"), s1row(DEF, "spec defaults (0.5% base)"), "",
     f"With the spec defaults the weekly cap binds in {pct(run_s1(DEF).clipped_weeks(),1)} of weeks.", "",
     "## Scenario 2: a 12-event swarm (M6.0-7.2 inside 36 h) added to the real catalog", "",
     f"Worst trailing-7-day mint: {pct(s2.worst_week_mint_share(),4)} of supply against a {c['week_ppm']/1e4:.1f}% cap; worst 30-day passive loss {pct(s2.worst_30d_loss())}. Final supply {s2.t.supply/U:,.0f} TREM (real-only: {r1.t.supply/U:,.0f}). The monthly cap was already exhausted by the real events, so the swarm adds nothing.", "",
     "## Scenario 3: bad bots post 10 identical made-up M7.0 quakes in one week", "", "| bad bots (of 5) | fakes that count (of 10, mean of 20 seeds) | extra supply from fakes | worst 7-day mint |", "|---|---|---|---|"]
base_supply = run_s3(P, 0, 100).t.supply
for k in range(6):
    rs = [run_s3(P, k, sd) for sd in SEEDS]
    L.append(f"| {k} | {mean([fakes_counted(x) for x in rs]):.1f} | {pct(mean([(x.t.supply - base_supply) / base_supply for x in rs]))} | {pct(max(x.worst_week_mint_share() for x in rs),3)} |")
L += ["", "Below three bad bots no fake can count. At three or more, fakes count, but never past the caps (the real events had already used much of the allowance, so a quieter month would let more through). Honest bots do not stop it: counting needs three matching attestations and nothing else. That is the weak spot: trust sits in the five fixed bots.", "",
      "## Scenario 4: bots offline for the whole 60 days", "", "| bots offline (of 5) | real events that count | final supply (TREM) |", "|---|---|---|"]
for m in range(6):
    s = run_s4(P, m, 100); L.append(f"| {m} | {pct(s.counted(s.real_ids),1)} | {s.t.supply/U:,.0f} |")
L += ["", "With two or fewer bots offline every real event still counts. With three or more offline nothing counts and nothing is created: the system fails safe rather than minting on too little evidence.", "",
      "## Scenario 5: claim spam (6 made-up claims an hour from 80 accounts, all 60 days)", ""]
s5 = runs["scenario5_claimspam"]
L += [f"- Real events that count: {pct(s5.counted(s5.real_ids),1)}. Made-up claims that count: {fakes_counted(s5)} of {len(s5.fake_ids)}.",
      f"- Most claims open at once: {s5.max_open_claims} against a limit of {P.max_claims}; the contract refused {s5.refused.get('claim', 0)} claims.",
      "- Claims have their own limit, separate from the limit on events the bots start, so claim spam cannot take the slots the bots need.", "",
      "## Scenario 6: community giving (holders send their own coins to the relief list)", "",
      "Assumed behaviour, not measured: 100 holders with 0.1% of the initial supply each and one with 5%, reacting to counted quakes (the variants are written down in docs/DECISIONS.md before the run).", "",
      "| variant | givers | gifts | coins given (TREM) | given as a share of coins minted | largest giver's share of gifts | giver bonus paid (TREM) | bonus as a share of gifts | supply and mints same as scenario 1 |", "|---|---|---|---|---|---|---|---|---|"]
base_runs = {sd: run_s1(P, sd) for sd in SEEDS}; minted1 = base_runs[SEEDS[0]].t.supply - P.s0 - base_runs[SEEDS[0]].t.div_total
for m, label in GIVE_MODES.items():
    rs = [give_runs[m]] + [run_s6(P, m, sd) for sd in SEEDS[1:]]
    for sd, x in zip(SEEDS, rs):  # hard checks G1 and G2, against scenario 1 run with the same seed (the seed sets when each bot attests)
        g = sum(x.t.given.values()); b = base_runs[sd]
        assert [d["supply"] for d in x.series] == [d["supply"] for d in b.series] and [l for l in x.t.log if l[0] == "event_counted"] == [l for l in b.t.log if l[0] == "event_counted"], f"G1 failed in {m} seed {sd}"
        assert sum(x.t.tok[a] for a in P.relief) == sum(b.t.tok[a] for a in P.relief) + g, f"G2 failed in {m} seed {sd}"
        days = x.t.calm_days  # B1: the bonus never exceeds its share of the dividends, nor the cap summed over the calm days (an aggregate bound)
        assert x.t.bonus_total <= P.giver_share_ppm * x.t.div_total // 10**6 + 1 and x.t.bonus_total <= P.giver_cap_ppm * g * days // 10**6 + days, f"B1 failed in {m} seed {sd}"
    tot = mean([sum(x.t.given.values()) for x in rs]); top = mean([max(x.t.given.values()) / sum(x.t.given.values()) if x.t.given else 0 for x in rs])
    L.append(f"| {label} | {mean([len(x.t.given) for x in rs]):.1f} | {mean([sum(1 for l in x.t.log if l[0] == 'gave') for x in rs]):.1f} | {tot/U:,.0f} | {pct(tot / minted1, 1)} | {pct(top, 1) if tot else 'n/a'} | {mean([x.t.bonus_total for x in rs])/U:,.0f} | {pct(mean([x.t.bonus_total for x in rs]) / tot, 1) if tot else 'n/a'} | yes |")
ms = give_runs["many_small"]; h0 = SMALL[0]; wh = give_runs["whale"]
def farm(givers, each, days=60):  # B2 and B3: 60 calm days, gifts made on day 0
    t = Tremor(Params(s0=P.s0, calm_ppm=P.calm_ppm, giver_share_ppm=P.giver_share_ppm, giver_cap_ppm=P.giver_cap_ppm), "ada"); now = 20000 * DAY
    for i in range(givers): t.ft_transfer("ada", f"g{i}", each, now)
    for i in range(givers): t.give(f"g{i}", each, now + 1)
    t.roll(now + days * DAY + 5); t.check_invariants()
    return t, sum(t.holding(f"g{i}") for i in range(givers))
one, h1 = farm(1, 10_000 * U); many, h50 = farm(50, 200 * U); tiny, _ = farm(1, 1 * U)
assert abs(one.bonus_total - many.bonus_total) <= 50 and abs(h1 - h50) <= 50, "B2 failed"
assert tiny.bonus_total <= 300_000, "B3 failed"
bonus_lines = [f"- Giver bonus (20% of each calm-day dividend, each coin given earns at most 0.5% a day): a single account giving 10,000 TREM earned {one.bonus_total / U:,.2f} TREM in 60 calm days; fifty accounts giving 200 TREM each earned {many.bonus_total / U:,.2f} TREM in total, so splitting gifts gains nothing (the giver accounts' holdings differ by {abs(h1 - h50)} base units). A lone giver of 1 TREM earned {tiny.bonus_total / U:.4f} TREM, so tiny gifts cannot farm the pool. A gift takes at least about 200 calm days to earn back; with many givers the shared pool, not the cap, limits it (the 10,000 TREM gift above earned about 12% in 60 days)."]
L += ["", f"Mean of {len(SEEDS)} seeds. In every variant and every seed the daily supply and every mint are identical to scenario 1, and the relief accounts end with scenario 1's balances plus exactly the gifts: giving creates nothing and moves no cap. "
      f"Quakes created {minted1/U:,.0f} TREM for the relief list in these 60 days; the gifts above are on top of that, paid by the givers alone. "
      f"A large holder giving 10% after each M7+ ends with {wh.t.tok[WHALE]/U:,.0f} TREM of {P.s0//20//U:,} and all of the gifts. These numbers follow from the assumed behaviour: they show how the mechanic responds, not how people would act.", ""] + bonus_lines + [""]
L += ["",
      "## Scenario 7: the calm-day dividend (real quakes, five honest bots, the chosen quake parameters)", "",
      "| dividend per calm day | calm days that paid (60 days plus the 3 closing days) | created for holders (TREM) | created for relief (TREM) | passive holder's loss of share (60d) | weeks with a clipped quake mint | passes every check |", "|---|---|---|---|---|---|---|"]
for cd in CJ["candidates"]:
    L.append(f"| {cd['calm_ppm']/1e4:.3f}%{' (chosen)' if cd['calm_ppm'] == CALM else ' (off)' if cd['calm_ppm'] == 0 else ''} | {cd['calm_days']} | {cd['holders_minted']/U:,.0f} | {cd['relief_minted']/U:,.0f} | {pct(cd['s1_dilution'])} | {pct(cd['s1_clipped_weeks'],1)} | {'yes' if cd['pass'] else 'no'} |")
c0 = CJ["candidates"][0]; cc = next(x for x in CJ["candidates"] if x["calm_ppm"] == CALM)
L += ["", f"The dividend is outside the weekly and monthly caps, which bound quake mints only, so relief's allowance is never spent on holders: relief received {cc['relief_minted']/U:,.0f} TREM with the chosen dividend and {c0['relief_minted']/U:,.0f} without it (slightly more, because each quake mints a share of a slightly larger supply). Holders received {cc['holders_minted']/U:,.0f} TREM. The dividend's own limit is one per day: at most {CALM/1e4:.2f}% of supply a day, about {7*CALM/1e4:.2f}% a week, on top of the quake caps. "
      f"Said plainly: the dividend makes a holder's coin count grow (by {pct(cc['holders_minted'] / P.s0)} of the starting supply here) but hardly changes their share of the supply, because almost every coin is paid the same percentage. A passive holder's loss of share over the 60 days is {pct(cc['s1_dilution'])} with it and {pct(c0['s1_dilution'])} without. Only the relief accounts are left out, and they hold a few percent of the supply, so that is all the share there is to move. Every other account is paid in proportion to its balance, including the launcher.", "",
      "## Scenario 8: the impact bar (honest bots send every real M6+ quake, green ones too)", ""]
import dataclasses
off_bar = Sim(dataclasses.replace(P, min_alert=1), SEEDS[0]); off_bar.real_events(ALL6, BOTS); off_bar.real_ids = [e for e, _, _ in ALL6]; off_bar.run()
a1 = [run_a1(P, sd) for sd in SEEDS]; s1s = [run_s1(P, sd) for sd in SEEDS]
greens = [e for e, _, _ in ALL6 if ALERT[e] < 2]
same = all([d["supply"] for d in x.series] == [d["supply"] for d in y.series] for x, y in zip(a1, s1s))
counted_green = max(sum(1 for e in greens if x.t.ev.get(e) and x.t.ev[e].status == "counted") for x in a1)
L += [f"- Quakes sent to the contract: {len(ALL6)}; below the bar (green): {len(greens)}; at or above it: {len(CAT)}.",
      f"- Green quakes that counted, in any of {len(SEEDS)} seeds: {counted_green}. Attestations the contract refused as below the bar (mean per run): {mean([x.refused.get('attest', 0) for x in a1]):.0f}.",
      f"- Supply over the 60 days identical to the run that never sends the green quakes: {'yes' if same else 'NO'}.",
      f"- With the bar, {len(CAT)} real quakes count in 60 days (about {len(CAT) / 2:.1f} a month), the weekly cap bound in {pct(s1s[0].clipped_weeks(), 1)} of weeks, and a passive holder is diluted by {pct(s1s[0].passive_dilution())}. With the bar off (`min_alert` 1, all {len(ALL6)} count) the same parameters gave {pct(off_bar.passive_dilution())} and a cap that bound in {pct(off_bar.clipped_weeks(), 1)} of weeks.",
      "- Three bad bots can still lie about the alert level as well (they attest anything); the bar stops honest mistakes and spam, not a majority of bad bots. That is the unchanged weak spot.", "",
      "## Top passing combinations", "", "| base | week | month | s1 dilution | s1 clipped weeks |", "|---|---|---|---|---|"]
rows = [r for r in csv.DictReader(open(OUT / "grid.csv")) if r["pass"] == "True"][:6]
L += [f"| {int(r['base_ppm'])/1e4:.2f}% | {int(r['week_ppm'])/1e4:.1f}% | {int(r['month_ppm'])/1e4:.1f}% | {pct(float(r['s1_dilution']))} | {pct(float(r['s1_clipped_weeks']),1)} |" for r in rows]
L += ["", "Charts: `supply.svg` (one panel per scenario). Series: `scenario*.csv` (daily supply, minted, passive holder share in ppm (balance plus unclaimed dividend), coins given so far, dividends created so far, weekly and monthly cap use)."]
(OUT / "SUMMARY.md").write_text("\n".join(L) + "\n"); print("\n".join(L))
