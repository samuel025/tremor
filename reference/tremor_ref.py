"""Tremor Python reference. Source of truth for the math is RULES.md.
Exact integer arithmetic only; every division floors. Amounts are base units (6 decimals)."""
from dataclasses import dataclass, field, asdict
DAY = 86400
UNIT = 10**6
MAX_OPEN_EVENTS = 64  # PLACEHOLDER: open question 6 (measure in sandbox)


class Reject(Exception):
    pass


@dataclass(frozen=True)
class Params:
    s0: int = 1_000_000 * UNIT
    min_mag_x10: int = 60
    base_ppm: int = 2500  # confirmed at Gate A (DECISIONS.md)
    max_event_ppm: int = 15000
    cooldown_s: int = DAY
    week_cap_ppm: int = 15000
    month_cap_ppm: int = 50000
    bond: int = 1000 * UNIT
    window_s: int = DAY
    vote_s: int = 2 * DAY
    slash_pct: int = 20
    quorum_ppm: int = 2000
    max_age_s: int = 30 * DAY
    relief: tuple = ("relief1", "relief2", "relief3", "relief4", "relief5")

    def validate(self):
        if min(self.week_cap_ppm, self.month_cap_ppm, self.base_ppm, self.max_event_ppm, self.cooldown_s, self.bond) <= 0:
            raise Reject("caps and shares must be nonzero")
        if not 0 <= self.slash_pct <= 100:
            raise Reject("slash_pct must be 0..100")
        if len(self.relief) != 5 or len(set(self.relief)) != 5:
            raise Reject("need 5 distinct relief accounts")


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
    mag_x10: int
    origin_s: int
    reporter: str
    reported_at: int
    status: str = "waiting"  # waiting | challenged | counted | rejected
    challenger: str = None
    challenged_at: int = None
    votes: dict = field(default_factory=dict)  # acct -> (side, amount)
    pot: int = 0
    win_left: int = 0
    winner: str = None  # 'real' | 'not' | None (None => everything returned)
    claimed: set = field(default_factory=set)
    minted: int = 0
    clipped: bool = False


class Tremor:
    def __init__(self, p: Params, launcher: str):
        p.validate()
        self.p = p
        self.tok = {launcher: p.s0}
        for a in p.relief:
            self.tok.setdefault(a, 0)
        self.bal = {}     # unlocked bond balance (escrowed in contract)
        self.locked = {}  # locked bonds/stakes held per account (for invariants)
        self.supply = p.s0
        self.ev = {}
        self.recent = []  # last 16 counted origin times
        self.buckets = {}  # day -> minted
        self.log = []

    # ---- token + escrow
    def ft_balance_of(self, a): return self.tok.get(a, 0)

    def ft_transfer(self, f, t, n):
        if n <= 0 or self.tok.get(f, 0) < n: raise Reject("insufficient balance")
        self.tok[f] -= n; self.tok[t] = self.tok.get(t, 0) + n

    def deposit_bond(self, a, n):
        if n <= 0 or self.tok.get(a, 0) < n: raise Reject("insufficient balance")
        self.tok[a] -= n; self.bal[a] = self.bal.get(a, 0) + n

    def withdraw_bond(self, a, n):
        if n <= 0 or self.bal.get(a, 0) < n: raise Reject("insufficient bond balance")
        self.bal[a] -= n; self.tok[a] = self.tok.get(a, 0) + n

    def _lock(self, a, n):
        if self.bal.get(a, 0) < n: raise Reject("insufficient bond balance")
        self.bal[a] -= n; self.locked[a] = self.locked.get(a, 0) + n

    def _unlock(self, a, n):
        self.locked[a] -= n; self.bal[a] = self.bal.get(a, 0) + n

    # ---- caps
    def minted_last(self, now, days):
        d = now // DAY
        return sum(v for k, v in self.buckets.items() if d - days < k <= d)

    def state(self, now):
        m7, m30 = self.minted_last(now, 7), self.minted_last(now, 30)
        return dict(supply=self.supply, m7=m7, m30=m30,
                    week_left=max(0, self.supply * self.p.week_cap_ppm // 10**6 - m7),
                    month_left=max(0, self.supply * self.p.month_cap_ppm // 10**6 - m30))

    def _count(self, eid, now):
        e = self.ev[eid]
        gap = cooldown_gap(e.origin_s, self.recent, self.p.cooldown_s)
        m, raw, clipped = mint_amount(self.p, self.supply, e.mag_x10, gap,
                                      self.minted_last(now, 7), self.minted_last(now, 30))
        for a, n in zip(self.p.relief, split(m)):
            self.tok[a] += n
        self.supply += m
        self.buckets[now // DAY] = self.buckets.get(now // DAY, 0) + m
        self.recent = (self.recent + [e.origin_s])[-16:]
        e.status, e.minted, e.clipped = "counted", m, clipped
        self.log.append(("event_counted", eid, m, clipped, now))
        return m, raw, clipped

    # ---- events
    def report_event(self, a, eid, mag_x10, origin_s, now):
        p = self.p
        if mag_x10 < p.min_mag_x10 or mag_x10 > 100: raise Reject("magnitude out of range")
        if origin_s > now: raise Reject("origin in the future")
        if now - origin_s > p.max_age_s: raise Reject("origin too old")
        if not eid or len(eid) > 32 or not eid.isascii(): raise Reject("bad event id")
        if eid in self.ev: raise Reject("event id already exists")
        if sum(1 for e in self.ev.values() if e.status in ("waiting", "challenged")) >= MAX_OPEN_EVENTS:
            raise Reject("too many open events")
        self._lock(a, p.bond)
        self.ev[eid] = Ev(mag_x10, origin_s, a, now)
        self.log.append(("event_posted", eid, a, now))

    def challenge(self, a, eid, now):
        e = self._get(eid)
        if e.status != "waiting" or now >= e.reported_at + self.p.window_s: raise Reject("window closed")
        if a == e.reporter: raise Reject("reporter cannot challenge")
        self._lock(a, self.p.bond)
        e.status, e.challenger, e.challenged_at = "challenged", a, now
        self.log.append(("event_challenged", eid, a, now))

    def vote(self, a, eid, side, n, now):
        e = self._get(eid)
        if e.status != "challenged" or now >= e.challenged_at + self.p.vote_s: raise Reject("not in vote period")
        if side not in ("real", "not"): raise Reject("bad side")
        if a in e.votes: raise Reject("already voted")
        if n <= 0: raise Reject("zero amount")
        self._lock(a, n)
        e.votes[a] = (side, n)
        self.log.append(("vote_cast", eid, a, side, n, now))

    def finalize(self, eid, now):
        e, p = self._get(eid), self.p
        if e.status == "waiting":
            if now < e.reported_at + p.window_s: raise Reject("window still open")
            self._unlock(e.reporter, p.bond)
            return self._count(eid, now)
        if e.status != "challenged": raise Reject("already final")
        if now < e.challenged_at + p.vote_s: raise Reject("vote still open")
        real = sum(n for s, n in e.votes.values() if s == "real")
        no = sum(n for s, n in e.votes.values() if s == "not")
        if real + no < self.supply * p.quorum_ppm // 10**6 or real == no:
            e.status, e.winner = "rejected", None  # everything returned (see DECISIONS D-1)
            self._unlock(e.reporter, p.bond); self._unlock(e.challenger, p.bond)
            self.log.append(("event_rejected", eid, "no_quorum_or_tie", now))
            return None
        e.winner = "real" if real > no else "not"
        win_bonder, lose_bonder = (e.reporter, e.challenger) if e.winner == "real" else (e.challenger, e.reporter)
        self._unlock(win_bonder, p.bond)
        self.locked[lose_bonder] -= p.bond  # forfeited into pot
        e.pot = p.bond
        for v, (s, n) in e.votes.items():
            if s != e.winner:
                pen = n * p.slash_pct // 100
                self.locked[v] -= pen  # slashed coins move into the pot now
                e.pot += pen
        e.win_left = real if e.winner == "real" else no
        if e.winner == "real":
            return self._count(eid, now)
        e.status = "rejected"
        self.log.append(("event_rejected", eid, "voted_down", now))
        return None

    def claim_vote(self, a, eid, now):
        e, p = self._get(eid), self.p
        if e.status not in ("counted", "rejected"): raise Reject("not final")
        if a not in e.votes or a in e.claimed: raise Reject("nothing to claim")
        side, n = e.votes[a]
        e.claimed.add(a)
        if e.winner is None:
            out = n
            self.locked[a] -= n; self.bal[a] = self.bal.get(a, 0) + n
        elif side == e.winner:
            share = e.pot * n // e.win_left
            e.pot -= share; e.win_left -= n
            self.locked[a] -= n; self.bal[a] = self.bal.get(a, 0) + n + share
            out = n + share
        else:
            pen = n * p.slash_pct // 100
            self.locked[a] -= n - pen; self.bal[a] = self.bal.get(a, 0) + n - pen
            out = n - pen
        self.log.append(("claimed", eid, a, out, now))
        return out

    def _get(self, eid):
        if eid not in self.ev: raise Reject("unknown event")
        return self.ev[eid]

    # ---- invariants (RULES.md section 6)
    def escrow(self):
        return sum(self.bal.values()) + sum(self.locked.values()) + sum(e.pot for e in self.ev.values())

    def check_invariants(self):
        assert self.supply == self.p.s0 + sum(e.minted for e in self.ev.values()), "supply = S0 + mints"
        assert self.supply == sum(self.tok.values()) + self.escrow(), "balances + escrow = supply"
        assert all(v >= 0 for d in (self.tok, self.bal, self.locked) for v in d.values())
        for e in self.ev.values():
            assert e.minted == 0 or e.status == "counted"
        for k in self.buckets:  # supply only grows, so the final supply bounds every earlier allowance
            assert self.minted_last(k * DAY, 7) <= self.supply * self.p.week_cap_ppm // 10**6, "weekly cap"
            assert self.minted_last(k * DAY, 30) <= self.supply * self.p.month_cap_ppm // 10**6, "monthly cap"

    # ---- snapshot used by the conformance vectors (must match the Rust core exactly)
    def snapshot(self):
        nz = lambda d: {k: v for k, v in sorted(d.items()) if v}
        return dict(supply=self.supply, tok=nz(self.tok), bal=nz(self.bal), locked=nz(self.locked),
                    buckets=nz(self.buckets), recent=list(self.recent),
                    events={k: [e.status, e.minted, e.pot, e.win_left, e.winner or "", e.clipped] for k, e in sorted(self.ev.items())})
