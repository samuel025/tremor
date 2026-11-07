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
for n, g in ((1, gv1), (2, gv2), (3, gv3)):
    (out / f"gv-{n}.json").write_text(json.dumps(g, indent=1) + "\n")
