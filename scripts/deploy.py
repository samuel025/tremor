#!/usr/bin/env python3
"""Deploys a Tremor contract to NEAR TESTNET and prepares it for visitors. Testnet only; costs test coins, never real money.
  python3 scripts/deploy.py demo [--reset]    10 s minimum quake age and 2 minute claims, so a judge sees a result at once
  python3 scripts/deploy.py live [--reset]    real timing: 6 h minimum quake age
  --rekey    make new function-call keys for the five bots (each can only call `attest`)
Accounts are sub-accounts of the parent named in .state/parent_account (demo) or .state/parent_live (live); their keys stay in .state/home.
Parameters, the five publisher bots and the relief accounts are fixed at deploy time: there is no owner and no way to change them afterwards."""
import json, os, pathlib, re, subprocess, sys, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV = dict(os.environ, HOME=str(ROOT / ".state/home")); U = 10**6
WASM = ROOT / "contract/target/near/tremor.wasm"
PROFILES = {
    "demo": dict(parent_file="parent_account", contract="tremor", launcher="ada", min_age_s=10, max_age_s=5_184_000, claim_wait_s=120, tap=5_000, pool=300_000, contract_near="3.2", label="Demo (10 second finality, 2 minute claims)"),
    "live": dict(parent_file="parent_live", contract="tremor-live", launcher="launcher", min_age_s=21_600, max_age_s=1_209_600, claim_wait_s=43_200, tap=5_000, pool=300_000, contract_near="3.3", label="Live (real timing: quakes confirmed after 6 hours)"),
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
    reliefs = [f"relief{i}.{parent}" for i in range(1, 6)]; bots = [f"bot{i}.{parent}" for i in range(1, 6)]
    if "--reset" in sys.argv and exists(C):
        print("reset: deleting", C); sh("near", "account", "delete-account", C, "beneficiary", parent, "network-config", "testnet", "sign-with-legacy-keychain", "send")
    print("accounts:"); create(L, parent, "0.3")
    for r in reliefs: create(r, parent, "0.05")
    for b in bots: create(b, parent, "0.25")
    args = {"params": {"s0": str(1_000_000 * U), "min_mag_x10": 60, "base_ppm": 2500, "max_event_ppm": 15000, "cooldown_s": 86400, "week_cap_ppm": 15000, "month_cap_ppm": 50000,
                       "min_age_s": P["min_age_s"], "max_age_s": P["max_age_s"], "max_open": 64, "max_claims": 32, "claim_wait_s": P["claim_wait_s"], "threshold": 3,
                       "tap_amount": str(P["tap"] * U), "publisher_accounts": None, "relief_accounts": None}, "publisher_accounts": bots, "relief_accounts": reliefs, "launcher": L}
    (ROOT / ".state" / f"init_args_{prof}.json").write_text(json.dumps(args))
    create(C, parent, P["contract_near"])
    if "--reset" in sys.argv or "window" in "" or not sh("near", "contract", "call-function", "as-read-only", C, "get_params", "json-args", "{}", "network-config", "testnet", "now", check=False).count("threshold"):
        print("deploying", WASM.name, "to", C)
        sh("near", "contract", "deploy", C, "use-file", str(WASM), "with-init-call", "new", "json-args", json.dumps(args), "prepaid-gas", "100 Tgas", "attached-deposit", "0 NEAR", "network-config", "testnet", "sign-with-legacy-keychain", "send")
    print("filling the tap pool:", P["pool"], "TREM from", L)
    call(C, L, "ft_transfer", {"receiver_id": C, "amount": str(P["pool"] * U)}, "1 yoctoNEAR")
    full = ROOT / ".state" / f"bot_keys_full_{prof}.json"; simple = ROOT / ".state" / f"bot_keys_{prof}.json"
    if "--rekey" in sys.argv or not simple.exists():
        old = json.loads(full.read_text()) if full.exists() else {}
        keys = {}
        for b in bots:
            if b in old: sh("near", "account", "delete-keys", b, "public-keys", old[b]["public_key"], "network-config", "testnet", "sign-with-legacy-keychain", "send", check=False)
            out = sh("near", "account", "add-key", b, "grant-function-call-access", "--allowance", "1 NEAR", "--contract-account-id", C, "--function-names", "attest",
                     "autogenerate-new-keypair", "print-to-terminal", "network-config", "testnet", "sign-with-legacy-keychain", "send")
            keys[b] = {"public_key": re.search(r"Public Key: (ed25519:\S+)", out)[1], "private_key": re.search(r"SECRET KEYPAIR: (ed25519:\S+)", out)[1]}
        full.write_text(json.dumps(keys)); simple.write_text(json.dumps({b: k["private_key"] for b, k in keys.items()})); os.chmod(full, 0o600); os.chmod(simple, 0o600)
        print("  five bot keys saved (each can only call `attest`):", simple.name)
    d = json.loads((ROOT / "deployments.json").read_text()); d[prof].update(contract=C, bots=bots, label=P["label"], min_age_s=P["min_age_s"], claim_wait_s=P["claim_wait_s"])
    for k in ("window_s", "vote_s", "keeper"): d[prof].pop(k, None)
    (ROOT / "deployments.json").write_text(json.dumps(d, indent=2) + "\n")
    print(f"done: {prof} contract {C}; tap gives {P['tap']:,} TREM once per account from a {P['pool']:,} TREM pool")


if __name__ == "__main__": main()
