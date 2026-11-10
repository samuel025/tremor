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
# GV-5: calm_ppm = 100 (0.01% of supply per calm day). D = 86,400 s; T0 is the start of day 20000.
D = 86400
gv5 = dict(name="GV-5 calm-day dividend: a day with no counted quake pays holders, a quake day pays nothing", params=dict(P, calm_ppm=100), steps=[
    # the first transaction starts the clock; nothing is paid for earlier days
    dict(op="transfer", who="ada", to="bob", amount=100_000 * U, now=T0, expect_ok=True, expect_supply=1_000_000 * U),
    # two days later: days 20000 and 20001 were calm. 100 TREM, then 0.01% of 1,000,100 = 100.01 TREM. bob holds a tenth: 20.001
    dict(op="claim_dividend", who="bob", now=T0 + 2 * D + 10, expect_ok=True, expect_supply=1_000_200_010_000, expect_balance=100_020_001_000, expect_pot=180_009_000),
    dict(op="claim_dividend", who="ada", now=T0 + 2 * D + 10, expect_ok=True, expect_supply=1_000_200_010_000, expect_balance=900_180_009_000, expect_pot=0),
    dict(op="claim_dividend", who="ada", now=T0 + 2 * D + 11, expect_ok=False, expect_supply=1_000_200_010_000),   # nothing left to claim
    dict(op="claim_dividend", who="relief1", now=T0 + 2 * D + 12, expect_ok=False, expect_supply=1_000_200_010_000),
    # a M6.0 quake on day 20002: 0.5% of 1,000,200.01 = 5,001.00005 TREM (the dividends are outside the caps and use none of the weekly allowance)
    dict(op="quake", event_id="E1", mag_x10=60, origin_s=T0 + 2 * D + 20, now=T0 + 2 * D + 20, expect_ok=True, expect_supply=1_005_201_010_050, expect_relief=[1_000_200_010] * 5),
    # day 20003: the only finished day since is 20002, a quake day, so nothing is paid
    dict(op="claim_dividend", who="bob", now=T0 + 3 * D + 5, expect_ok=False, expect_supply=1_005_201_010_050),
    # day 20004: day 20003 was calm: 0.01% of 1,005,201.01005 = 100.520101 TREM, shared over the 1,000,200.01 TREM not held by relief accounts
    dict(op="claim_dividend", who="bob", now=T0 + 4 * D + 5, expect_ok=True, expect_supply=1_005_301_530_151, expect_balance=100_030_053_010, expect_relief=[1_000_200_010] * 5),
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
# GV-7: the giver bonus. calm_ppm 100, 20% of each dividend reserved for givers, each coin given may earn at most 0.5% a day.
# The launcher gives 10,000 TREM on day 0 (relief then holds 10,000), bob holds 100,000. Days 0 and 1 are settled on day 2.
# Day 0: dividend 100 TREM, giver pool 20 TREM = 0.002 per coin given (below the 0.005 cap), so givers take all 20 and holders get 80 over the
# 990,000 TREM not held by relief. Day 1: dividend 100.01, pool 20.002. The launcher's bonus is 40.002 TREM; bob's share is on his balance only.
gv7 = dict(name="GV-7 giver bonus: givers share a reserved part of the calm-day dividend; relief earns nothing", params=dict(P, calm_ppm=100, giver_share_ppm=200000, giver_cap_ppm=5000), steps=[
    dict(op="transfer", who="ada", to="bob", amount=100_000 * U, now=T0, expect_ok=True, expect_supply=1_000_000 * U),
    dict(op="give", who="ada", amount=10_000 * U, now=T0 + 1, expect_ok=True, expect_supply=1_000_000 * U),
    dict(op="claim_dividend", who="bob", now=T0 + 2 * D + 10, expect_ok=True, expect_supply=1_000_200_010_000, expect_balance=100_016_162_424, expect_pot=183_847_576),
    dict(op="claim_dividend", who="ada", now=T0 + 2 * D + 11, expect_ok=True, expect_supply=1_000_200_010_000, expect_balance=890_183_847_575, expect_pot=1),
])
# GV-8: the cap binds. A lone giver of 100 TREM could take the whole 20 TREM pool, but a coin may earn only 0.5% a day: 0.5 TREM. The rest of
# the dividend goes to holders. Day 0 is settled on day 1.
gv8 = dict(name="GV-8 giver bonus cap: a lone small giver earns only 0.5% of the gift a day", params=dict(P, calm_ppm=100, giver_share_ppm=200000, giver_cap_ppm=5000), steps=[
    dict(op="give", who="ada", amount=100 * U, now=T0, expect_ok=True, expect_supply=1_000_000 * U),
    dict(op="claim_dividend", who="ada", now=T0 + D + 5, expect_ok=True, expect_supply=1_000_100_000_000, expect_balance=999_999_999_999, expect_pot=1),
])
for n, g in ((1, gv1), (2, gv2), (3, gv3), (4, gv4), (5, gv5), (6, gv6), (7, gv7), (8, gv8)):
    (out / f"gv-{n}.json").write_text(json.dumps(g, indent=1) + "\n")
