"""Tremor Python reference. Source of truth for the math is RULES.md.
Exact integer arithmetic only; every division floors. Amounts are base units (6 decimals).
Quakes are published by five fixed bots (publishers); an event counts when `threshold` different publishers attest the same record
(event id, magnitude, origin time and USGS PAGER alert level; the alert must be at least `min_alert`)."""
from dataclasses import dataclass, field
DAY = 86400
UNIT = 10**6


class Reject(Exception):
    pass


@dataclass(frozen=True)
class Params:
    s0: int = 1_000_000 * UNIT
    min_mag_x10: int = 60
    min_alert: int = 2             # USGS PAGER alert level a quake needs: 1 green, 2 yellow, 3 orange, 4 red. Chosen: yellow
    base_ppm: int = 2500           # confirmed at Gate A (DECISIONS.md)
    max_event_ppm: int = 15000
    cooldown_s: int = DAY
    week_cap_ppm: int = 15000
    month_cap_ppm: int = 50000
    min_age_s: int = 6 * 3600      # finality delay: an attestation is refused until the event is this old
    max_age_s: int = 30 * DAY
    max_open: int = 64             # pending events started by bots
    max_claims: int = 32           # open visitor claims
    claim_wait_s: int = 12 * 3600  # how long a claim stays open
    threshold: int = 3
    match_ppm: int = 0             # donation match: a gift of n is topped up by n * match_ppm / 10^6 from the reserve (100000 = 10%); 0 disables matching
    match_day_ppm: int = 0         # most the reserve may add in one UTC day, in ppm of the supply
    match_month_ppm: int = 0       # most the reserve may add over 30 days, in ppm of the supply
    match_account_max: int = 0     # most the reserve may add because of one account's gifts, ever (base units)
    tap_amount: int = 0            # starter coins each account may take once from the pool; 0 disables the tap
    publishers: tuple = ("bot1", "bot2", "bot3", "bot4", "bot5")
    relief: tuple = ("relief1", "relief2", "relief3", "relief4", "relief5")

    def validate(self):
        if min(self.week_cap_ppm, self.month_cap_ppm, self.base_ppm, self.max_event_ppm, self.cooldown_s) <= 0:
            raise Reject("caps and shares must be nonzero")
        if len(self.relief) != 5 or len(set(self.relief)) != 5: raise Reject("need 5 distinct relief accounts")
        if len(self.publishers) != 5 or len(set(self.publishers)) != 5: raise Reject("need 5 distinct publishers")
        if not 1 <= self.threshold <= 5: raise Reject("threshold must be 1..5")
        if not 0 <= self.match_ppm <= 10**6: raise Reject("match rate must be 0..1,000,000 ppm")


def share_ppm(p: Params, mag_x10: int) -> int:
    """base at M6.0, 2x at M7.0, 3x at M8.0 (linear per 0.1), clipped to max_event_ppm."""
    return min(p.max_event_ppm, p.base_ppm * max(0, mag_x10 - 50) // 10)


def cooldown_gap(origin_s: int, recent_origins, cooldown_s: int) -> int:
    return min([cooldown_s] + [abs(origin_s - o) for o in recent_origins])


def mint_amount(p: Params, supply: int, mag_x10: int, gap: int, m7: int, m30: int):
    """Returns (mint, raw, clipped)."""
    raw = supply * share_ppm(p, mag_x10) * gap // (10**6 * p.cooldown_s)
    wk = max(0, supply * p.week_cap_ppm // 10**6 - m7)
    mo = max(0, supply * p.month_cap_ppm // 10**6 - m30)
    m = min(raw, wk, mo)
    return m, raw, m < raw


def split(mint: int):
    each = mint // 5
    return [each + mint % 5] + [each] * 4


@dataclass
class Ev:
    created_at: int
    claimer: str = None
    versions: dict = field(default_factory=dict)   # (mag_x10, origin_s, alert) -> set of publishers
    attested: set = field(default_factory=set)     # publishers that already attested this id (any version)
    status: str = "pending"                        # pending | counted
    mag_x10: int = 0
    origin_s: int = 0
    alert: int = 0
    minted: int = 0
    clipped: bool = False


class Tremor:
    def __init__(self, p: Params, launcher: str):
        p.validate()
        self.p = p
        self.tok = {launcher: p.s0}
        for a in p.relief: self.tok.setdefault(a, 0)
        self.supply = p.s0
        self.ev = {}
        self.recent = []   # counted origin times that can still lie within cooldown_s of a future valid event
        self.buckets = {}  # day -> minted
        self.tapped = set()
        self.given = {}    # account -> coins it has given to the relief list, ever
        self.given_sum = 0      # all coins ever given
        self.reserve = 0        # the donation-matching reserve: coins people put in with fund_match; they leave only as matches
        self.funded_total = 0   # all coins ever put into the reserve
        self.matched_total = 0  # all coins the reserve has added to gifts
        self.matched_by = {}    # account -> coins the reserve added because of that account's gifts
        self.mbuckets = {}      # day -> coins matched that day (the match budgets apply to these)
        self.log = []

    # ---- token
    def ft_balance_of(self, a): return self.tok.get(a, 0)

    def ft_transfer(self, f, t, n):
        if n <= 0 or self.tok.get(f, 0) < n: raise Reject("insufficient balance")
        self.tok[f] -= n; self.tok[t] = self.tok.get(t, 0) + n

    def tap(self, a, pool):
        """Once per account: move tap_amount from the pool (coins the launcher put there) to a. Mints nothing."""
        if self.p.tap_amount == 0: raise Reject("tap disabled")
        if a == pool or a in self.tapped: raise Reject("already tapped")
        if self.tok.get(pool, 0) < self.p.tap_amount: raise Reject("tap pool empty")
        self.tok[pool] -= self.p.tap_amount; self.tok[a] = self.tok.get(a, 0) + self.p.tap_amount
        self.tapped.add(a)
        self.log.append(("tapped", a, self.p.tap_amount))

    # ---- giving and matching
    def matched_last(self, now, days):
        d = now // DAY
        return sum(v for k, v in self.mbuckets.items() if d - days < k <= d)

    def match_for(self, a, n, now):
        """What the reserve would add to a gift of n from account a right now: the smallest of the rate, what is in the reserve,
        today's budget, the 30-day budget and what is left of the account's own allowance."""
        p = self.p
        if p.match_ppm == 0 or self.reserve == 0: return 0
        raw = n * p.match_ppm // 10**6
        day_left = max(0, self.supply * p.match_day_ppm // 10**6 - self.matched_last(now, 1))
        month_left = max(0, self.supply * p.match_month_ppm // 10**6 - self.matched_last(now, 30))
        acct_left = max(0, p.match_account_max - self.matched_by.get(a, 0))
        return min(raw, self.reserve, day_left, month_left, acct_left)

    def fund_match(self, a, n, now):
        """Any holder except a relief account: put n of your own coins into the matching reserve. They can only ever leave as matches
        added to gifts to the relief list: there is no way to take them back out. Mints nothing."""
        if a in self.p.relief: raise Reject("relief accounts cannot fund the reserve")
        if n <= 0 or self.tok.get(a, 0) < n: raise Reject("insufficient balance")
        self.tok[a] -= n; self.reserve += n; self.funded_total += n
        self.log.append(("funded", a, n, self.reserve, now))

    def give(self, a, n, now):
        """Any holder: send n of your own coins to the relief list, split like a mint, topped up by the match when the reserve allows.
        Mints nothing, changes no cap and gives the giver no say in anything; the contract only remembers the running total per giver.
        Returns the match that was added."""
        if a in self.p.relief: raise Reject("relief accounts cannot give")
        if n <= 0 or self.tok.get(a, 0) < n: raise Reject("insufficient balance")
        m = self.match_for(a, n, now)
        self.tok[a] -= n; self.reserve -= m
        for r, part in zip(self.p.relief, split(n + m)):
            self.tok[r] += part
        self.given[a] = self.given.get(a, 0) + n; self.given_sum += n
        if m:
            self.matched_by[a] = self.matched_by.get(a, 0) + m; self.matched_total += m
            self.mbuckets[now // DAY] = self.mbuckets.get(now // DAY, 0) + m
        self.log.append(("gave", a, n, self.given[a], m, now))
        return m

    # ---- caps
    def minted_last(self, now, days):
        d = now // DAY
        return sum(v for k, v in self.buckets.items() if d - days < k <= d)

    def state(self, now):
        m7, m30 = self.minted_last(now, 7), self.minted_last(now, 30)
        return dict(supply=self.supply, m7=m7, m30=m30,
                    week_left=max(0, self.supply * self.p.week_cap_ppm // 10**6 - m7),
                    month_left=max(0, self.supply * self.p.month_cap_ppm // 10**6 - m30))

    def _count(self, eid, mag_x10, origin_s, alert, now):
        e = self.ev[eid]
        gap = cooldown_gap(origin_s, self.recent, self.p.cooldown_s)
        m, raw, clipped = mint_amount(self.p, self.supply, mag_x10, gap, self.minted_last(now, 7), self.minted_last(now, 30))
        for a, n in zip(self.p.relief, split(m)):
            self.tok[a] += n
        self.supply += m
        self.buckets[now // DAY] = self.buckets.get(now // DAY, 0) + m
        # Keep every counted origin that can still be within cooldown_s of a valid future event. A future origin is at
        # least now - max_age_s, so an origin older than now - max_age_s - cooldown_s can never affect a later gap.
        # Pruning by time (not by count) keeps out-of-order counts correct: the last 16 counted origins is not enough.
        horizon = max(0, now - self.p.max_age_s - self.p.cooldown_s)
        self.recent = [o for o in self.recent + [origin_s] if o >= horizon]
        e.status, e.minted, e.clipped, e.mag_x10, e.origin_s, e.alert = "counted", m, clipped, mag_x10, origin_s, alert
        self.log.append(("event_counted", eid, m, clipped, now))
        return m, raw, clipped

    # ---- events
    def _check(self, eid, mag_x10, origin_s, now, fresh_ok=False, alert=2):
        p = self.p
        if mag_x10 < p.min_mag_x10 or mag_x10 > 100: raise Reject("magnitude out of range")
        if not 1 <= alert <= 4: raise Reject("alert level out of range")
        if alert < p.min_alert: raise Reject("expected impact too low")
        if origin_s > now: raise Reject("origin in the future")
        if now - origin_s > p.max_age_s: raise Reject("origin too old")
        if not fresh_ok and now - origin_s < p.min_age_s: raise Reject("too recent")
        if not eid or len(eid) > 32 or not eid.isascii(): raise Reject("bad event id")

    def _open_pending(self, now):
        """pending events started by bots that can still be attested."""
        return sum(1 for e in self.ev.values() if e.status == "pending" and e.claimer is None and now - min(o for _, o, _a in e.versions) <= self.p.max_age_s)

    def _open_claims(self, now):
        return [e for e in self.ev.values() if e.status == "pending" and e.claimer is not None and now < e.created_at + self.p.claim_wait_s]

    def submit_claim(self, a, eid, mag_x10, origin_s, now, alert=2):
        """Anyone: tell the contract about a quake. It stays pending until publishers confirm it; a made-up claim never mints."""
        self._check(eid, mag_x10, origin_s, now, fresh_ok=True, alert=alert)
        if eid in self.ev: raise Reject("event id already exists")
        open_claims = self._open_claims(now)
        if any(e.claimer == a for e in open_claims): raise Reject("you already have an open claim")
        if len(open_claims) >= self.p.max_claims: raise Reject("too many open claims")
        e = Ev(created_at=now, claimer=a); e.versions[(mag_x10, origin_s, alert)] = set()
        self.ev[eid] = e
        self.log.append(("claim_submitted", eid, a, mag_x10, origin_s, now, alert))

    def attest(self, pub, eid, mag_x10, origin_s, now, alert=2):
        """A publisher confirms a quake it found in USGS. Counts (and mints) when `threshold` different publishers attest the same record."""
        if pub not in self.p.publishers: raise Reject("not a publisher")
        self._check(eid, mag_x10, origin_s, now, alert=alert)
        e = self.ev.get(eid)
        if e is not None and e.status == "counted": raise Reject("already counted")
        if e is not None and pub in e.attested: raise Reject("already attested")
        if e is None:
            if self._open_pending(now) >= self.p.max_open: raise Reject("too many pending events")
            e = Ev(created_at=now); self.ev[eid] = e
        key = (mag_x10, origin_s, alert)
        e.versions.setdefault(key, set()).add(pub); e.attested.add(pub)
        self.log.append(("attested", eid, pub, mag_x10, origin_s, len(e.versions[key]), now, alert))
        if len(e.versions[key]) >= self.p.threshold:
            return self._count(eid, mag_x10, origin_s, alert, now)
        return None

    # ---- invariants (RULES.md)
    def check_invariants(self):
        assert self.supply == self.p.s0 + sum(e.minted for e in self.ev.values()), "supply = S0 + quake mints"
        assert self.supply == sum(self.tok.values()) + self.reserve and self.reserve >= 0, "balances + reserve = supply"
        assert all(v >= 0 for v in self.tok.values())
        assert all(v > 0 for v in self.given.values()) and not set(self.given) & set(self.p.relief), "givers"
        assert self.given_sum == sum(self.given.values()), "giver totals"
        assert self.matched_total == sum(self.matched_by.values()) == sum(self.mbuckets.values()), "match totals"
        assert self.reserve == self.funded_total - self.matched_total, "the reserve only grows by funding and shrinks by matching"
        assert all(v <= self.p.match_account_max for v in self.matched_by.values()), "per-account match allowance"
        for k in self.mbuckets:
            assert self.matched_last(k * DAY, 1) <= self.supply * self.p.match_day_ppm // 10**6, "daily match budget"
            assert self.matched_last(k * DAY, 30) <= self.supply * self.p.match_month_ppm // 10**6, "monthly match budget"
        for e in self.ev.values():
            assert e.minted == 0 or e.status == "counted"
            if e.status == "counted":
                assert len(e.versions[(e.mag_x10, e.origin_s, e.alert)]) >= self.p.threshold and e.alert >= self.p.min_alert, "counted with enough agreement and impact"
        for k in self.buckets:
            assert self.minted_last(k * DAY, 7) <= self.supply * self.p.week_cap_ppm // 10**6, "weekly cap"
            assert self.minted_last(k * DAY, 30) <= self.supply * self.p.month_cap_ppm // 10**6, "monthly cap"

    def snapshot(self):
        nz = lambda d: {k: v for k, v in sorted(d.items()) if v}
        return dict(supply=self.supply, tok=nz(self.tok), buckets=nz(self.buckets), recent=list(self.recent), tapped=sorted(self.tapped), given=nz(self.given),
                    match=[self.reserve, self.funded_total, self.matched_total, self.given_sum], matched_by=nz(self.matched_by), mbuckets=nz(self.mbuckets),
                    events={k: [e.status, e.minted, e.clipped, e.claimer or "", e.created_at,
                                [[m, o, a, sorted(s)] for (m, o, a), s in sorted(e.versions.items())]] for k, e in sorted(self.ev.items())})
