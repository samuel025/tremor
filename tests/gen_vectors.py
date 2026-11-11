#!/usr/bin/env python3
"""Writes vectors/gv-*.json from the hand-computed numbers in RULES.md section 6.
These numbers are typed from the rules (NOT produced by the reference) so the reference is checked against them."""
import json, pathlib
U = 10**6
H = 3600
T0 = 20000 * 86400  # a day boundary
P = dict(s0=1_000_000 * U, base_ppm=5000, min_age_s=0)  # GV numbers use the spec-default 0.5% base share (not the Gate A choice)
out = pathlib.Path(__file__).resolve().parent.parent / "vectors"
conf = lambda *a: [("bot%d" % i) for i in a]
gv1 = dict(name="GV-1 minting and the split (each event is confirmed by 3 bots at its own origin time)", params=P, steps=[
    dict(event_id="E1", mag_x10=60, origin_s=T0, now=T0,
         expect=dict(mint=5000 * U, supply=1_005_000 * U, each=[1000 * U] * 5, clipped=False)),
    dict(event_id="E2", mag_x10=70, origin_s=T0 + 48 * H, now=T0 + 48 * H,
         expect=dict(mint=10_050 * U, supply=1_015_050 * U, each=[2010 * U] * 5, clipped=False)),
    dict(event_id="E3", mag_x10=60, origin_s=T0 + 60 * H, now=T0 + 60 * H,
         expect=dict(raw=2_537_625_000, mint=175_750_000, supply=1_015_225_750_000, each=[35_150_000] * 5, clipped=True, relief_balance=3_045_150_000)),
])
gv2 = dict(name="GV-2 three of five publishers must agree", params=P, steps=[
    dict(op="claim", who="judge", event_id="q1", mag_x10=60, origin_s=T0, now=T0, expect_ok=True),
    dict(op="attest", who="bot1", event_id="q1", mag_x10=60, origin_s=T0, now=T0 + 5, expect_ok=True, expect_supply=1_000_000 * U),
    dict(op="attest", who="bot2", event_id="q1", mag_x10=60, origin_s=T0, now=T0 + 6, expect_ok=True, expect_supply=1_000_000 * U),
    dict(op="attest", who="nobody", event_id="q1", mag_x10=60, origin_s=T0, now=T0 + 7, expect_ok=False, expect_supply=1_000_000 * U),
    dict(op="attest", who="bot3", event_id="q1", mag_x10=60, origin_s=T0, now=T0 + 8, expect_ok=True, expect_supply=1_005_000 * U),
    dict(op="attest", who="bot4", event_id="q1", mag_x10=60, origin_s=T0, now=T0 + 9, expect_ok=False, expect_supply=1_005_000 * U),
])
gv3 = dict(name="GV-3 disagreement, too few, and a made-up claim never mint", params=P, steps=[
    dict(op="attest", who="bot1", event_id="d1", mag_x10=60, origin_s=T0, now=T0 + 5, expect_ok=True, expect_supply=1_000_000 * U),
    dict(op="attest", who="bot2", event_id="d1", mag_x10=60, origin_s=T0, now=T0 + 5, expect_ok=True, expect_supply=1_000_000 * U),
    dict(op="attest", who="bot3", event_id="d1", mag_x10=61, origin_s=T0, now=T0 + 5, expect_ok=True, expect_supply=1_000_000 * U),  # 2 for M6.0, 1 for M6.1: nothing mints
    dict(op="attest", who="bot3", event_id="d1", mag_x10=60, origin_s=T0, now=T0 + 6, expect_ok=False, expect_supply=1_000_000 * U),  # one attestation per publisher
    dict(op="attest", who="bot4", event_id="d1", mag_x10=60, origin_s=T0, now=T0 + 7, expect_ok=True, expect_supply=1_005_000 * U),  # third matching one: counts
    dict(op="claim", who="liar", event_id="fake-1", mag_x10=74, origin_s=T0, now=T0 + 10, expect_ok=True, expect_supply=1_005_000 * U),
    dict(op="attest", who="bot1", event_id="x1", mag_x10=59, origin_s=T0, now=T0 + 10, expect_ok=False, expect_supply=1_005_000 * U),  # below M6.0
])
# GV-4: 12.000003 TREM = 12,000,003 base units; a fifth is 2,400,000 with 3 left over, which goes to the first relief account.
gv4 = dict(name="GV-4 giving: a holder's own coins go to the relief list; nothing is created", params=P, steps=[
    dict(op="give", who="ada", amount=12_000_003, now=T0, expect_ok=True, expect_supply=1_000_000 * U,
         expect_relief=[2_400_003, 2_400_000, 2_400_000, 2_400_000, 2_400_000], expect_given=12_000_003),
    dict(op="give", who="ada", amount=1 * U, now=T0 + 1, expect_ok=True, expect_supply=1_000_000 * U,
         expect_relief=[2_600_003, 2_600_000, 2_600_000, 2_600_000, 2_600_000], expect_given=13_000_003),
    dict(op="give", who="stranger", amount=1, now=T0 + 2, expect_ok=False, expect_supply=1_000_000 * U),   # holds nothing
    dict(op="give", who="relief1", amount=1, now=T0 + 3, expect_ok=False, expect_supply=1_000_000 * U),    # a relief account cannot give
    dict(op="give", who="ada", amount=0, now=T0 + 4, expect_ok=False, expect_supply=1_000_000 * U),
    # a quake after the gifts mints exactly what it would have without them: 0.5% of an unchanged supply, 1,000 TREM each
    dict(op="quake", event_id="E1", mag_x10=60, origin_s=T0 + 10, now=T0 + 10, expect_ok=True, expect_supply=1_005_000 * U,
         expect_relief=[1_002_600_003, 1_002_600_000, 1_002_600_000, 1_002_600_000, 1_002_600_000], expect_given=13_000_003),
])
# GV-5: the donation match. The launcher puts 50,000 TREM in the reserve. A gift is topped up by 10%, from the reserve, never by minting.
# Budgets 0.5% of supply a day (5,000 TREM) and 2% over 30 days (20,000 TREM); one account's gifts can add at most 10,000 TREM.
D = 86400
M = dict(P, match_ppm=100_000, match_day_ppm=5000, match_month_ppm=20000, match_account_max=10_000 * U)
gv5 = dict(name="GV-5 donation match: a gift is topped up from the reserve; nothing is created", params=M, steps=[
    dict(op="fund", who="ada", amount=50_000 * U, now=T0, expect_ok=True, expect_supply=1_000_000 * U, expect_reserve=50_000 * U),
    # a gift of 1,000 TREM adds 100 TREM from the reserve: the relief list receives 1,100 TREM, 220 each
    dict(op="give", who="ada", amount=1_000 * U, now=T0 + 1, expect_ok=True, expect_supply=1_000_000 * U, expect_reserve=49_900 * U, expect_matched=100 * U,
         expect_relief=[220 * U] * 5, expect_given=1_000 * U),
    # 12.000003 TREM adds 1.2 TREM (floor of 1.2000003); 13.200003 TREM is split: a fifth is 2.64, with 3 left over for the first account
    dict(op="give", who="ada", amount=12_000_003, now=T0 + 2, expect_ok=True, expect_supply=1_000_000 * U, expect_reserve=49_898_800_000, expect_matched=1_200_000,
         expect_relief=[222_640_003] + [222_640_000] * 4, expect_given=1_012_000_003),
    dict(op="fund", who="relief1", amount=1, now=T0 + 3, expect_ok=False, expect_supply=1_000_000 * U, expect_reserve=49_898_800_000),   # a relief account cannot fund
    dict(op="give", who="stranger", amount=1, now=T0 + 4, expect_ok=False, expect_supply=1_000_000 * U, expect_reserve=49_898_800_000),   # holds nothing
    dict(op="fund", who="ada", amount=0, now=T0 + 5, expect_ok=False, expect_supply=1_000_000 * U, expect_reserve=49_898_800_000),
    # a quake mints exactly what it would have without the reserve: 0.5% of an unchanged supply, 1,000 TREM each
    dict(op="quake", event_id="E1", mag_x10=60, origin_s=T0 + 10, now=T0 + 10, expect_ok=True, expect_supply=1_005_000 * U, expect_reserve=49_898_800_000,
         expect_relief=[1_222_640_003] + [1_222_640_000] * 4, expect_given=1_012_000_003),
])
# GV-6: only quakes with expected human impact count. alert 1 green, 2 yellow, 3 orange, 4 red; the bar is yellow (2).
gv6 = dict(name="GV-6 impact bar: a green quake is refused, and three bots must agree on the alert level too", params=P, steps=[
    dict(op="attest", who="bot1", event_id="g1", mag_x10=60, origin_s=T0, alert=1, now=T0 + 5, expect_ok=False, expect_supply=1_000_000 * U),   # green: below the bar
    dict(op="claim", who="judge", event_id="g2", mag_x10=60, origin_s=T0, alert=1, now=T0 + 5, expect_ok=False, expect_supply=1_000_000 * U),   # a claim is held to the same bar
    dict(op="attest", who="bot1", event_id="g3", mag_x10=60, origin_s=T0, alert=0, now=T0 + 5, expect_ok=False, expect_supply=1_000_000 * U),   # no such level
    dict(op="attest", who="bot1", event_id="g3", mag_x10=60, origin_s=T0, alert=5, now=T0 + 5, expect_ok=False, expect_supply=1_000_000 * U),
    dict(op="attest", who="bot1", event_id="a2", mag_x10=60, origin_s=T0, alert=3, now=T0 + 5, expect_ok=True, expect_supply=1_000_000 * U),    # orange
    dict(op="attest", who="bot2", event_id="a2", mag_x10=60, origin_s=T0, alert=3, now=T0 + 6, expect_ok=True, expect_supply=1_000_000 * U),
    dict(op="attest", who="bot3", event_id="a2", mag_x10=60, origin_s=T0, alert=2, now=T0 + 7, expect_ok=True, expect_supply=1_000_000 * U),    # same quake, yellow: a different record, 2 + 1 mint nothing
    dict(op="attest", who="bot4", event_id="a2", mag_x10=60, origin_s=T0, alert=3, now=T0 + 8, expect_ok=True, expect_supply=1_005_000 * U),    # a third orange: counts, M6.0 mints 0.5% as always
    dict(op="attest", who="bot5", event_id="a2", mag_x10=60, origin_s=T0, alert=3, now=T0 + 9, expect_ok=False, expect_supply=1_005_000 * U),   # already counted
])
# GV-7: the budgets. Match rate 100% so the budgets alone decide. Reserve 100,000 TREM; budget 5,000 TREM a day and 20,000 TREM over 30 days.
# Days 0 to 4, then day 30, when day 0 has left the 30-day window.
gv7 = dict(name="GV-7 match budgets: a daily budget, a 30-day budget, and a window that slides", params=dict(P, match_ppm=1_000_000, match_day_ppm=5000, match_month_ppm=20000, match_account_max=1_000_000 * U), steps=[
    dict(op="fund", who="ada", amount=100_000 * U, now=T0, expect_ok=True, expect_supply=1_000_000 * U, expect_reserve=100_000 * U),
    dict(op="give", who="ada", amount=4_000 * U, now=T0 + 1, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=4_000 * U, expect_reserve=96_000 * U),   # day 0: 4,000 of 5,000 used
    dict(op="give", who="ada", amount=3_000 * U, now=T0 + 2, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=1_000 * U, expect_reserve=95_000 * U),   # only 1,000 left today
    dict(op="give", who="ada", amount=1 * U, now=T0 + 3, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=0, expect_reserve=95_000 * U),              # nothing left today; the gift still goes through
    dict(op="give", who="ada", amount=5_000 * U, now=T0 + D + 1, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=5_000 * U, expect_reserve=90_000 * U),       # day 1: a fresh daily budget
    dict(op="give", who="ada", amount=5_000 * U, now=T0 + 2 * D + 1, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=5_000 * U, expect_reserve=85_000 * U),
    dict(op="give", who="ada", amount=5_000 * U, now=T0 + 3 * D + 1, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=5_000 * U, expect_reserve=80_000 * U),   # 20,000 matched in 4 days
    dict(op="give", who="ada", amount=5_000 * U, now=T0 + 4 * D + 1, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=0, expect_reserve=80_000 * U),          # the 30-day budget is used
    dict(op="give", who="ada", amount=5_000 * U, now=T0 + 30 * D + 1, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=5_000 * U, expect_reserve=75_000 * U,   # day 0 has left the window: 5,000 free again
         expect_relief=[11_400_200_000] * 5, expect_given=32_001 * U),
])
# GV-8: the per-account allowance, an empty reserve, and a refill. Match rate 10%; one account's gifts can add at most 500 TREM.
gv8 = dict(name="GV-8 per-account allowance and an empty reserve", params=dict(P, match_ppm=100_000, match_day_ppm=100_000, match_month_ppm=100_000, match_account_max=500 * U), steps=[
    dict(op="fund", who="ada", amount=800 * U, now=T0, expect_ok=True, expect_supply=1_000_000 * U, expect_reserve=800 * U),
    dict(op="transfer", who="ada", to="bob", amount=10_000 * U, now=T0 + 1, expect_ok=True, expect_supply=1_000_000 * U),
    dict(op="transfer", who="ada", to="carol", amount=10_000 * U, now=T0 + 2, expect_ok=True, expect_supply=1_000_000 * U),
    dict(op="give", who="bob", amount=4_000 * U, now=T0 + 3, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=400 * U, expect_reserve=400 * U),
    dict(op="give", who="bob", amount=4_000 * U, now=T0 + 4, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=100 * U, expect_reserve=300 * U),   # bob's allowance (500) runs out
    dict(op="give", who="bob", amount=1_000 * U, now=T0 + 5, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=0, expect_reserve=300 * U),
    dict(op="give", who="carol", amount=4_000 * U, now=T0 + 6, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=300 * U, expect_reserve=0),       # carol would get 400, the reserve has 300
    dict(op="give", who="carol", amount=1_000 * U, now=T0 + 7, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=0, expect_reserve=0),
    dict(op="fund", who="bob", amount=1 * U, now=T0 + 8, expect_ok=True, expect_supply=1_000_000 * U, expect_reserve=1 * U),                               # anyone can refill it
    dict(op="give", who="carol", amount=100 * U, now=T0 + 9, expect_ok=True, expect_supply=1_000_000 * U, expect_matched=1 * U, expect_reserve=0,
         expect_relief=[2_980_200_000] * 5),
])
for n, g in ((1, gv1), (2, gv2), (3, gv3), (4, gv4), (5, gv5), (6, gv6), (7, gv7), (8, gv8)):
    (out / f"gv-{n}.json").write_text(json.dumps(g, indent=1) + "\n")
