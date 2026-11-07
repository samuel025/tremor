#!/usr/bin/env python3
"""Writes vectors/gv-*.json from the hand-computed numbers in RULES.md section 6.
These numbers are typed from the spec (NOT produced by the reference) so the reference is checked against them."""
import json, pathlib
U = 10**6
P = dict(s0=1_000_000 * U)
out = pathlib.Path(__file__).resolve().parent.parent / "vectors"
T0 = 20000 * 86400  # day boundary
H = 3600
gv1 = dict(name="GV-1 minting and the split", params=P, steps=[
    dict(op="count", event_id="E1", mag_x10=60, origin_s=T0, now=T0,
         expect=dict(mint=5000 * U, supply=1_005_000 * U, each=[1000 * U] * 5, clipped=False)),
    dict(op="count", event_id="E2", mag_x10=70, origin_s=T0 + 48 * H, now=T0 + 48 * H,
         expect=dict(mint=10_050 * U, supply=1_015_050 * U, each=[2010 * U] * 5, clipped=False)),
    dict(op="count", event_id="E3", mag_x10=60, origin_s=T0 + 60 * H, now=T0 + 60 * H,
         expect=dict(raw=2_537_625_000, mint=175_750_000, supply=1_015_225_750_000,
                     each=[35_150_000] * 5, clipped=True, relief_balance=3_045_150_000)),
])
gv2 = dict(name="GV-2 a challenge the event survives", params=dict(P, s0=1_015_225_750_000), scenario="challenge",
           votes=[["Ada", "real", 3000 * U], ["Bayo", "not", 1000 * U], ["Chidi", "not", 500 * U]],
           expect=dict(outcome="counted", pot=1300 * U, final_bond={"Ada": 4300 * U, "Bayo": 800 * U, "Chidi": 400 * U},
                       reporter_bond_returned=1000 * U, escrow_before=6500 * U, escrow_after=6500 * U, turnout_min=2_030_451_500))
gv3 = dict(name="GV-3 too little turnout", params=dict(P, s0=1_015_225_750_000), scenario="challenge",
           votes=[["Ada", "real", 1000 * U]],
           expect=dict(outcome="rejected", minted=0, final_bond={"Ada": 1000 * U}, reporter_bond_returned=1000 * U,
                       challenger_bond_returned=1000 * U))
for n, g in ((1, gv1), (2, gv2), (3, gv3)):
    (out / f"gv-{n}.json").write_text(json.dumps(g, indent=1) + "\n")
