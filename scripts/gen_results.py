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
        storage_per_event_bytes=int(need(r"STORAGE per open event: (\d+) bytes", out, "storage line").group(1)),
        report_gas_tgas=int(need(r"with 63 open: (\d+) Tgas", out, "report gas").group(1)), date=now)

if "--live" in sys.argv:
    res["verify_onchain"] = {}
    for net in ("demo", "live"):
        rc, out = run(f"python3 scripts/verify_onchain.py --net {net} 2>&1")
        res["verify_onchain"][net] = dict(pass_=len(re.findall(r"^PASS", out, re.M)), fail=len(re.findall(r"^FAIL", out, re.M)), ok=rc == 0, date=now,
                                          contract=need(r"verify-onchain: (\S+) on testnet", out, "contract id").group(1),
                                          keys=int(need(r"access keys on the contract: (\d+)", out, "key count").group(1)))

demo_log = ROOT / ".state/demo2.log"
if demo_log.exists() and "--keep-demo" not in sys.argv:
    t = demo_log.read_text()
    res["demo"] = dict(pass_=len(re.findall(r"^\s+PASS", t, re.M)), fail=len(re.findall(r"^\s+FAIL", t, re.M)), ok="ALL CHECKS PASSED" in t, date=now)

ch = json.loads((ROOT / "results/sim/chosen.json").read_text()); c = ch["chosen"]; summ = (ROOT / "results/sim/SUMMARY.md").read_text()
whale = float(need(r"blocks ([\d.]+)% of real events", summ, "whale block share").group(1))
defaults = float(need(r"With the spec defaults the weekly cap binds in ([\d.]+)%", summ, "default cap-binding share").group(1))
fakes0 = float(need(r"\| 0% \| [\d.]+% \| ([\d.]+)% \|", summ, "fake dilution, nobody watching").group(1))
fakes50 = float(need(r"\| 50% \| ([\d.]+)% \|", summ, "fakes rejected at 50% watchers").group(1))
selfish = float(need(r"\| 30% \| [\d.]+% \| [\d.]+% \| ([\d.]+)% \|", summ, "selfish 30% / penalty 20% result").group(1))
catalog = [l for l in open(ROOT / "data/usgs_60d.csv") if not l.startswith("#")][1:]
res["simulation"] = dict(grid=ch["n_grid"], passing=ch["n_pass"], chosen={k: c[k] for k in ("base_ppm", "week_ppm", "month_ppm", "slash_pct", "quorum_ppm")},
    passive_dilution=c["s1_dilution"], clipped_weeks=c["s1_clipped_weeks"], fakes_rejected_half_watch=c["s3_rej_half"], real_events_count_30pct_selfish=c["s5_count_30"],
    whale_blocks_pct=whale, fakes_rejected_50_pct=fakes50, selfish30_pen20_counted_pct=selfish, default_clipped_weeks_pct=defaults, fake_extra_supply_nobody_watching_pct=fakes0,
    catalog_events=len(catalog), catalog_m6=sum(1 for l in catalog if int(l.split(",")[1]) >= 60))
OUT.write_text(json.dumps(res, indent=1) + "\n"); print(json.dumps({k: v for k, v in res.items() if k != "simulation"}, indent=1))
