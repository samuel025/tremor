#!/usr/bin/env python3
"""Writes results/sim/<scenario>.csv, supply.svg and SUMMARY.md for the chosen parameters (reads chosen.json, grid.csv)."""
import csv, json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from simulate import *
OUT = ROOT / "results/sim"; ch = json.load(open(OUT / "chosen.json")); c = ch["chosen"]
P = params(c["base_ppm"], c["week_ppm"], c["month_ppm"]); DEF = params(5000); PM = params(c["base_ppm"], c["week_ppm"], c["month_ppm"], match=True)
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
     f"base share {c['base_ppm']/1e4:.2f}% at M6.0 (2x at M7, 3x at M8, max 1.5%), weekly cap {c['week_ppm']/1e4:.1f}%, monthly cap {c['month_ppm']/1e4:.1f}%. Holding promises no return: supply changes only by quake mints. Scenario 7 adds the donation match. "
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
      "| variant | givers | gifts | coins given (TREM) | given as a share of coins minted | largest giver's share of gifts | supply and mints same as scenario 1 |", "|---|---|---|---|---|---|---|"]
base_runs = {sd: run_s1(P, sd) for sd in SEEDS}; minted1 = base_runs[SEEDS[0]].t.supply - P.s0
for m, label in GIVE_MODES.items():
    rs = [give_runs[m]] + [run_s6(P, m, sd) for sd in SEEDS[1:]]
    for sd, x in zip(SEEDS, rs):  # hard checks G1 and G2, against scenario 1 run with the same seed (the seed sets when each bot attests)
        g = sum(x.t.given.values()); b = base_runs[sd]
        assert [d["supply"] for d in x.series] == [d["supply"] for d in b.series] and [l for l in x.t.log if l[0] == "event_counted"] == [l for l in b.t.log if l[0] == "event_counted"], f"G1 failed in {m} seed {sd}"
        assert sum(x.t.tok[a] for a in P.relief) == sum(b.t.tok[a] for a in P.relief) + g, f"G2 failed in {m} seed {sd}"
    tot = mean([sum(x.t.given.values()) for x in rs]); top = mean([max(x.t.given.values()) / sum(x.t.given.values()) if x.t.given else 0 for x in rs])
    L.append(f"| {label} | {mean([len(x.t.given) for x in rs]):.1f} | {mean([sum(1 for l in x.t.log if l[0] == 'gave') for x in rs]):.1f} | {tot/U:,.0f} | {pct(tot / minted1, 1)} | {pct(top, 1) if tot else 'n/a'} | yes |")
wh = give_runs["whale"]
L += ["", f"Mean of {len(SEEDS)} seeds. In every variant and every seed the daily supply and every mint are identical to scenario 1, and the relief accounts end with scenario 1's balances plus exactly the gifts: giving creates nothing and moves no cap. "
      f"Quakes created {minted1/U:,.0f} TREM for the relief list in these 60 days; the gifts above are on top of that, paid by the givers alone. "
      f"A large holder giving 10% after each M7+ ends with {wh.t.tok[WHALE]/U:,.0f} TREM of {P.s0//20//U:,} and all of the gifts. These numbers follow from the assumed behaviour: they show how the mechanic responds, not how people would act.", ""]
# ---- scenario 7: the donation match (checks M1 to M4, logged in docs/DECISIONS.md before the run)
match_runs = {m: run_s6(PM, m, 100) for m in GIVE_MODES}
L += ["", "## Scenario 7: the donation match (the same giving behaviours, with a 100,000 TREM reserve)", "",
      f"Launch values: the match adds 10% of a gift, at most {PM.match_day_ppm/1e4:.1f}% of supply a day and {PM.match_month_ppm/1e4:.0f}% over 30 days, and at most {PM.match_account_max/U:,.0f} TREM per account; the launcher puts {RESERVE/U:,.0f} TREM in the reserve first. "
      "The match goes to the relief accounts, not to the giver, and creates no coins. Mean of 20 seeds.", "",
      "| variant | coins given (TREM) | matched from the reserve (TREM) | matched as a share of gifts | reserve left at day 60 (TREM) | days the daily budget was used up | the largest giver's share of the match | supply and mints same as scenario 1 |", "|---|---|---|---|---|---|---|---|"]
for m, label in GIVE_MODES.items():
    rs = [match_runs[m]] + [run_s6(PM, m, sd) for sd in SEEDS[1:]]
    for sd, x in zip(SEEDS, rs):  # M1 and M2 against scenario 1 with the same seed; M3 is checked by the invariants on every step of every run
        b = base_runs[sd]; g = sum(x.t.given.values())
        assert [d["supply"] for d in x.series] == [d["supply"] for d in b.series] and [l for l in x.t.log if l[0] == "event_counted"] == [l for l in b.t.log if l[0] == "event_counted"], f"M1 failed in {m} seed {sd}"
        assert sum(x.t.tok[a] for a in PM.relief) == sum(b.t.tok[a] for a in PM.relief) + g + x.t.matched_total, f"M2 failed in {m} seed {sd}"
        assert x.t.reserve + x.t.matched_total == RESERVE, f"M2 (reserve) failed in {m} seed {sd}"
    tot = mean([sum(x.t.given.values()) for x in rs]); mt = mean([x.t.matched_total for x in rs])
    full = mean([sum(1 for v in x.t.mbuckets.values() if v >= PM.s0 * PM.match_day_ppm // 10**6 - 1) for x in rs])
    top = mean([max(x.t.matched_by.values()) / x.t.matched_total if x.t.matched_by else 0 for x in rs])
    L.append(f"| {label} | {tot/U:,.0f} | {mt/U:,.0f} | {pct(mt / tot, 1) if tot else 'n/a'} | {mean([x.t.reserve for x in rs])/U:,.0f} | {full:.1f} | {pct(top, 1) if mt else 'n/a'} | yes |")
def farm(accounts, each, match_max):  # M4: many accounts on one day
    t = Tremor(Params(s0=P.s0, match_ppm=PM.match_ppm, match_day_ppm=PM.match_day_ppm, match_month_ppm=PM.match_month_ppm, match_account_max=match_max), "ada"); now = 20000 * DAY
    t.fund_match("ada", RESERVE, now)
    for i in range(accounts): t.ft_transfer("ada", f"g{i}", each)
    for i in range(accounts): t.give(f"g{i}", each, now + 1)
    t.check_invariants(); return t
one, many = farm(1, 10_000 * U, PM.match_account_max), farm(50, 10_000 * U, PM.match_account_max)
assert one.matched_total == PM.match_account_max and many.matched_total == PM.s0 * PM.match_day_ppm // 10**6, "M4 failed"
L += ["", f"In every variant and every seed the daily supply and every quake mint are identical to scenario 1, the relief accounts end with scenario 1's balances plus exactly the gifts plus exactly what was matched, and the reserve plus everything matched equals what was put in (checks M1 and M2). "
      f"No day's match exceeded the daily budget and no 30-day window the monthly budget (check M3, tested on every step). "
      f"Said plainly about the limit that can be bypassed (check M4): one account giving 10,000 TREM gets {one.matched_total/U:,.0f} TREM of match (its allowance), but fifty accounts each giving 10,000 TREM on one day get {many.matched_total/U:,.0f} TREM in total: the daily budget stops them, not the per-account allowance, because the contract cannot tell that the accounts belong to one person. "
      "Whoever gives first on a day takes that day's budget.", "",
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
L += ["", "Charts: `supply.svg` (one panel per scenario). Series: `scenario*.csv` (daily supply, minted, passive holder share in ppm, coins given so far, reserve left, coins matched so far, weekly and monthly cap use)."]
(OUT / "SUMMARY.md").write_text("\n".join(L) + "\n"); print("\n".join(L))
