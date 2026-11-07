#!/usr/bin/env python3
"""make results: runs the checks and records what they report in results/results.json (the README is generated from this file).
  --sandbox   also run the near-workspaces suite (slow, about 3 minutes); without it the last recorded sandbox numbers are kept
  --live      also run `verify-onchain` against testnet (needs network)"""
import datetime, json, pathlib, re, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "results/results.json"
res = json.loads(OUT.read_text()) if OUT.exists() else {}

def run(cmd, cwd=ROOT, timeout=1500):
    r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout + r.stderr

def need(rx, text, what):
    m = re.search(rx, text)
    if not m: sys.exit(f"could not find {what} in output:\n{text[-800:]}")
    return m

now = datetime.date.today().isoformat()
rc, out = run("python3 -m unittest discover -s tests 2>&1")
res["python_tests"] = dict(passed=int(need(r"Ran (\d+) tests", out, "python test count").group(1)), ok=rc == 0 and "OK" in out, date=now)

rc, out = run("cd contract && cargo test --test conformance -- --nocapture 2>&1")
m = need(r"conformance: (\d+) scenarios, (\d+) steps, (\d+) mismatches", out, "conformance line")
res["conformance"] = dict(scenarios=int(m[1]), steps=int(m[2]), mismatches=int(m[3]), tests_passed=int(need(r"test result: ok\. (\d+) passed", out, "rust test result").group(1)), ok=rc == 0, date=now)

rc, out = run("python3 scripts/replay.py 2>&1")
res["replay"] = dict(pass_=len(re.findall(r"^PASS", out, re.M)), fail=len(re.findall(r"^FAIL", out, re.M)), ok=rc == 0, date=now)

if "--sandbox" in sys.argv:
    rc, out = run("cd contract && cargo near build non-reproducible-wasm --no-abi 2>&1 | tail -1; cd sandbox && cargo test -- --nocapture --test-threads=1 2>&1", timeout=2400)
    m = need(r"test result: (\w+)\. (\d+) passed; (\d+) failed", out, "sandbox result")
    res["sandbox"] = dict(passed=int(m[2]), failed=int(m[3]), ok=m[1] == "ok",
        storage_per_event_bytes=int(need(r"STORAGE per pending event: (\d+) bytes", out, "storage line").group(1)),
        attest_gas_tgas=int(need(r"with 63 pending: (\d+) Tgas", out, "attest gas").group(1)), date=now)

if "--live" in sys.argv:
    res["verify_onchain"] = {}
    for net in ("demo", "live"):
        rc, out = run(f"python3 scripts/verify_onchain.py --net {net} 2>&1")
        res["verify_onchain"][net] = dict(pass_=len(re.findall(r"^PASS", out, re.M)), fail=len(re.findall(r"^FAIL", out, re.M)), ok=rc == 0, date=now,
                                          contract=need(r"verify-onchain: (\S+) on testnet", out, "contract id").group(1),
                                          keys=int(need(r"access keys on the contract: (\d+)", out, "key count").group(1)))

logs = sorted((ROOT / ".state").glob("demo[0-9]*.log"), key=lambda f: f.stat().st_mtime)
demo_log = logs[-1] if logs else ROOT / ".state/none.log"
if demo_log.exists() and "--keep-demo" not in sys.argv:
    t = demo_log.read_text()
    res["demo"] = dict(pass_=len(re.findall(r"^\s+PASS", t, re.M)), fail=len(re.findall(r"^\s+FAIL", t, re.M)), ok="ALL CHECKS PASSED" in t, date=now)

if "--live" in sys.argv:  # starter coins per tap, read from the deployed contract's parameters
    import base64, urllib.request
    live = json.loads((ROOT / "deployments.json").read_text())["live"]["contract"]
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "query", "params": {"request_type": "call_function", "finality": "final", "account_id": live, "method_name": "get_params", "args_base64": base64.b64encode(b"{}").decode()}}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request("https://test.rpc.fastnear.com", body, {"Content-Type": "application/json"}), timeout=30))
    res["tap_amount"] = int(json.loads(bytes(r["result"]["result"]))["tap_amount"]) // 10**6

ch = json.loads((ROOT / "results/sim/chosen.json").read_text()); c = ch["chosen"]; summ = (ROOT / "results/sim/SUMMARY.md").read_text()
def section(name):  # the text of one scenario in SUMMARY.md
    m = re.search(rf"## {name}.*?(?=\n## |\Z)", summ, re.S)
    if not m: sys.exit(f"SUMMARY.md has no section {name}")
    return m.group(0)
defaults = float(need(r"With the spec defaults the weekly cap binds in ([\d.]+)% of weeks", summ, "default cap-binding share").group(1))
s3, s4, s5 = section("Scenario 3"), section("Scenario 4"), section("Scenario 5")
bad2 = float(need(r"\| 2 \| ([\d.]+) \|", s3, "fakes counted with 2 bad bots").group(1))
bad3 = need(r"\| 3 \| ([\d.]+) \| ([\d.]+)% \|", s3, "fakes counted with 3 bad bots")
off2 = float(need(r"\| 2 \| ([\d.]+)% \|", s4, "real events counted with 2 bots offline").group(1))
off3 = float(need(r"\| 3 \| ([\d.]+)% \|", s4, "real events counted with 3 bots offline").group(1))
spam = need(r"Real events that count: ([\d.]+)%\. Made-up claims that count: (\d+) of (\d+)", s5, "claim spam result"); spam2 = need(r"Most claims open at once: (\d+) against a limit of (\d+); the contract refused (\d+) claims", s5, "claim spam limits")
catalog = [l for l in open(ROOT / "data/usgs_60d.csv") if not l.startswith("#")][1:]
res["simulation"] = dict(grid=ch["n_grid"], passing=ch["n_pass"], chosen={k: c[k] for k in ("base_ppm", "week_ppm", "month_ppm")},
    passive_dilution=c["s1_dilution"], clipped_weeks=c["s1_clipped_weeks"], default_clipped_weeks_pct=defaults,
    bad2_fakes_counted=bad2, bad3_fakes_counted=float(bad3[1]), bad3_extra_supply_pct=float(bad3[2]), offline2_real_counted_pct=off2, offline3_real_counted_pct=off3,
    spam_real_counted_pct=float(spam[1]), spam_fakes_counted=int(spam[2]), spam_fakes_total=int(spam[3]), spam_max_open=int(spam2[1]), spam_limit=int(spam2[2]), spam_refused=int(spam2[3]),
    catalog_events=len(catalog), catalog_m6=sum(1 for l in catalog if int(l.split(",")[1]) >= 60))
OUT.write_text(json.dumps(res, indent=1) + "\n"); print(json.dumps({k: v for k, v in res.items() if k != "simulation"}, indent=1))
