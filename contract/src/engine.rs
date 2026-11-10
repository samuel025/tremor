//! Pure Tremor logic: a line-for-line port of reference/tremor_ref.py (RULES.md is the source of truth).
//! Quakes are published by five fixed bots; an event counts when `threshold` different publishers attest the same record.
//! No NEAR types here, so it is tested natively against the Python reference.
use near_sdk::borsh::{BorshDeserialize, BorshSerialize};
use std::collections::{BTreeMap, BTreeSet};

pub const DAY: u64 = 86_400;
const MILLION: u128 = 1_000_000;
pub const SCALE: u128 = 1_000_000_000_000_000_000; // the dividend-per-coin number is kept times this
pub const MAX_ROLL: u32 = 400;                     // most calm days settled in one call

#[derive(BorshSerialize, BorshDeserialize, Clone, Debug)]
#[borsh(crate = "near_sdk::borsh")]
pub struct Params {
    pub s0: u128,
    pub min_mag_x10: u32,
    pub min_alert: u32,     // USGS PAGER alert level a quake needs: 1 green, 2 yellow, 3 orange, 4 red
    pub base_ppm: u128,
    pub max_event_ppm: u128,
    pub cooldown_s: u64,
    pub week_cap_ppm: u128,
    pub month_cap_ppm: u128,
    pub min_age_s: u64,     // finality delay: an attestation is refused until the event is this old
    pub max_age_s: u64,
    pub max_open: u32,      // pending events started by bots
    pub max_claims: u32,    // open visitor claims
    pub claim_wait_s: u64,  // how long a claim stays open
    pub threshold: u32,
    pub calm_ppm: u128,     // share of supply created for holders after each full day with no counted quake; 0 disables it
    pub tap_amount: u128,   // starter coins each account may take once from the pool; 0 disables the tap
    pub publishers: Vec<String>,
    pub relief: Vec<String>,
}

impl Params {
    pub fn validate(&self) -> Result<(), String> {
        if self.week_cap_ppm == 0 || self.month_cap_ppm == 0 || self.base_ppm == 0 || self.max_event_ppm == 0 || self.cooldown_s == 0 {
            return Err("caps and shares must be nonzero".into());
        }
        let rel: BTreeSet<&String> = self.relief.iter().collect();
        if self.relief.len() != 5 || rel.len() != 5 { return Err("need 5 distinct relief accounts".into()); }
        let pubs: BTreeSet<&String> = self.publishers.iter().collect();
        if self.publishers.len() != 5 || pubs.len() != 5 { return Err("need 5 distinct publishers".into()); }
        if self.threshold < 1 || self.threshold > 5 { return Err("threshold must be 1..5".into()); }
        Ok(())
    }
}

#[derive(BorshSerialize, BorshDeserialize, Clone, Copy, PartialEq, Eq, Debug)]
#[borsh(crate = "near_sdk::borsh")]
pub enum Status { Pending, Counted }
impl Status {
    pub fn as_str(&self) -> &'static str { match self { Status::Pending => "pending", Status::Counted => "counted" } }
}

#[derive(BorshSerialize, BorshDeserialize, Clone, Debug)]
#[borsh(crate = "near_sdk::borsh")]
pub struct Ev {
    pub created_at: u64,
    pub claimer: Option<String>,
    pub versions: BTreeMap<(u32, u64, u32), BTreeSet<String>>, // (magnitude x10, origin, alert) -> publishers that attested exactly that
    pub attested: BTreeSet<String>,                        // publishers that already attested this id (any version)
    pub status: Status,
    pub mag_x10: u32,
    pub origin_s: u64,
    pub alert: u32,
    pub minted: u128,
    pub clipped: bool,
}

pub fn share_ppm(p: &Params, mag_x10: u32) -> u128 {
    let steps = (mag_x10 as u128).saturating_sub(50);
    (p.base_ppm * steps / 10).min(p.max_event_ppm)
}

pub fn cooldown_gap(origin_s: u64, recent: &[u64], cooldown_s: u64) -> u64 {
    recent.iter().map(|o| origin_s.abs_diff(*o)).fold(cooldown_s, |a, b| a.min(b))
}

/// Returns (mint, raw, clipped)
pub fn mint_amount(p: &Params, supply: u128, mag_x10: u32, gap: u64, m7: u128, m30: u128) -> (u128, u128, bool) {
    let raw = supply * share_ppm(p, mag_x10) * gap as u128 / (MILLION * p.cooldown_s as u128);
    let wk = (supply * p.week_cap_ppm / MILLION).saturating_sub(m7);
    let mo = (supply * p.month_cap_ppm / MILLION).saturating_sub(m30);
    let m = raw.min(wk).min(mo);
    (m, raw, m < raw)
}

pub fn split(mint: u128) -> [u128; 5] {
    let each = mint / 5;
    [each + mint % 5, each, each, each, each]
}

#[derive(BorshSerialize, BorshDeserialize, Clone, Debug)]
#[borsh(crate = "near_sdk::borsh")]
pub struct Core {
    pub p: Params,
    pub tok: BTreeMap<String, u128>,
    pub supply: u128,
    pub ev: BTreeMap<String, Ev>,
    pub recent: Vec<u64>,              // counted origin times that can still lie within cooldown_s of a future valid event
    pub buckets: BTreeMap<u64, u128>,  // day -> minted by quakes (the caps apply to these)
    pub tapped: BTreeSet<String>,      // accounts that already took their starter coins
    pub given: BTreeMap<String, u128>, // account -> coins it has given to the relief list, ever
    pub acc: u128,                     // dividend per coin so far, times SCALE
    pub paid: BTreeMap<String, u128>,  // account -> the value of acc when its balance was last settled
    pub div_pot: u128,                 // dividend coins created but not yet credited to an account
    pub div_total: u128,               // all dividend coins ever created
    pub calm_days: u64,                // days that paid a dividend
    pub settled_to: Option<u64>,       // the next day to settle (None until the first transaction)
    pub quake_day: Option<u64>,        // the last day on which a quake was counted
    #[borsh(skip)]
    pub pending_log: Vec<(String, String)>, // (event, json data); drained by the contract after every call
}

fn get(m: &BTreeMap<String, u128>, k: &str) -> u128 { *m.get(k).unwrap_or(&0) }
fn add(m: &mut BTreeMap<String, u128>, k: &str, n: u128) { *m.entry(k.to_string()).or_insert(0) += n; }
fn sub(m: &mut BTreeMap<String, u128>, k: &str, n: u128) {
    let e = m.get_mut(k).expect("internal: missing balance");
    *e = e.checked_sub(n).expect("internal: balance underflow");
}
fn q(s: &str) -> String { format!("\"{}\"", s) }

impl Core {
    pub fn new(p: Params, launcher: &str) -> Result<Core, String> {
        p.validate()?;
        let mut tok = BTreeMap::new();
        tok.insert(launcher.to_string(), p.s0);
        for a in &p.relief { tok.entry(a.clone()).or_insert(0); }
        Ok(Core { supply: p.s0, p, tok, ev: BTreeMap::new(), recent: vec![], buckets: BTreeMap::new(), tapped: BTreeSet::new(), given: BTreeMap::new(), acc: 0, paid: BTreeMap::new(), div_pot: 0, div_total: 0, calm_days: 0,
                  settled_to: None, quake_day: None, pending_log: vec![] })
    }

    fn emit(&mut self, event: &str, data: String) { self.pending_log.push((event.to_string(), data)); }

    // ---- token
    pub fn ft_balance_of(&self, a: &str) -> u128 { get(&self.tok, a) }

    pub fn ft_transfer(&mut self, f: &str, t: &str, n: u128, now: u64) -> Result<(), String> {
        self.roll(now);
        self.settle(f); self.settle(t);
        if n == 0 || get(&self.tok, f) < n { return Err("insufficient balance".into()); }
        sub(&mut self.tok, f, n);
        add(&mut self.tok, t, n);
        Ok(())
    }

    /// Once per account: move `tap_amount` from `pool` (coins the launcher put there) to `a`. Mints nothing.
    pub fn tap(&mut self, a: &str, pool: &str, now: u64) -> Result<(), String> {
        self.roll(now);
        self.settle(a); self.settle(pool);
        let amt = self.p.tap_amount;
        if amt == 0 { return Err("tap disabled".into()); }
        if a == pool || self.tapped.contains(a) { return Err("already tapped".into()); }
        if get(&self.tok, pool) < amt { return Err("tap pool empty".into()); }
        sub(&mut self.tok, pool, amt);
        add(&mut self.tok, a, amt);
        self.tapped.insert(a.to_string());
        self.emit("tapped", format!("{{\"account\":{},\"amount\":\"{}\"}}", q(a), amt));
        Ok(())
    }

    /// Any holder: send `n` of your own coins to the relief list, split like a mint. Mints nothing, changes no cap and gives
    /// the giver no say in anything; the contract only remembers the running total per giver. Returns that total.
    pub fn give(&mut self, a: &str, n: u128, now: u64) -> Result<u128, String> {
        self.roll(now);
        if self.p.relief.iter().any(|x| x == a) { return Err("relief accounts cannot give".into()); }
        self.settle(a);
        if n == 0 || get(&self.tok, a) < n { return Err("insufficient balance".into()); }
        sub(&mut self.tok, a, n);
        let relief = self.p.relief.clone();
        for (r, part) in relief.iter().zip(split(n)) { add(&mut self.tok, r, part); }
        add(&mut self.given, a, n);
        let total = get(&self.given, a);
        self.emit("gave", format!("{{\"account\":{},\"amount\":\"{}\",\"total\":\"{}\",\"time\":{}}}", q(a), n, total, now));
        Ok(total)
    }

    // ---- calm-day dividend
    /// Settle every full day that has passed. A day in which no quake was counted creates calm_ppm of the supply for holders. It is
    /// outside the weekly and monthly caps (those bound quake mints) and has its own limit: one per day. Nothing but the days
    /// themselves is used, so settling late gives exactly the result of settling on time.
    pub fn roll(&mut self, now: u64) {
        let today = now / DAY;
        let Some(start) = self.settled_to else {
            self.settled_to = Some(today);
            self.emit("clock_started", format!("{{\"day\":{},\"time\":{}}}", today, now)); // logged so a replay knows when calm days began to count
            return;
        };
        if self.p.calm_ppm == 0 { self.settled_to = Some(start.max(today)); return; }
        let (mut x, mut n, mut minted) = (start, 0u32, 0u128);
        while x < today && n < MAX_ROLL {
            let day = x; x += 1; n += 1;
            if Some(day) == self.quake_day { continue; }
            let relief: u128 = self.p.relief.iter().map(|r| get(&self.tok, r)).sum();
            let eligible = self.supply.saturating_sub(self.div_pot).saturating_sub(relief);
            if eligible == 0 { continue; }
            let d = self.supply * self.p.calm_ppm / MILLION;
            if d == 0 { continue; }
            self.acc += d * SCALE / eligible;
            self.supply += d; self.div_pot += d; self.div_total += d; self.calm_days += 1; minted += d;
        }
        self.settled_to = Some(x);
        if minted > 0 { self.emit("dividend", format!("{{\"from_day\":{},\"to_day\":{},\"minted\":\"{}\",\"supply\":\"{}\",\"time\":{}}}", start, x, minted, self.supply, now)); }
    }

    /// Credit account `a` with the dividend its balance has earned since it was last settled. Relief accounts earn none.
    fn settle(&mut self, a: &str) -> u128 {
        if self.p.relief.iter().any(|x| x == a) { return 0; }
        let owed = get(&self.tok, a) * (self.acc - get(&self.paid, a)) / SCALE;
        self.paid.insert(a.to_string(), self.acc);
        if owed > 0 {
            add(&mut self.tok, a, owed);
            self.div_pot -= owed;
            self.emit("credited", format!("{{\"account\":{},\"amount\":\"{}\"}}", q(a), owed));
        }
        owed
    }

    pub fn claim_dividend(&mut self, a: &str, now: u64) -> Result<u128, String> {
        self.roll(now);
        if self.p.relief.iter().any(|x| x == a) { return Err("relief accounts earn no dividend".into()); }
        let owed = self.settle(a);
        if owed == 0 { return Err("nothing to claim".into()); }
        Ok(owed)
    }

    /// What claim_dividend would credit right now (changes nothing).
    pub fn dividend_of(&self, a: &str, now: u64) -> u128 {
        let mut c = self.clone(); c.roll(now);
        if c.p.relief.iter().any(|x| x == a) { return 0; }
        get(&c.tok, a) * (c.acc - get(&c.paid, a)) / SCALE
    }

    // ---- caps
    pub fn minted_last(&self, now: u64, days: u64) -> u128 {
        let d = now / DAY;
        self.buckets.iter().filter(|(k, _)| **k <= d && **k + days > d).map(|(_, v)| *v).sum()
    }
    /// (m7, m30, week_left, month_left)
    pub fn state(&self, now: u64) -> (u128, u128, u128, u128) {
        let (m7, m30) = (self.minted_last(now, 7), self.minted_last(now, 30));
        (m7, m30,
         (self.supply * self.p.week_cap_ppm / MILLION).saturating_sub(m7),
         (self.supply * self.p.month_cap_ppm / MILLION).saturating_sub(m30))
    }

    fn count(&mut self, eid: &str, mag: u32, origin: u64, alert: u32, now: u64) -> (u128, u128, bool) {
        let gap = cooldown_gap(origin, &self.recent, self.p.cooldown_s);
        let (m, raw, clipped) = mint_amount(&self.p, self.supply, mag, gap, self.minted_last(now, 7), self.minted_last(now, 30));
        let relief = self.p.relief.clone();
        for (a, n) in relief.iter().zip(split(m)) { add(&mut self.tok, a, n); }
        self.supply += m;
        *self.buckets.entry(now / DAY).or_insert(0) += m;
        self.quake_day = Some(now / DAY);
        // Keep every counted origin that can still be within cooldown_s of a valid future event. A future origin is at
        // least now - max_age_s, so anything older than now - max_age_s - cooldown_s can never affect a later gap.
        // Pruning by time (not by count) keeps out-of-order counts correct: the last 16 counted origins is not enough.
        self.recent.push(origin);
        let horizon = now.saturating_sub(self.p.max_age_s.saturating_add(self.p.cooldown_s));
        self.recent.retain(|o| *o >= horizon);
        let e = self.ev.get_mut(eid).unwrap();
        e.status = Status::Counted; e.minted = m; e.clipped = clipped; e.mag_x10 = mag; e.origin_s = origin; e.alert = alert;
        self.emit("event_counted", format!("{{\"event_id\":{},\"mag_x10\":{},\"origin_s\":{},\"alert\":{},\"minted\":\"{}\",\"clipped\":{},\"supply\":\"{}\",\"time\":{}}}", q(eid), mag, origin, alert, m, clipped, self.supply, now));
        (m, raw, clipped)
    }

    // ---- events
    fn check(&self, eid: &str, mag: u32, origin: u64, alert: u32, now: u64, fresh_ok: bool) -> Result<(), String> {
        let p = &self.p;
        if mag < p.min_mag_x10 || mag > 100 { return Err("magnitude out of range".into()); }
        if alert < 1 || alert > 4 { return Err("alert level out of range".into()); }
        if alert < p.min_alert { return Err("expected impact too low".into()); }
        if origin > now { return Err("origin in the future".into()); }
        if now - origin > p.max_age_s { return Err("origin too old".into()); }
        if !fresh_ok && now - origin < p.min_age_s { return Err("too recent".into()); }
        if eid.is_empty() || eid.len() > 32 || !eid.is_ascii() { return Err("bad event id".into()); }
        Ok(())
    }

    /// pending events started by bots that can still be attested
    fn open_pending(&self, now: u64) -> u32 {
        self.ev.values().filter(|e| e.status == Status::Pending && e.claimer.is_none()
            && now.saturating_sub(e.versions.keys().map(|k| k.1).min().unwrap_or(0)) <= self.p.max_age_s).count() as u32
    }
    fn open_claims(&self, now: u64) -> Vec<&Ev> {
        self.ev.values().filter(|e| e.status == Status::Pending && e.claimer.is_some() && now < e.created_at + self.p.claim_wait_s).collect()
    }

    /// Anyone: tell the contract about a quake. It stays pending until publishers confirm it; a made-up claim never mints.
    pub fn submit_claim(&mut self, a: &str, eid: &str, mag: u32, origin: u64, alert: u32, now: u64) -> Result<(), String> {
        self.roll(now);
        self.check(eid, mag, origin, alert, now, true)?;
        if self.ev.contains_key(eid) { return Err("event id already exists".into()); }
        let open = self.open_claims(now);
        if open.iter().any(|e| e.claimer.as_deref() == Some(a)) { return Err("you already have an open claim".into()); }
        if open.len() as u32 >= self.p.max_claims { return Err("too many open claims".into()); }
        let mut versions = BTreeMap::new(); versions.insert((mag, origin, alert), BTreeSet::new());
        self.ev.insert(eid.to_string(), Ev { created_at: now, claimer: Some(a.to_string()), versions, attested: BTreeSet::new(), status: Status::Pending, mag_x10: 0, origin_s: 0, alert: 0, minted: 0, clipped: false });
        self.emit("claim_submitted", format!("{{\"event_id\":{},\"claimer\":{},\"mag_x10\":{},\"origin_s\":{},\"alert\":{},\"time\":{}}}", q(eid), q(a), mag, origin, alert, now));
        Ok(())
    }

    /// A publisher confirms a quake it found in USGS. Counts (and mints) when `threshold` different publishers attest the same record.
    pub fn attest(&mut self, publ: &str, eid: &str, mag: u32, origin: u64, alert: u32, now: u64) -> Result<Option<(u128, u128, bool)>, String> {
        self.roll(now);
        if !self.p.publishers.iter().any(|x| x == publ) { return Err("not a publisher".into()); }
        self.check(eid, mag, origin, alert, now, false)?;
        if let Some(e) = self.ev.get(eid) {
            if e.status == Status::Counted { return Err("already counted".into()); }
            if e.attested.contains(publ) { return Err("already attested".into()); }
        } else {
            if self.open_pending(now) >= self.p.max_open { return Err("too many pending events".into()); }
            self.ev.insert(eid.to_string(), Ev { created_at: now, claimer: None, versions: BTreeMap::new(), attested: BTreeSet::new(), status: Status::Pending, mag_x10: 0, origin_s: 0, alert: 0, minted: 0, clipped: false });
        }
        let e = self.ev.get_mut(eid).unwrap();
        let set = e.versions.entry((mag, origin, alert)).or_insert_with(BTreeSet::new);
        set.insert(publ.to_string());
        let n = set.len() as u32;
        e.attested.insert(publ.to_string());
        let threshold = self.p.threshold;
        self.emit("attested", format!("{{\"event_id\":{},\"publisher\":{},\"mag_x10\":{},\"origin_s\":{},\"alert\":{},\"attestations\":{},\"time\":{}}}", q(eid), q(publ), mag, origin, alert, n, now));
        if n >= threshold { return Ok(Some(self.count(eid, mag, origin, alert, now))); }
        Ok(None)
    }

    // ---- invariants (RULES.md)
    pub fn check_invariants(&self) {
        assert_eq!(self.supply, self.p.s0 + self.ev.values().map(|e| e.minted).sum::<u128>() + self.div_total, "supply = S0 + mints + dividends");
        assert_eq!(self.supply, self.tok.values().sum::<u128>() + self.div_pot, "balances + unclaimed dividend = supply");
        assert!(self.given.iter().all(|(a, v)| *v > 0 && !self.p.relief.contains(a)), "givers");
        for e in self.ev.values() {
            assert!(e.minted == 0 || e.status == Status::Counted);
            if e.status == Status::Counted { assert!(e.versions[&(e.mag_x10, e.origin_s, e.alert)].len() as u32 >= self.p.threshold && e.alert >= self.p.min_alert); }
        }
        for k in self.buckets.keys() {
            assert!(self.minted_last(k * DAY, 7) <= self.supply * self.p.week_cap_ppm / MILLION, "weekly cap");
            assert!(self.minted_last(k * DAY, 30) <= self.supply * self.p.month_cap_ppm / MILLION, "monthly cap");
        }
    }
}
