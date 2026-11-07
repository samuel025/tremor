#!/usr/bin/env python3
"""make readme: fills README.tmpl.md from results/results.json, the vectors and the lock files. Nothing numeric is typed by hand."""
import json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent


def lock_version(lock, crate):
    m = re.search(r'name = "%s"\nversion = "([^"]+)"' % re.escape(crate), lock.read_text()); return m[1] if m else "?"


def build(results=None):
    R = results or json.loads((ROOT / "results/results.json").read_text())
    S = R["simulation"]; c = S["chosen"]
    pct = lambda ppm: f"{ppm / 1e4:g}"
    gv = json.loads((ROOT / "vectors/gv-1.json").read_text())
    rows = ["| Event | Magnitude | New coins (TREM) | Supply after (TREM) | Each relief account gets (TREM) | Cut by a cap |", "|---|---|---|---|---|---|"]
    for st in gv["steps"]:
        e = st["expect"]; f = lambda x: f"{x / 1e6:,.2f}".rstrip("0").rstrip(".") if x % 1_000_000 else f"{x // 1_000_000:,}"
        rows.append(f"| {st['event_id']} | M{st['mag_x10'] / 10:.1f} | {f(e['mint'])} | {f(e['supply'])} | {f(e['each'][0])} | {'yes' if e['clipped'] else 'no'} |")
    py, cf, rp, vo, sb, dm = R["python_tests"], R["conformance"], R["replay"], R["verify_onchain"], R.get("sandbox"), R.get("demo")
    res = [
        f"- `make test`: {py['passed']} Python tests pass ({py['date']}), including the three golden vectors.",
        f"- `make conformance`: the Rust contract logic and the Python reference agree on {cf['scenarios']} seeded random scenarios, {cf['steps']:,} steps, {cf['mismatches']} mismatches ({cf['date']}).",
        (f"- `make sandbox-test`: {sb['passed']} simulated-network tests pass, {sb['failed']} fail ({sb['date']}). One open event costs about {sb['storage_per_event_bytes']} bytes of storage; `report_event` burns about {sb['report_gas_tgas']} Tgas with 63 events open." if sb else "- `make sandbox-test`: not recorded yet."),
        f"- `make replay` (offline): {rp['pass_']} checks pass, {rp['fail']} fail ({rp['date']}).",
        f"- `make verify-onchain` (live testnet, `{vo['contract']}`): {vo['pass_']} checks pass, {vo['fail']} fail ({vo['date']}). The contract still has {vo['keys']} access key; every key is deleted only as the very last step, on the human's word, and `python3 scripts/verify_onchain.py --final` then demands an empty list.",
        (f"- `make demo` (testnet): {dm['pass_']} of {dm['pass_'] + dm['fail']} checks matched the reference's expected values ({dm['date']})." if dm else "- `make demo`: not recorded."),
        f"- `make sim`: {S['grid']} parameter combinations were tried on {S['catalog_events']} real events ({S['catalog_m6']} of M6.0 or more); {S['passing']} passed every threshold that was written down before the run (`docs/DECISIONS.md`). Chosen: {pct(c['base_ppm'])}% base share, {pct(c['week_ppm'])}% weekly cap, {pct(c['month_ppm'])}% monthly cap, {c['slash_pct']}% penalty, {pct(c['quorum_ppm'])}% minimum turnout. A passive holder is diluted by {S['passive_dilution'] * 100:.2f}% over the 60 real days. See `results/sim/SUMMARY.md`.",
    ]
    mapping = {
        "verify.contract": vo["contract"], "conformance.scenarios": str(cf["scenarios"]), "bond": "1,000",
        "params.base": pct(c["base_ppm"]), "params.week": pct(c["week_ppm"]), "params.month": pct(c["month_ppm"]), "params.slash": str(c["slash_pct"]), "params.quorum": pct(c["quorum_ppm"]),
        "sim.fake_extra": f"{S['fake_extra_supply_nobody_watching_pct']:g}", "sim.fakes_rejected": f"{S['fakes_rejected_50_pct']:.0f}", "sim.whale": f"{S['whale_blocks_pct']:.0f}",
        "sim.selfish": f"{S['selfish30_pen20_counted_pct']:.0f}", "sim.catalog_events": str(S["catalog_events"]), "sim.catalog_m6": str(S["catalog_m6"]),
        "sim.clipped_pct": f"{S['clipped_weeks'] * 100:.0f}", "sim.default_clipped": f"{S['default_clipped_weeks_pct']:g}",
        "libs.near_sdk": lock_version(ROOT / "contract/Cargo.lock", "near-sdk"), "libs.near_workspaces": lock_version(ROOT / "contract/sandbox/Cargo.lock", "near-workspaces"),
        "libs.vite": json.loads((ROOT / "web/node_modules/vite/package.json").read_text())["version"], "libs.typescript": json.loads((ROOT / "web/node_modules/typescript/package.json").read_text())["version"],
        "RESULTS": "\n".join(res), "GV1": "\n".join(rows),
    }
    text = (ROOT / "README.tmpl.md").read_text()
    def sub(m):
        k = m.group(1)
        if k not in mapping: sys.exit(f"README template uses unknown placeholder {{{{{k}}}}}")
        return mapping[k]
    return re.sub(r"\{\{([\w.]+)\}\}", sub, text)


if __name__ == "__main__":
    (ROOT / "README.md").write_text(build()); print("README.md written")
