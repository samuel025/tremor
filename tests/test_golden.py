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

    def test_gv5(self):
        g = load(5); t = Tremor(Params(**g["params"]), "ada")
        for st in g["steps"]:
            try:
                if st["op"] == "transfer": t.ft_transfer(st["who"], st["to"], st["amount"], st["now"])
                elif st["op"] == "claim_dividend": t.claim_dividend(st["who"], st["now"])
                else: confirm(t, st["event_id"], st["mag_x10"], st["origin_s"], st["now"])
                ok = True
            except Reject: ok = False
            self.assertEqual(ok, st["expect_ok"], st); self.assertEqual(t.supply, st["expect_supply"], st)
            if "expect_balance" in st: self.assertEqual(t.tok[st["who"]], st["expect_balance"], st)
            if "expect_pot" in st: self.assertEqual(t.div_pot, st["expect_pot"], st)
            if "expect_relief" in st: self.assertEqual([t.tok[a] for a in t.p.relief], st["expect_relief"], st)
            t.check_invariants()
        self.assertEqual(t.calm_days, 3)
        self.assertEqual(t.dividend_of("ada", 20004 * DAY + 5), 900_180_009_000 * 100_499_999_995_000 // 10**18)

    def test_dividend_is_the_same_settled_late_or_on_time_and_leaves_the_caps_alone(self):
        def run(touch_daily):
            t = Tremor(Params(s0=1_000_000 * UNIT, base_ppm=5000, min_age_s=0, calm_ppm=5000, week_cap_ppm=15000, month_cap_ppm=50000), "ada")
            t0 = 20000 * DAY; t.ft_transfer("ada", "bob", 1000, t0)
            confirm(t, "E1", 60, t0 + DAY + 5, t0 + DAY + 5)
            if touch_daily:
                for d in range(2, 40): t.ft_transfer("ada", "bob", 1, t0 + d * DAY + 7)
            t.roll(t0 + 40 * DAY + 9); t.check_invariants()
            return t.supply, dict(t.buckets), t.calm_days, t.ev["E1"].minted
        late, daily = run(False), run(True)
        self.assertEqual(late, daily)
        self.assertEqual(late[2], 39)                   # days 0 to 39 are finished; day 1 had a quake
        self.assertEqual(sum(late[1].values()), late[3])   # the day buckets hold only the quake mint, so the caps see no dividend


if __name__ == "__main__":
    unittest.main()
