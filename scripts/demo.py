#!/usr/bin/env python3
"""make demo: the scripted scene (PRD section 13) on NEAR TESTNET. Prints the Python reference's expected value next to the real one.
Needs the funded accounts in .state/ (see docs/NOTES.md). Takes about 12 minutes because the demo windows are 120 s and 180 s.
`--no-reset` re-uses the deployed contract (only works once per deployment)."""
import csv, json, os, subprocess, sys, time, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reference"))
from tremor_ref import Params, Tremor, Reject
ENV = dict(os.environ, HOME=str(ROOT / ".state/home"))
P = (ROOT / ".state/parent_account").read_text().strip(); C = f"tremor.{P}"; U = 10**6
fails = 0


def sh(*a, check=True, stdout_only=False):
    r = subprocess.run(a, capture_output=True, text=True, env=ENV)
    out = r.stdout + r.stderr
    if check and ("Error:" in out or r.returncode):
        raise SystemExit("FAILED: " + " ".join(a[:6]) + "\n" + out[-600:])
    return r.stdout if stdout_only else out


def call(who, method, args=None, deposit="0 NEAR"):
    return sh("near", "contract", "call-function", "as-transaction", C, method, "json-args", json.dumps(args or {}), "prepaid-gas", "100 Tgas",
              "attached-deposit", deposit, "sign-as", f"{who}.{P}", "network-config", "testnet", "sign-with-legacy-keychain", "send")


def view(method, args=None):
    out = sh("near", "contract", "call-function", "as-read-only", C, method, "json-args", json.dumps(args or {}), "network-config", "testnet", "now", stdout_only=True)
    return json.loads(out)  # the CLI prints the bare JSON result on stdout and its labels on stderr


def check(label, expected, actual):
    global fails
    ok = expected == actual
    fails += not ok
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: expected {expected}, chain {actual}")


def trem(x): return f"{x / U:,.2f} TREM"
def wait_until(ts):
    while time.time() < ts + 2: time.sleep(2)
def acct(n): return f"{n}.{P}"


def reset():
    print("Step 0: reset: delete, recreate and redeploy the demo contract so the scene starts clean (testnet only)")
    out = subprocess.run([sys.executable, str(ROOT / "scripts/deploy.py"), "demo", "--reset"], capture_output=True, text=True, env=ENV)
    if out.returncode: raise SystemExit("reset failed:\n" + (out.stdout + out.stderr)[-600:])


if "--no-reset" not in sys.argv: reset()
print("\nStep 1: params, airdrop, bonds")
prm = view("get_params")
p = Params(s0=int(prm["s0"]), min_mag_x10=prm["min_mag_x10"], base_ppm=prm["base_ppm"], max_event_ppm=prm["max_event_ppm"], cooldown_s=prm["cooldown_s"],
           week_cap_ppm=prm["week_cap_ppm"], month_cap_ppm=prm["month_cap_ppm"], bond=int(prm["bond"]), window_s=prm["window_s"], vote_s=prm["vote_s"],
           slash_pct=prm["slash_pct"], quorum_ppm=prm["quorum_ppm"], max_age_s=prm["max_age_s"], relief=tuple(prm["relief_accounts"]))
ref = Tremor(p, acct("ada"))
for n in ("bayo", "chidi", "dayo"): call(n, "storage_deposit", {"account_id": acct(n)}, "0.00125 NEAR")
for n, v in (("bayo", 100_000), ("chidi", 50_000), ("dayo", 20_000)):
    call("ada", "ft_transfer", {"receiver_id": acct(n), "amount": str(v * U)}, "1 yoctoNEAR"); ref.ft_transfer(acct("ada"), acct(n), v * U)
for n, v in (("ada", 100_000), ("bayo", 50_000), ("chidi", 20_000), ("dayo", 10_000)):
    call(n, "deposit_bond", {"amount": str(v * U)}, "1 yoctoNEAR"); ref.deposit_bond(acct(n), v * U)
check("supply", 1_000_000 * U, int(view("ft_total_supply")))
print("  parameters on chain:", {k: v for k, v in prm.items() if k != "relief_accounts"})

print("\nStep 2: Dayo reports a real M6+ event from the committed catalog")
rows = [r for r in csv.DictReader(l for l in open(ROOT / "data/usgs_60d.csv") if not l.startswith("#"))]
catalog = {r["event_id"] for r in rows}
real = [r for r in rows if int(r["mag_x10"]) >= 60][-1]
call("dayo", "report_event", {"event_id": real["event_id"], "mag_x10": int(real["mag_x10"]), "origin_s": int(real["origin_s"])})
ev = view("get_event", {"event_id": real["event_id"]})
ref.report_event(acct("dayo"), real["event_id"], int(real["mag_x10"]), int(real["origin_s"]), ev["reported_at"])
check("status", "waiting", ev["status"]); print(f"  matches USGS catalog: {real['event_id'] in catalog} (M{int(real['mag_x10'])/10})")

print("\nStep 3: after the window, anyone calls finalize")
wait_until(ev["window_ends"]); call("bayo", "finalize", {"event_id": real["event_id"]})
now = view("get_state")["now_s"]; ref.finalize(real["event_id"], now)
check("new supply", ref.supply, int(view("ft_total_supply")))
check("each relief account", ref.tok[acct("relief1")], int(view("ft_balance_of", {"account_id": acct("relief1")})))
check("log has event_counted", True, any("event_counted" in l for l in view("get_log", {"from": 0, "limit": 20})))

print("\nStep 4: Dayo reports a made-up event, fake-001, M7.4")
n = view("get_state")["now_s"]; call("dayo", "report_event", {"event_id": "fake-001", "mag_x10": 74, "origin_s": n - 100})
ev = view("get_event", {"event_id": "fake-001"}); ref.report_event(acct("dayo"), "fake-001", 74, n - 100, ev["reported_at"])
print(f"  RED FLAG: fake-001 {'NOT' if 'fake-001' not in catalog else ''} found in the USGS catalog")

print("\nStep 5: Bayo challenges; Ada and Chidi vote not real, Dayo votes real; then finalize and claim")
call("bayo", "challenge", {"event_id": "fake-001"}); ev = view("get_event", {"event_id": "fake-001"}); ref.challenge(acct("bayo"), "fake-001", ev["challenged_at"])
for who, side, amt in (("ada", "not_real", 30_000), ("chidi", "not_real", 10_000), ("dayo", "real", 5_000)):
    call(who, "vote", {"event_id": "fake-001", "side": side, "amount": str(amt * U)}); ref.vote(acct(who), "fake-001", "real" if side == "real" else "not", amt * U, ev["challenged_at"] + 1)
wait_until(ev["vote_ends"]); call("chidi", "finalize", {"event_id": "fake-001"}); ref.finalize("fake-001", view("get_state")["now_s"])
for who in ("ada", "chidi", "dayo"): call(who, "claim_vote", {"event_id": "fake-001"}); ref.claim_vote(acct(who), "fake-001", 0)
check("event rejected", "rejected", view("get_event", {"event_id": "fake-001"})["status"])
check("supply unchanged", ref.supply, int(view("ft_total_supply")))
for who in ("ada", "bayo", "chidi", "dayo"):
    check(f"{who} bond balance", ref.bal.get(acct(who), 0), int(view("bond_balance_of", {"account_id": acct(who)})))

print("\nStep 6: Dayo reports another made-up event, fake-002; nobody challenges. The worst case, shown honestly")
n = view("get_state")["now_s"]; call("dayo", "report_event", {"event_id": "fake-002", "mag_x10": 74, "origin_s": n - 100})
ev = view("get_event", {"event_id": "fake-002"}); ref.report_event(acct("dayo"), "fake-002", 74, n - 100, ev["reported_at"])
wait_until(ev["window_ends"]); call("bayo", "finalize", {"event_id": "fake-002"})
r = ref.finalize("fake-002", view("get_state")["now_s"])
check("supply after the fake counted (caps apply)", ref.supply, int(view("ft_total_supply")))
print(f"  fake-002 minted {trem(r[0])}, clipped={r[2]}; it still shows RED (not in the USGS catalog)")
st = view("get_state"); print(f"  caps meter: weekly allowance left {trem(int(st['week_left']))}, monthly left {trem(int(st['month_left']))}")

print("\nStep 7: parameters and the access-key list")
check("parameters unchanged", prm, view("get_params"))
keys = json.loads(sh("curl", "-s", "https://rpc.testnet.near.org", "-H", "Content-Type: application/json", "-d", json.dumps(
    {"jsonrpc": "2.0", "id": 1, "method": "query", "params": {"request_type": "view_access_key_list", "finality": "final", "account_id": C}})))["result"]["keys"]
print(f"  access keys on {C}: {len(keys)} (they are deleted only as the very last step, on the human's word)")
print("\nStep 8: make verify-onchain (not built yet) then the simulation section")
print(f"\nRESULT: {'ALL CHECKS PASSED' if not fails else str(fails) + ' CHECK(S) FAILED'}")
sys.exit(1 if fails else 0)
