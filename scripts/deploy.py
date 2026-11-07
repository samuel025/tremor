#!/usr/bin/env python3
"""Deploys a Tremor contract to NEAR TESTNET and prepares it for visitors. Testnet only; costs test coins, never real money.
  python3 scripts/deploy.py demo [--reset]    2 min waiting window / 3 min vote, for judges who want a result at once
  python3 scripts/deploy.py live              real 24 h / 48 h windows, plus a keeper account (see scripts/keeper.py)
Accounts are sub-accounts of the parent named in .state/parent_account (demo) or .state/parent_live (live); their keys stay in .state/home.
Parameters are fixed at deploy time: there is no owner and no way to change them afterwards."""
import json, os, pathlib, subprocess, sys, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV = dict(os.environ, HOME=str(ROOT / ".state/home")); U = 10**6
WASM = ROOT / "contract/target/near/tremor.wasm"
PROFILES = {
    "demo": dict(parent_file="parent_account", contract="tremor", launcher="ada", window_s=120, vote_s=180, max_age_s=5_184_000, tap=5_000, pool=300_000, contract_near="3.2"),
    "live": dict(parent_file="parent_live", contract="tremor-live", launcher="launcher", window_s=86_400, vote_s=172_800, max_age_s=1_209_600, tap=5_000, pool=300_000, contract_near="3.3"),
}


def sh(*a, check=True):
    r = subprocess.run(a, capture_output=True, text=True, env=ENV); out = r.stdout + r.stderr
    if check and ("Error:" in out or r.returncode): raise SystemExit("FAILED: " + " ".join(a[:7]) + "\n" + out[-700:])
    return out


def exists(acct):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "query", "params": {"request_type": "view_account", "finality": "final", "account_id": acct}}).encode()
    for url in ("https://test.rpc.fastnear.com", "https://rpc.testnet.near.org"):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(url, body, {"Content-Type": "application/json"}), timeout=30)); return "error" not in r and "error" not in r.get("result", {})
        except Exception: continue
    raise SystemExit("no RPC answered")


def create(acct, parent, near):
    if exists(acct): print(f"  {acct} exists"); return
    sh("near", "account", "create-account", "fund-myself", acct, f"{near} NEAR", "autogenerate-new-keypair", "save-to-legacy-keychain", "sign-as", parent, "network-config", "testnet", "sign-with-legacy-keychain", "send"); print(f"  created {acct} ({near} NEAR)")


def call(contract, signer, method, args, deposit="0 NEAR"):
    return sh("near", "contract", "call-function", "as-transaction", contract, method, "json-args", json.dumps(args), "prepaid-gas", "100 Tgas", "attached-deposit", deposit, "sign-as", signer, "network-config", "testnet", "sign-with-legacy-keychain", "send")


def main():
    prof = sys.argv[1] if len(sys.argv) > 1 else ""
    if prof not in PROFILES: raise SystemExit(__doc__)
    P = PROFILES[prof]; parent = (ROOT / ".state" / P["parent_file"]).read_text().strip(); C = f"{P['contract']}.{parent}"; L = f"{P['launcher']}.{parent}"
    reliefs = [f"relief{i}.{parent}" for i in range(1, 6)]
    if "--reset" in sys.argv and exists(C):
        print("reset: deleting", C); sh("near", "account", "delete-account", C, "beneficiary", parent, "network-config", "testnet", "sign-with-legacy-keychain", "send")
    print("accounts:"); create(L, parent, "0.3")
    for r in reliefs: create(r, parent, "0.05")
    if prof == "live": create(f"keeper.{parent}", parent, "0.4")
    args = {"params": {"s0": str(1_000_000 * U), "min_mag_x10": 60, "base_ppm": 2500, "max_event_ppm": 15000, "cooldown_s": 86400, "week_cap_ppm": 15000, "month_cap_ppm": 50000,
                       "bond": str(1000 * U), "window_s": P["window_s"], "vote_s": P["vote_s"], "slash_pct": 20, "quorum_ppm": 2000, "max_age_s": P["max_age_s"],
                       "tap_amount": str(P["tap"] * U), "relief_accounts": None}, "relief_accounts": reliefs, "launcher": L}
    (ROOT / ".state" / f"init_args_{prof}.json").write_text(json.dumps(args))
    if prof == "demo": (ROOT / ".state/init_args.json").write_text(json.dumps(args))
    create(C, parent, P["contract_near"])
    if not exists(C) or "--reset" in sys.argv or not sh("near", "contract", "call-function", "as-read-only", C, "get_params", "json-args", "{}", "network-config", "testnet", "now", check=False).count("window_s"):
        print("deploying", WASM.name, "to", C)
        sh("near", "contract", "deploy", C, "use-file", str(WASM), "with-init-call", "new", "json-args", json.dumps(args), "prepaid-gas", "100 Tgas", "attached-deposit", "0 NEAR", "network-config", "testnet", "sign-with-legacy-keychain", "send")
    print("filling the tap pool:", P["pool"], "TREM from", L)
    call(C, L, "ft_transfer", {"receiver_id": C, "amount": str(P["pool"] * U)}, "1 yoctoNEAR")
    d = json.loads((ROOT / "deployments.json").read_text()); d[prof]["contract"] = C; (ROOT / "deployments.json").write_text(json.dumps(d, indent=2) + "\n")
    print(f"done: {prof} contract {C}; tap gives {P['tap']:,} TREM once per account from a {P['pool']:,} TREM pool")


if __name__ == "__main__": main()
