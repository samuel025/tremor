#!/usr/bin/env python3
"""make replay: offline. Recomputes supply, mints, caps and outcomes from a committed fixture of the testnet log and compares
with what the chain reported when the fixture was saved. Exits non-zero on any failed check."""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reference"))
from replaylog import replay

fails = 0
def check(label, ok, detail=""):
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {label} {detail}")

paths = [pathlib.Path(a) for a in sys.argv[1:]] or sorted((ROOT / "fixtures").glob("testnet-*.json"))
if not paths: sys.exit("no fixtures: run `python3 scripts/verify_onchain.py --save fixtures/testnet-demo.json` first")
for path in paths:
    fx = json.loads(path.read_text()); print(f"== {path.name} ({len(fx['log'])} log lines)")
    ref, bad = replay(fx["params"], fx["log"], fx["state"]["now_s"])
    check("every log step replays and agrees (mints, clipped flags, supply, outcomes, claim payouts)", not bad, "; ".join(bad[:3]))
    check("supply", ref.supply == int(fx["supply"]), f"reference {ref.supply} chain {fx['supply']}")
    for acct, bal in fx["relief_balances"].items(): check(f"relief balance {acct.split('.')[0]}", ref.tok.get(acct, 0) == int(bal), f"reference {ref.tok.get(acct, 0)} chain {bal}")
    st = ref.state(fx["state"]["now_s"])
    check("weekly allowance left", st["week_left"] == int(fx["state"]["week_left"]), f"reference {st['week_left']} chain {fx['state']['week_left']}")
    check("monthly allowance left", st["month_left"] == int(fx["state"]["month_left"]), f"reference {st['month_left']} chain {fx['state']['month_left']}")
    check("minted last 7 / 30 days", (st["m7"], st["m30"]) == (int(fx["state"]["minted_7d"]), int(fx["state"]["minted_30d"])))
    for ev in fx["events"]:
        r = ref.ev.get(ev["event_id"]); check(f"event {ev['event_id']} status", bool(r) and r.status == ev["status"] and r.minted == int(ev["minted"]), f"({ev['status']})")
    check("supply equals initial supply plus every mint", ref.supply == ref.p.s0 + sum(e.minted for e in ref.ev.values()))
print(f"\n{'ALL CHECKS PASSED' if not fails else str(fails) + ' CHECK(S) FAILED'}"); sys.exit(1 if fails else 0)
