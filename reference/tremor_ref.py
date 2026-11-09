"""Tremor Python reference. Source of truth for the math is RULES.md.
Exact integer arithmetic only; every division floors. Amounts are base units (6 decimals).
Quakes are published by five fixed bots (publishers); an event counts when `threshold` different publishers attest the same record."""
from dataclasses import dataclass, field
DAY = 86400
UNIT = 10**6


class Reject(Exception):
    pass


@dataclass(frozen=True)
class Params:
    s0: int = 1_000_000 * UNIT
    min_mag_x10: int = 60
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
    tap_amount: int = 0            # starter coins each account may take once from the pool; 0 disables the tap
    publishers: tuple = ("bot1", "bot2", "bot3", "bot4", "bot5")
    relief: tuple = ("relief1", "relief2", "relief3", "relief4", "relief5")

    def validate(self):
        if min(self.week_cap_ppm, self.month_cap_ppm, self.base_ppm, self.max_event_ppm, self.cooldown_s) <= 0:
            raise Reject("caps and shares must be nonzero")
        if len(self.relief) != 5 or len(set(self.relief)) != 5: raise Reject("need 5 distinct relief accounts")
        if len(self.publishers) != 5 or len(set(self.publishers)) != 5: raise Reject("need 5 distinct publishers")
        if not 1 <= self.threshold <= 5: raise Reject("threshold must be 1..5")


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
    versions: dict = field(default_factory=dict)   # (mag_x10, origin_s) -> set of publishers
    attested: set = field(default_factory=set)     # publishers that already attested this id (any version)
    status: str = "pending"                        # pending | counted
    mag_x10: int = 0
    origin_s: int = 0
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

    # ---- caps
    def minted_last(self, now, days):
        d = now // DAY
        return sum(v for k, v in self.buckets.items() if d - days < k <= d)

    def state(self, now):
        m7, m30 = self.minted_last(now, 7), self.minted_last(now, 30)
        return dict(supply=self.supply, m7=m7, m30=m30,
                    week_left=max(0, self.supply * self.p.week_cap_ppm // 10**6 - m7),
                    month_left=max(0, self.supply * self.p.month_cap_ppm // 10**6 - m30))

    def _count(self, eid, mag_x10, origin_s, now):
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
        e.status, e.minted, e.clipped, e.mag_x10, e.origin_s = "counted", m, clipped, mag_x10, origin_s
        self.log.append(("event_counted", eid, m, clipped, now))
        return m, raw, clipped

    # ---- events
    def _check(self, eid, mag_x10, origin_s, now, fresh_ok=False):
        p = self.p
        if mag_x10 < p.min_mag_x10 or mag_x10 > 100: raise Reject("magnitude out of range")
        if origin_s > now: raise Reject("origin in the future")
        if now - origin_s > p.max_age_s: raise Reject("origin too old")
        if not fresh_ok and now - origin_s < p.min_age_s: raise Reject("too recent")
        if not eid or len(eid) > 32 or not eid.isascii(): raise Reject("bad event id")

    def _open_pending(self, now):
        """pending events started by bots that can still be attested."""
        return sum(1 for e in self.ev.values() if e.status == "pending" and e.claimer is None and now - min(o for _, o in e.versions) <= self.p.max_age_s)

    def _open_claims(self, now):
        return [e for e in self.ev.values() if e.status == "pending" and e.claimer is not None and now < e.created_at + self.p.claim_wait_s]

    def submit_claim(self, a, eid, mag_x10, origin_s, now):
        """Anyone: tell the contract about a quake. It stays pending until publishers confirm it; a made-up claim never mints."""
        self._check(eid, mag_x10, origin_s, now, fresh_ok=True)
        if eid in self.ev: raise Reject("event id already exists")
        open_claims = self._open_claims(now)
        if any(e.claimer == a for e in open_claims): raise Reject("you already have an open claim")
        if len(open_claims) >= self.p.max_claims: raise Reject("too many open claims")
        e = Ev(created_at=now, claimer=a); e.versions[(mag_x10, origin_s)] = set()
        self.ev[eid] = e
        self.log.append(("claim_submitted", eid, a, mag_x10, origin_s, now))

    def attest(self, pub, eid, mag_x10, origin_s, now):
        """A publisher confirms a quake it found in USGS. Counts (and mints) when `threshold` different publishers attest the same record."""
        if pub not in self.p.publishers: raise Reject("not a publisher")
        self._check(eid, mag_x10, origin_s, now)
        e = self.ev.get(eid)
        if e is not None and e.status == "counted": raise Reject("already counted")
        if e is not None and pub in e.attested: raise Reject("already attested")
        if e is None:
            if self._open_pending(now) >= self.p.max_open: raise Reject("too many pending events")
            e = Ev(created_at=now); self.ev[eid] = e
        key = (mag_x10, origin_s)
        e.versions.setdefault(key, set()).add(pub); e.attested.add(pub)
        self.log.append(("attested", eid, pub, mag_x10, origin_s, len(e.versions[key]), now))
        if len(e.versions[key]) >= self.p.threshold:
            return self._count(eid, mag_x10, origin_s, now)
        return None

    # ---- invariants (RULES.md)
    def check_invariants(self):
        assert self.supply == self.p.s0 + sum(e.minted for e in self.ev.values()), "supply = S0 + mints"
        assert self.supply == sum(self.tok.values()), "balances = supply"
        assert all(v >= 0 for v in self.tok.values())
        for e in self.ev.values():
            assert e.minted == 0 or e.status == "counted"
            if e.status == "counted":
                assert len(e.versions[(e.mag_x10, e.origin_s)]) >= self.p.threshold
        for k in self.buckets:
            assert self.minted_last(k * DAY, 7) <= self.supply * self.p.week_cap_ppm // 10**6, "weekly cap"
            assert self.minted_last(k * DAY, 30) <= self.supply * self.p.month_cap_ppm // 10**6, "monthly cap"

    def snapshot(self):
        nz = lambda d: {k: v for k, v in sorted(d.items()) if v}
        return dict(supply=self.supply, tok=nz(self.tok), buckets=nz(self.buckets), recent=list(self.recent), tapped=sorted(self.tapped),
                    events={k: [e.status, e.minted, e.clipped, e.claimer or "", e.created_at,
                                [[m, o, sorted(s)] for (m, o), s in sorted(e.versions.items())]] for k, e in sorted(self.ev.items())})
