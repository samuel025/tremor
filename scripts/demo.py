#!/usr/bin/env python3
"""make demo: the scripted scene on NEAR TESTNET with the five publisher bots. Prints the Python reference's expected value next to the real one.
Needs the funded accounts in .state/ (see docs/NOTES.md). Takes a couple of minutes. Stop any running `bots.mjs` first: it would confirm
the demo's quakes before the script does.  `--no-reset` re-uses the deployed contract (only works once per deployment)."""
import csv, json, os, subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reference"))
from replaylog import params_from_chain
from tremor_ref import Tremor, Reject
ENV = dict(os.environ, HOME=str(ROOT / ".state/home"))
P = (ROOT / ".state/parent_account").read_text().strip(); C = f"tremor.{P}"; U = 10**6
fails = 0


def sh(*a, check=True, stdout_only=False):
    r = subprocess.run(a, capture_output=True, text=True, env=ENV); out = r.stdout + r.stderr
    if check and ("Error:" in out or r.returncode): raise SystemExit("FAILED: " + " ".join(a[:6]) + "\n" + out[-600:])
    return r.stdout if stdout_only else out


def call(who, method, args=None, deposit="0 NEAR"):
    return sh("near", "contract", "call-function", "as-transaction", C, method, "json-args", json.dumps(args or {}), "prepaid-gas", "100 Tgas",
              "attached-deposit", deposit, "sign-as", f"{who}.{P}", "network-config", "testnet", "sign-with-legacy-keychain", "send", check=False)


def view(method, args=None):
    return json.loads(sh("near", "contract", "call-function", "as-read-only", C, method, "json-args", json.dumps(args or {}), "network-config", "testnet", "now", stdout_only=True))


def check(label, expected, actual):
    global fails
    ok = expected == actual; fails += not ok
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: expected {expected}, chain {actual}")


def refused(out): return "panicked" in out or "Error" in out
def supply(): return int(view("ft_total_supply"))
def acct(n): return f"{n}.{P}"


if "--no-reset" not in sys.argv:
    print("Step 0: reset: delete, recreate and redeploy the demo contract so the scene starts clean (testnet only)")
    out = subprocess.run([sys.executable, str(ROOT / "scripts/deploy.py"), "demo", "--reset"], capture_output=True, text=True, env=ENV)
    if out.returncode: raise SystemExit("reset failed:\n" + (out.stdout + out.stderr)[-600:])

print("\nStep 1: the parameters, the five fixed bots, the starting supply")
prm = view("get_params"); ref = Tremor(params_from_chain(prm), acct("ada"))
check("supply", 1_000_000 * U, supply()); check("publishers (fixed at launch)", 5, len(prm["publisher_accounts"])); check("bots that must agree", 3, prm["threshold"])
rows = [r for r in csv.DictReader(l for l in open(ROOT / "data/usgs_60d.csv") if not l.startswith("#"))]
LEVEL = {"green": 1, "yellow": 2, "orange": 3, "red": 4}  # USGS PAGER alert level as the rules number it
real = [r for r in rows if int(r["mag_x10"]) >= 60 and LEVEL.get(r["alert"], 0) >= prm["min_alert"]]; catalog = {r["event_id"] for r in rows}  # only quakes with enough expected impact can count
green = next(r for r in rows if int(r["mag_x10"]) >= 60 and r["alert"] == "green")
q1, q2 = real[-3], real[-5]
bots = [acct(f"bot{i}") for i in range(1, 6)]
def rec(r, dm=0): return {"event_id": r["event_id"], "mag_x10": int(r["mag_x10"]) + dm, "origin_s": int(r["origin_s"]), "alert": LEVEL[r["alert"]]}
def now(): return view("get_state")["now_s"]


def attest(i, r, dm=0):
    out = call(f"bot{i}", "attest", rec(r, dm)); t = now()
    try: ref.attest(bots[i - 1], r["event_id"], int(r["mag_x10"]) + dm, int(r["origin_s"]), t, LEVEL[r["alert"]]); ok = True
    except Reject: ok = False
    return ok, not refused(out)


print(f"\nStep 2: a visitor (Dayo) tells the contract about a real quake, {q1['event_id']} (M{int(q1['mag_x10'])/10}). A claim alone creates nothing")
call("dayo", "submit_claim", rec(q1)); ref.submit_claim(acct("dayo"), q1["event_id"], int(q1["mag_x10"]), int(q1["origin_s"]), now(), LEVEL[q1["alert"]])
e = view("get_event", {"event_id": q1["event_id"]}); check("status", "pending", e["status"]); check("attestations", 0, e["attestations"]); check("supply", 1_000_000 * U, supply())

print("\nStep 3: the bots confirm it from USGS: two are not enough, the third counts, a fourth is refused")
for i in (1, 2):
    a = attest(i, q1); check(f"bot{i} attests (accepted)", a[0], a[1]); check(f"supply after {i} of 5", ref.supply, supply())
a = attest(3, q1); check("bot3 attests (accepted)", a[0], a[1]); check("supply after the third bot", ref.supply, supply())
check("each relief account", ref.tok[acct("relief1")], int(view("ft_balance_of", {"account_id": acct("relief1")})))
a = attest(4, q1); check("bot4 attests an already counted event (refused)", a[0], a[1])
print(f"  matches USGS catalog: {q1['event_id'] in catalog}")

print("\nStep 4: someone who is not one of the five bots tries to attest: refused")
out = call("bayo", "attest", rec(q2)); check("a non-publisher is refused", True, refused(out))

print("\nStep 4b: a real quake that USGS expects to have little impact on people (alert level green) can never count")
out = call("bot1", "attest", rec(green)); check(f"bot1 attests the real but green {green['event_id']} (M{int(green['mag_x10']) / 10}): refused", True, refused(out))
out = call("bayo", "submit_claim", rec(green)); check("a claim of it is refused too", True, refused(out)); check("supply unchanged", ref.supply, supply())

print("\nStep 5: a visitor (Bayo) claims a made-up quake, fake-001. USGS has no such event, so no honest bot attests it")
call("bayo", "submit_claim", {"event_id": "fake-001", "mag_x10": 74, "origin_s": now() - 120, "alert": 2}); ref.submit_claim(acct("bayo"), "fake-001", 74, now() - 120, now(), 2)
e = view("get_event", {"event_id": "fake-001"})
print("  RED FLAG: fake-001 is NOT in the USGS catalog:", "fake-001" not in catalog); check("status", "pending", e["status"]); check("supply unchanged", ref.supply, supply())

print("\nStep 6: the bots disagree about a quake: two say M6.x, one says a tenth higher. Nothing counts until three agree")
for i, dm in ((1, 0), (2, 0), (3, 1)):
    a = attest(i, q2, dm); check(f"bot{i} attests ({'+' if dm else ''}{dm / 10} off) (accepted)", a[0], a[1])
check("no coins created by 2 + 1", ref.supply, supply())
a = attest(4, q2); check("bot4 completes three matching attestations", a[0], a[1]); check("it counts", ref.supply, supply())

print("\nStep 7: the worst case, shown honestly. If three bots were bad and attested the made-up quake, it would count, but only up to the caps")
fake = {"event_id": "fake-001", "mag_x10": 74, "origin_s": ref.ev["fake-001"].versions and list(ref.ev["fake-001"].versions)[0][1], "alert": 2}
for i in (1, 2):
    out = call(f"bot{i}", "attest", fake)
    try: ref.attest(bots[i - 1], "fake-001", 74, fake["origin_s"], now(), 2)
    except Reject: pass
    check(f"bad bot{i} attests the fake: still pending (supply unchanged)", ref.supply, supply())
out = call("bot3", "attest", fake)
try: r = ref.attest(bots[2], "fake-001", 74, fake["origin_s"], now(), 2); minted = r[0] if r else 0
except Reject: minted = 0
check("a third bad bot makes it count (capped)", ref.supply, supply()); print(f"  the fake minted {minted / U:,.2f} TREM; the weekly and monthly caps still apply")
st = view("get_state"); print(f"  caps meter: weekly allowance left {int(st['week_left']) / U:,.2f} TREM, monthly left {int(st['month_left']) / U:,.2f} TREM")

print("\nStep 8: the rules and the access-key list")
check("parameters unchanged", prm, view("get_params"))
keys = json.loads(sh("curl", "-s", "https://test.rpc.fastnear.com", "-H", "Content-Type: application/json", "-d", json.dumps(
    {"jsonrpc": "2.0", "id": 1, "method": "query", "params": {"request_type": "view_access_key_list", "finality": "final", "account_id": C}})))["result"]["keys"]
print(f"  access keys on {C}: {len(keys)} (deleted only as the very last step, on the human's word)")
print(f"\nRESULT: {'ALL CHECKS PASSED' if not fails else str(fails) + ' CHECK(S) FAILED'}")
sys.exit(1 if fails else 0)
