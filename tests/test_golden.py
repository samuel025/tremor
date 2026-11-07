import json, pathlib, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reference"))
from tremor_ref import *
U = UNIT
load = lambda n: json.loads((ROOT / "vectors" / f"gv-{n}.json").read_text())


class GV(unittest.TestCase):
    def test_gv1(self):
        g = load(1); t = Tremor(Params(**g["params"]), "ada")
        for st in g["steps"]:
            t.ev[st["event_id"]] = Ev(st["mag_x10"], st["origin_s"], "r", st["now"])
            before = t.tok[t.p.relief[1]]
            m, raw, clipped = t._count(st["event_id"], st["now"])
            e = st["expect"]
            self.assertEqual(m, e["mint"]); self.assertEqual(t.supply, e["supply"]); self.assertEqual(clipped, e["clipped"])
            self.assertEqual(t.tok[t.p.relief[1]] - before, e["each"][1])
            if "raw" in e: self.assertEqual(raw, e["raw"])
            if "relief_balance" in e: self.assertEqual(t.tok[t.p.relief[1]], e["relief_balance"])
        # a 1% holder's share of the original supply falls by 1.4997%
        fall = 1 - (10_000 * U / t.supply) / 0.01
        self.assertAlmostEqual(round(fall * 100, 4), 1.4997, places=3)

    def run_challenge(self, g):
        p = Params(**g["params"]); t = Tremor(p, "launcher"); T = 20000 * DAY
        voters = {a.lower(): v for a, _, v in g["votes"]}
        for a, v in {**voters, "dayo": 1000 * U, "ngo": 1000 * U}.items():  # dayo reports, ngo challenges
            t.ft_transfer("launcher", a, v); t.deposit_bond(a, v)
        esc0 = t.escrow()
        t.report_event("dayo", "usq1", 60, T - 3600, T)
        t.challenge("ngo", "usq1", T + 10)
        for a, side, v in g["votes"]: t.vote(a.lower(), "usq1", side, v, T + 20)
        t.finalize("usq1", T + 20 + p.vote_s)
        for a, _, _ in g["votes"]: t.claim_vote(a.lower(), "usq1", T + 20 + p.vote_s)
        t.check_invariants()
        return t, esc0

    def test_gv2(self):
        g = load(2); e = g["expect"]; t, esc0 = self.run_challenge(g)
        self.assertEqual(t.ev["usq1"].status, "counted")
        self.assertEqual(t.ev["usq1"].pot, 0)  # paid out in sequence, no dust
        for k, v in e["final_bond"].items(): self.assertEqual(t.bal[k.lower()], v)
        self.assertEqual(t.bal["dayo"], e["reporter_bond_returned"])
        self.assertEqual(esc0, e["escrow_before"])  # contract holds 6,500 before and after
        self.assertEqual(t.escrow(), esc0)
        self.assertEqual(t.p.s0 * t.p.quorum_ppm // 10**6, e["turnout_min"])
        self.assertGreater(t.ev["usq1"].minted, 0)

    def test_gv3(self):
        g = load(3); e = g["expect"]; t, _ = self.run_challenge(g)
        self.assertEqual(t.ev["usq1"].status, "rejected"); self.assertEqual(t.ev["usq1"].minted, 0)
        self.assertEqual(t.supply, g["params"]["s0"])
        self.assertEqual(t.bal["ada"], e["final_bond"]["Ada"])
        self.assertEqual((t.bal["dayo"], t.bal["ngo"]), (e["reporter_bond_returned"], e["challenger_bond_returned"]))


if __name__ == "__main__":
    unittest.main()
