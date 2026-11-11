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
                if st.get("op") == "claim": t.submit_claim(st["who"], st["event_id"], st["mag_x10"], st["origin_s"], st["now"], st.get("alert", 2)); ok = True
                else: t.attest(st["who"], st["event_id"], st["mag_x10"], st["origin_s"], st["now"], st.get("alert", 2)); ok = True
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

    def run_match(self, n):
        """Steps with funding, giving, transfers and quakes; every expectation is a number typed in tests/gen_vectors.py from RULES.md."""
        g = load(n); t = Tremor(Params(**g["params"]), "ada")
        for st in g["steps"]:
            before = t.matched_total
            try:
                if st["op"] == "transfer": t.ft_transfer(st["who"], st["to"], st["amount"])
                elif st["op"] == "give": t.give(st["who"], st["amount"], st["now"])
                elif st["op"] == "fund": t.fund_match(st["who"], st["amount"], st["now"])
                else: confirm(t, st["event_id"], st["mag_x10"], st["origin_s"], st["now"])
                ok = True
            except Reject: ok = False
            self.assertEqual(ok, st["expect_ok"], st); self.assertEqual(t.supply, st["expect_supply"], st)
            if "expect_reserve" in st: self.assertEqual(t.reserve, st["expect_reserve"], st)
            if "expect_matched" in st: self.assertEqual(t.matched_total - before, st["expect_matched"], st)
            if "expect_relief" in st: self.assertEqual([t.tok[a] for a in t.p.relief], st["expect_relief"], st)
            if "expect_given" in st: self.assertEqual(t.given["ada"], st["expect_given"], st)
            t.check_invariants()
        return t

    def test_gv5(self):
        t = self.run_match(5)
        self.assertEqual((t.matched_total, t.funded_total, t.given_sum), (101_200_000, 50_000 * UNIT, 1_012_000_003))

    def test_gv7(self):
        t = self.run_match(7)
        self.assertEqual((t.matched_total, t.reserve), (25_000 * UNIT, 75_000 * UNIT))

    def test_gv8(self):
        t = self.run_match(8)
        self.assertEqual((t.matched_by["bob"], t.matched_by["carol"], t.matched_total, t.funded_total), (500 * UNIT, 301 * UNIT, 801 * UNIT, 801 * UNIT))

    def test_the_match_never_creates_coins_and_cannot_be_farmed_beyond_the_budgets(self):
        """Fifty accounts each giving the most one account may have matched add what one account would, plus nothing more than the
        daily and monthly budgets; the supply never moves."""
        def run(accounts, each):
            t = Tremor(Params(s0=1_000_000 * UNIT, match_ppm=100_000, match_day_ppm=5000, match_month_ppm=20000, match_account_max=1000 * UNIT), "ada"); now = 20000 * DAY
            t.fund_match("ada", 100_000 * UNIT, now)
            for i in range(accounts): t.ft_transfer("ada", f"g{i}", each)
            for i in range(accounts): t.give(f"g{i}", each, now + 1)
            t.check_invariants()
            return t
        one, many = run(1, 10_000 * UNIT), run(50, 10_000 * UNIT)
        self.assertEqual(one.matched_total, 1000 * UNIT)            # one account: its allowance
        self.assertEqual(many.matched_total, 5000 * UNIT)           # fifty accounts: the daily budget (0.5% of supply), not 50 allowances
        self.assertEqual((one.supply, many.supply), (1_000_000 * UNIT, 1_000_000 * UNIT))

    def test_gv6(self):
        t = self.run_steps(6)
        self.assertEqual((t.ev["a2"].status, t.ev["a2"].alert), ("counted", 3))
        self.assertNotIn("g1", t.ev); self.assertNotIn("g2", t.ev); self.assertNotIn("g3", t.ev)   # refused records leave no trace

    def test_gv4(self):
        g = load(4); t = Tremor(Params(**g["params"]), "ada")
        for st in g["steps"]:
            try:
                if st["op"] == "give": t.give(st["who"], st["amount"], st["now"])
                else: confirm(t, st["event_id"], st["mag_x10"], st["origin_s"], st["now"])
                ok = True
            except Reject: ok = False
            self.assertEqual(ok, st["expect_ok"], st); self.assertEqual(t.supply, st["expect_supply"], st)
            if "expect_relief" in st: self.assertEqual([t.tok[a] for a in t.p.relief], st["expect_relief"], st)
            if "expect_given" in st: self.assertEqual(t.given["ada"], st["expect_given"], st)
            t.check_invariants()
        self.assertEqual(list(t.given), ["ada"])
        self.assertEqual(t.tok["ada"], 1_000_000 * UNIT - 13_000_003)


if __name__ == "__main__":
    unittest.main()
