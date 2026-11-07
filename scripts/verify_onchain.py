#!/usr/bin/env python3
"""make verify-onchain: reads the live testnet contract and checks it against the Python reference. Testnet only.
  --save FILE   also write the fixture used by `make replay`
  --final       also require an EMPTY access-key list (run after the human deletes the keys)
  --contract ID check another contract id (default: the one in .state)"""
import argparse, base64, json, pathlib, sys, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reference"))
from replaylog import replay

ap = argparse.ArgumentParser(); ap.add_argument("--save"); ap.add_argument("--final", action="store_true"); ap.add_argument("--contract"); ap.add_argument("--net", choices=["demo", "live"], help="read the contract from deployments.json")
a = ap.parse_args()
RPCS = ["https://test.rpc.fastnear.com", "https://rpc.testnet.near.org"]  # the official one rate-limits
C = a.contract or (json.loads((ROOT / "deployments.json").read_text())[a.net]["contract"] if a.net else f"tremor.{(ROOT / '.state/parent_account').read_text().strip()}")
fails = 0
ALLOWED = {"bond_balance_of", "challenge", "claim_vote", "contract_source_metadata", "deposit_bond", "finalize", "ft_balance_of", "ft_metadata",
           "ft_resolve_transfer", "ft_total_supply", "ft_transfer", "ft_transfer_call", "get_event", "get_log", "get_params", "get_state",
           "list_events", "memory", "new", "report_event", "storage_balance_bounds", "storage_balance_of", "storage_deposit", "vote", "withdraw_bond", "tap", "has_tapped"}

def rpc(method, params):
    for url in RPCS:
        try:
            req = urllib.request.Request(url, json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(), {"Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=30))
        except Exception: continue
        if "error" in r or "error" in r.get("result", {}): sys.exit(f"RPC error: {r}")
        return r["result"]
    sys.exit("no RPC endpoint answered")

def view(m, args=None):
    r = rpc("query", {"request_type": "call_function", "finality": "final", "account_id": C, "method_name": m,
                      "args_base64": base64.b64encode(json.dumps(args or {}).encode()).decode()})
    return json.loads(bytes(r["result"]))

def check(label, ok, detail=""):
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {label} {detail}")

print(f"verify-onchain: {C} on testnet")
prm = view("get_params"); st = view("get_state")
log = []
while len(log) < st["log_len"]: log += view("get_log", {"from": len(log), "limit": 100})
events = []
while True:
    page = view("list_events", {"from": len(events), "limit": 100}); events += page
    if len(page) < 100: break
ref, bad = replay(prm, log)
check("log fully read", len(log) == st["log_len"], f"({len(log)} lines)")
check("replaying the on-chain log reproduces every mint, clipped flag, outcome and claim payout", not bad, "; ".join(bad[:3]))
check("total supply equals the reference", int(view("ft_total_supply")) == ref.supply, f"({ref.supply})")
check("supply = initial supply + all mints", ref.supply == int(prm["s0"]) + sum(int(e["minted"]) for e in events))
relief = {}
for r in prm["relief_accounts"]:
    relief[r] = view("ft_balance_of", {"account_id": r}); check(f"relief balance {r.split('.')[0]}", int(relief[r]) == ref.tok.get(r, 0), f"({int(relief[r]) / 1e6:,.2f} TREM)")
s = ref.state(st["now_s"])
check("weekly and monthly allowance left match the reference", (s["week_left"], s["month_left"]) == (int(st["week_left"]), int(st["month_left"])))
for e in events:
    r = ref.ev.get(e["event_id"]); check(f"event {e['event_id']} ({e['status']})", bool(r) and r.status == e["status"] and r.minted == int(e["minted"]))
check("parameters are internally valid (nonzero caps, 5 distinct relief accounts, slash <= 100)", len(set(prm["relief_accounts"])) == 5 and prm["week_cap_ppm"] > 0 and prm["month_cap_ppm"] > 0 and prm["slash_pct"] <= 100)
code = base64.b64decode(rpc("query", {"request_type": "view_code", "finality": "final", "account_id": C})["code_base64"])
def leb(b, i):
    r = sh = 0
    while True:
        x = b[i]; i += 1; r |= (x & 127) << sh; sh += 7
        if x < 128: return r, i
i = 8; exports = []
while i < len(code):
    sid = code[i]; i += 1; ln, i = leb(code, i)
    if sid == 7:
        j = i; n, j = leb(code, j)
        for _ in range(n):
            l, j = leb(code, j); exports.append(code[j:j + l].decode()); j += l + 1; _, j = leb(code, j)
        break
    i += ln
check("deployed code exports only the intended methods (no owner, admin, upgrade, set_* or free-mint method)", set(exports) <= ALLOWED and exports, f"(extra: {sorted(set(exports) - ALLOWED)})")
keys = rpc("query", {"request_type": "view_access_key_list", "finality": "final", "account_id": C})["keys"]
if a.final: check("access-key list is EMPTY", len(keys) == 0, f"({len(keys)} keys)")
else: print(f"INFO  access keys on the contract: {len(keys)} (they are deleted only as the very last step; use --final after that)")
if a.save:
    fx = dict(contract=C, params=prm, state=st, supply=str(view("ft_total_supply")), log=log, events=events, relief_balances=relief)
    pathlib.Path(a.save).write_text(json.dumps(fx, indent=1) + "\n"); print(f"saved fixture {a.save}")
print(f"\n{'ALL CHECKS PASSED' if not fails else str(fails) + ' CHECK(S) FAILED'}"); sys.exit(1 if fails else 0)
