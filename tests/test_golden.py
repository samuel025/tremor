import json, pathlib, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reference"))
from tremor_ref import *
load = lambda n: json.loads((ROOT / "vectors" / f"gv-{n}.json").read_text())


def confirm(t, eid, mag, origin, now, bots=("bot1", "bot2", "bot3")):
    r = None
    for b in bots: r = t.attest(b, eid, mag, origin, now)
    return r


class GV(unittest.TestCase):
    def test_gv1(self):
        g = load(1); t = Tremor(Params(**g["params"]), "ada")
        for st in g["steps"]:
            before = t.tok[t.p.relief[1]]
            m, raw, clipped = confirm(t, st["event_id"], st["mag_x10"], st["origin_s"], st["now"])
            e = st["expect"]
            self.assertEqual(m, e["mint"]); self.assertEqual(t.supply, e["supply"]); self.assertEqual(clipped, e["clipped"])
            self.assertEqual(t.tok[t.p.relief[1]] - before, e["each"][1])
            if "raw" in e: self.assertEqual(raw, e["raw"])
            if "relief_balance" in e: self.assertEqual(t.tok[t.p.relief[1]], e["relief_balance"])
            t.check_invariants()
        # a 1% holder's share of the original supply falls by 1.4997%
        fall = 1 - (10_000 * UNIT / t.supply) / 0.01
        self.assertAlmostEqual(round(fall * 100, 4), 1.4997, places=3)

    def run_steps(self, n):
        g = load(n); t = Tremor(Params(**g["params"]), "ada")
        for st in g["steps"]:
            try:
                if st.get("op") == "claim": t.submit_claim(st["who"], st["event_id"], st["mag_x10"], st["origin_s"], st["now"]); ok = True
                else: t.attest(st["who"], st["event_id"], st["mag_x10"], st["origin_s"], st["now"]); ok = True
            except Reject: ok = False
            self.assertEqual(ok, st["expect_ok"], st)
            if "expect_supply" in st: self.assertEqual(t.supply, st["expect_supply"], st)
            t.check_invariants()
        return t

    def test_gv2(self):
        t = self.run_steps(2)
        self.assertEqual(t.ev["q1"].status, "counted")
        self.assertEqual([t.tok[a] for a in t.p.relief], [1000 * UNIT] * 5)

    def test_gv3(self):
        t = self.run_steps(3)
        self.assertEqual(t.ev["d1"].status, "counted"); self.assertEqual((t.ev["d1"].mag_x10), 60)
        self.assertEqual(t.ev["fake-1"].status, "pending"); self.assertEqual(t.ev["fake-1"].minted, 0)


if __name__ == "__main__":
    unittest.main()
