#!/usr/bin/env python3
"""make readme: fills README.tmpl.md from results/results.json, the vectors and the lock files. Nothing numeric is typed by hand."""
import json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent


def lock_version(lock, crate):
    m = re.search(r'name = "%s"\nversion = "([^"]+)"' % re.escape(crate), lock.read_text()); return m[1] if m else "?"


def npm_version(lock, pkg):
    """Version of an npm package from a committed package-lock.json (so no node_modules are needed)."""
    return json.loads(lock.read_text())["packages"][f"node_modules/{pkg}"]["version"]


def build(results=None):
    R = results or json.loads((ROOT / "results/results.json").read_text())
    S = R["simulation"]; c = S["chosen"]
    pct = lambda ppm: f"{ppm / 1e4:g}"
    gv = json.loads((ROOT / "vectors/gv-1.json").read_text())
    rows = ["| Event | Magnitude | New coins (TREM) | Supply after (TREM) | Each relief account gets (TREM) | Cut by a cap |", "|---|---|---|---|---|---|"]
    for st in gv["steps"]:
        e = st["expect"]; f = lambda x: f"{x / 1e6:,.2f}".rstrip("0").rstrip(".") if x % 1_000_000 else f"{x // 1_000_000:,}"
        rows.append(f"| {st['event_id']} | M{st['mag_x10'] / 10:.1f} | {f(e['mint'])} | {f(e['supply'])} | {f(e['each'][0])} | {'yes' if e['clipped'] else 'no'} |")
    py, cf, rp, vos, sb, dm = R["python_tests"], R["conformance"], R["replay"], R["verify_onchain"], R.get("sandbox"), R.get("demo")
    res = [
        f"- `make test`: {py['passed']} Python tests pass ({py['date']}), including the three golden vectors.",
        f"- `make conformance`: the Rust contract logic and the Python reference agree on {cf['scenarios']} seeded random scenarios, {cf['steps']:,} steps, {cf['mismatches']} mismatches ({cf['date']}).",
        (f"- `make sandbox-test`: {sb['passed']} simulated-network tests pass, {sb['failed']} fail ({sb['date']}). One pending event costs about {sb['storage_per_event_bytes']} bytes of storage; `attest` burns about {sb['attest_gas_tgas']} Tgas with 63 events pending." if sb else "- `make sandbox-test`: not recorded yet."),
        f"- `make conformance-web`: the TypeScript rules engine behind the page's simulation matches the Python reference on {R['web_conformance']['scenarios']} seeded scenarios, {R['web_conformance']['steps']:,} steps, {R['web_conformance']['mismatches']} mismatches, and golden vector 1 ({R['web_conformance']['date']}).",
        f"- `make replay` (offline): {rp['pass_']} checks pass, {rp['fail']} fail ({rp['date']}).",
        *[f"- `make verify-onchain` ({net}, `{vo['contract']}`): {vo['pass_']} checks pass, {vo['fail']} fail ({vo['date']}). The contract still has {vo['keys']} access key; every key is deleted only as the very last step, on the human's word, and `python3 scripts/verify_onchain.py --net {net} --final` then demands an empty list." for net, vo in vos.items()],
        (f"- `make demo` (testnet): {dm['pass_']} of {dm['pass_'] + dm['fail']} checks matched the reference's expected values ({dm['date']})." if dm else "- `make demo`: not recorded."),
        f"- `make sim`: {S['grid']} parameter combinations were tried on {S['catalog_events']} real events ({S['catalog_m6']} of M6.0 or more); {S['passing']} passed every threshold that was written down before the run (`docs/DECISIONS.md`). Chosen: {pct(c['base_ppm'])}% base share, {pct(c['week_ppm'])}% weekly cap, {pct(c['month_ppm'])}% monthly cap. A passive holder is diluted by {S['passive_dilution'] * 100:.2f}% over the 60 real days. See `results/sim/SUMMARY.md`.",
    ]
    mapping = {
        "web.scenarios": str(R["web_conformance"]["scenarios"]), "web.steps": f"{R['web_conformance']['steps']:,}", "web.mismatches": str(R["web_conformance"]["mismatches"]), "verify.live": vos["live"]["contract"], "verify.demo": vos["demo"]["contract"], "tap": f"{R['tap_amount']:,}", "conformance.scenarios": str(cf["scenarios"]),
        "params.base": pct(c["base_ppm"]), "params.week": pct(c["week_ppm"]), "params.month": pct(c["month_ppm"]),
        "sim.bad2": f"{S['bad2_fakes_counted']:g}", "sim.bad3": f"{S['bad3_fakes_counted']:g}", "sim.bad3_extra": f"{S['bad3_extra_supply_pct']:g}",
        "sim.off2": f"{S['offline2_real_counted_pct']:g}", "sim.off3": f"{S['offline3_real_counted_pct']:g}",
        "sim.spam_fakes_counted": str(S["spam_fakes_counted"]), "sim.spam_fakes_total": f"{S['spam_fakes_total']:,}", "sim.spam_real": f"{S['spam_real_counted_pct']:g}",
        "sim.catalog_events": str(S["catalog_events"]), "sim.catalog_m6": str(S["catalog_m6"]), "sim.clipped_pct": f"{S['clipped_weeks'] * 100:.0f}", "sim.default_clipped": f"{S['default_clipped_weeks_pct']:g}",
        "libs.near_sdk": lock_version(ROOT / "contract/Cargo.lock", "near-sdk"), "libs.near_workspaces": lock_version(ROOT / "contract/sandbox/Cargo.lock", "near-workspaces"),
        "libs.vite": npm_version(ROOT / "web/package-lock.json", "vite"), "libs.wallet_selector": npm_version(ROOT / "web/package-lock.json", "@near-wallet-selector/core"),
        "libs.near_api_js": npm_version(ROOT / "bots/package-lock.json", "near-api-js"), "libs.typescript": npm_version(ROOT / "web/package-lock.json", "typescript"),
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
