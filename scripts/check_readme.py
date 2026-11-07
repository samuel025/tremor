#!/usr/bin/env python3
"""make check-readme: confirms the README is current and that every claim in it maps to a command or a file.
  1. README.md equals a fresh render of README.tmpl.md from results/results.json (so no number is stale or hand-typed)
  2. every `make target` named exists in the Makefile
  3. every backticked repo path exists
  4. required sections are present
  5. no risky wording (security guarantees, value claims, casualty figures)
  6. results.json says every recorded check passed
TODO(human) markers are reported as warnings: they are for the human to fill before submission."""
import json, pathlib, re, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from make_readme import build

readme = (ROOT / "README.md").read_text() if (ROOT / "README.md").exists() else ""
fails, warns = [], []
def check(label, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {label} {detail}")
    if not ok: fails.append(label)

check("README.md is a fresh render of the template and results.json", readme == build(), "(run `make readme`)" if readme != build() else "")
makefile = (ROOT / "Makefile").read_text(); targets = set(re.findall(r"^([\w-]+):", makefile, re.M))
used = set(re.findall(r"`make ([\w-]+)", readme))
check("every `make` command in the README exists", used <= targets, f"missing: {sorted(used - targets)}" if not used <= targets else f"({len(used)} commands)")
paths = {p for p in re.findall(r"`([^`\s]+)`", readme) if re.search(r"(^|/)[\w.-]+\.(md|py|json|csv|svg|rs|toml|sh|ts)$", p) or p.endswith("/")}
paths = {p.rstrip("/") for p in paths if not p.startswith(("http", "<")) and "*" not in p and "<" not in p}
ignored = lambda p: subprocess.run(["git", "check-ignore", "-q", p], cwd=ROOT).returncode == 0  # private paths (like .state/) are deliberately not in the repo
missing = sorted(p for p in paths if not (ROOT / p).exists() and not (ROOT / p.split(" ")[0]).exists() and not ignored(p))
check("every backticked path in the README exists", not missing, f"missing: {missing}" if missing else f"({len(paths)} paths)")
required = ["## Results", "## Try it in five minutes", "## The mechanic in brief", "## How events are confirmed and what a liar can do", "## Honest limits", "## The case against Tremor", "## Two projects, one entrant", "## AI assistance, libraries, licence, data"]
check("required sections present", all(h in readme for h in required), str([h for h in required if h not in readme]))
banned = [r"\bsecure\b", r"\baudited\b", r"production[- ]ready", r"\bguarantee", r"risk[- ]free", r"will (be worth|go up|appreciate)", r"\bcasualt", r"\bfatalit", r"\binjur", r"\bdeath"]
hits = [b for b in banned if re.search(b, re.sub(r"^.*(no casualty figures).*$", "", readme, flags=re.M | re.I), re.I)]
check("no security guarantees, value claims or casualty figures", not hits, f"found: {hits}" if hits else "")
res = json.loads((ROOT / "results/results.json").read_text())
flat = {f"{k}.{n}" if k == "verify_onchain" else k: w for k, v in res.items() if isinstance(v, dict) for n, w in ([(n, w) for n, w in v.items()] if k == "verify_onchain" else [(None, v)])}
bad = [k for k, v in flat.items() if isinstance(v, dict) and (v.get("ok") is False or v.get("fail") or v.get("failed") or v.get("mismatches"))]
check("every recorded check in results/results.json passed", not bad, f"failing: {bad}" if bad else "")
for m in re.finditer(r"TODO\(human\)[^.\n]*", readme): warns.append(m.group(0))
for w in warns: print(f"WARN  {w}")
print(f"\n{'ALL CHECKS PASSED' if not fails else str(len(fails)) + ' CHECK(S) FAILED'}; {len(warns)} item(s) left for the human")
sys.exit(1 if fails else 0)
