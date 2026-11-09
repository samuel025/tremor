"""Edge cases the golden vectors do not cover: out-of-order cooldown retention and cap arithmetic at the boundary."""
import pathlib, sys, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reference"))
from tremor_ref import DAY, UNIT, Params, Tremor, mint_amount

PUBS = ("bot1", "bot2", "bot3", "bot4", "bot5")


def confirm(t, eid, mag, origin, now):
    for b in PUBS[: t.p.threshold]:
        t.attest(b, eid, mag, origin, now)


class Cooldown(unittest.TestCase):
    def test_out_of_order_counts_keep_a_nearby_old_origin(self):
        """Block times can be out of origin order and max_age_s is much longer than cooldown_s, so retaining only the
        last 16 counted origins can drop one a later event is close to. Pruning by time must keep it."""
        p = Params(s0=1_000_000 * UNIT, base_ppm=5000, cooldown_s=DAY, week_cap_ppm=1_000_000, month_cap_ppm=1_000_000,
                   min_age_s=0, max_age_s=30 * DAY, publishers=PUBS)
        t = Tremor(p, "launcher")
        now = 20000 * DAY
        origin0 = now - 6 * 3600
        confirm(t, "E0", 60, origin0, now)
        # 16 later-counted events whose origins are about 20 days away: with a fixed count of 16 they evict E0
        for i in range(16):
            confirm(t, f"far{i:02d}", 60, now - 20 * DAY + i, now)
        self.assertIn(origin0, t.recent, "the nearby origin must survive the far, later-counted events")

        supply, m7, m30 = t.supply, t.minted_last(now, 7), t.minted_last(now, 30)
        confirm(t, "Enew", 60, origin0 + 3600, now)  # one hour after E0, later than the far events in count order
        right = mint_amount(p, supply, 60, 3600, m7, m30)[0]
        wrong = mint_amount(p, supply, 60, DAY, m7, m30)[0]
        self.assertEqual(t.ev["Enew"].minted, right)
        self.assertNotEqual(right, wrong)


class Caps(unittest.TestCase):
    def p(self, **kw):
        base = dict(s0=1_000_000 * UNIT, base_ppm=5000, cooldown_s=1, week_cap_ppm=10000, month_cap_ppm=100000,
                    min_age_s=0, max_age_s=30 * DAY, publishers=PUBS)
        base.update(kw)
        return Params(**base)

    def test_exactly_at_the_weekly_cap(self):
        p = self.p()
        supply, raw, m7 = 1_000_000 * UNIT, 5_000_000_000, 5_000_000_000
        mint, got_raw, clipped = mint_amount(p, supply, 60, 1, m7, 0)
        self.assertEqual((mint, got_raw, clipped), (raw, raw, False))

    def test_one_base_unit_below_the_weekly_cap(self):
        p = self.p()
        supply, raw = 1_000_000 * UNIT, 5_000_000_000
        mint, _, clipped = mint_amount(p, supply, 60, 1, raw + 1, 0)  # leaves raw - 1 of allowance
        self.assertEqual(mint, raw - 1)
        self.assertTrue(clipped)

    def test_cap_one_unit_above_the_raw_mint(self):
        p = self.p()
        supply, raw = 1_000_000 * UNIT, 5_000_000_000
        mint, _, clipped = mint_amount(p, supply, 60, 1, raw - 1, 0)  # leaves raw + 1 of allowance
        self.assertEqual(mint, raw)
        self.assertFalse(clipped)

    def test_monthly_cap_binds_before_the_weekly_cap(self):
        p = self.p(base_ppm=10000, week_cap_ppm=1_000_000, month_cap_ppm=5000)
        mint, raw, clipped = mint_amount(p, 1_000_000 * UNIT, 60, 1, 0, 0)
        self.assertGreater(raw, 5_000_000_000)
        self.assertEqual(mint, 5_000_000_000)
        self.assertTrue(clipped)

    def test_caps_are_relative_to_supply_at_mint_time(self):
        """Documents the chosen semantics: a window allowance is a share of supply then, so it grows with earlier mints."""
        p = self.p(base_ppm=10000, week_cap_ppm=10000, month_cap_ppm=100000)
        t = Tremor(p, "launcher")
        now = 20000 * DAY
        confirm(t, "E1", 60, now - 100, now)
        self.assertEqual(t.ev["E1"].minted, 10_000_000_000)  # 1% of 1,000,000 TREM
        confirm(t, "E2", 60, now - 100_000, now)
        self.assertEqual(t.ev["E2"].minted, 100_000_000)      # 1% of the new supply, less what E1 used
        self.assertTrue(t.ev["E2"].clipped)


if __name__ == "__main__":
    unittest.main()
