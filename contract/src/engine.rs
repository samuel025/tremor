//! Pure Tremor logic: a line-for-line port of reference/tremor_ref.py (RULES.md is the source of truth).
//! Quakes are published by five fixed bots; an event counts when `threshold` different publishers attest the same record.
//! No NEAR types here, so it is tested natively against the Python reference.
use near_sdk::borsh::{BorshDeserialize, BorshSerialize};
use std::collections::{BTreeMap, BTreeSet};

pub const DAY: u64 = 86_400;
const MILLION: u128 = 1_000_000;

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
    pub match_ppm: u128,         // donation match: a gift of n is topped up by n * match_ppm / 10^6 from the reserve (100000 = 10%); 0 disables matching
    pub match_day_ppm: u128,     // most the reserve may add in one UTC day, in ppm of the supply
    pub match_month_ppm: u128,   // most the reserve may add over 30 days, in ppm of the supply
    pub match_account_max: u128, // most the reserve may add because of one account's gifts, ever (base units)
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
        if self.match_ppm > MILLION { return Err("match rate must be 0..1,000,000 ppm".into()); }
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
    pub given_sum: u128,               // all coins ever given
    pub reserve: u128,                 // the donation-matching reserve: coins people put in with fund_match; they leave only as matches
    pub funded_total: u128,            // all coins ever put into the reserve
    pub matched_total: u128,           // all coins the reserve has added to gifts
    pub matched_by: BTreeMap<String, u128>, // account -> coins the reserve added because of that account's gifts
    pub mbuckets: BTreeMap<u64, u128>, // day -> coins matched that day (the match budgets apply to these)
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
        Ok(Core { supply: p.s0, p, tok, ev: BTreeMap::new(), recent: vec![], buckets: BTreeMap::new(), tapped: BTreeSet::new(), given: BTreeMap::new(), given_sum: 0, reserve: 0, funded_total: 0, matched_total: 0,
                  matched_by: BTreeMap::new(), mbuckets: BTreeMap::new(), pending_log: vec![] })
    }

    fn emit(&mut self, event: &str, data: String) { self.pending_log.push((event.to_string(), data)); }

    // ---- token
    pub fn ft_balance_of(&self, a: &str) -> u128 { get(&self.tok, a) }

    pub fn ft_transfer(&mut self, f: &str, t: &str, n: u128) -> Result<(), String> {
        if n == 0 || get(&self.tok, f) < n { return Err("insufficient balance".into()); }
        sub(&mut self.tok, f, n);
        add(&mut self.tok, t, n);
        Ok(())
    }

    /// Once per account: move `tap_amount` from `pool` (coins the launcher put there) to `a`. Mints nothing.
    pub fn tap(&mut self, a: &str, pool: &str) -> Result<(), String> {
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

    // ---- giving and matching
    pub fn matched_last(&self, now: u64, days: u64) -> u128 {
        let d = now / DAY;
        self.mbuckets.iter().filter(|(k, _)| **k <= d && **k + days > d).map(|(_, v)| *v).sum()
    }

    /// What the reserve would add to a gift of `n` from account `a` right now: the smallest of the rate, what is in the reserve,
    /// today's budget, the 30-day budget and what is left of the account's own allowance.
    pub fn match_for(&self, a: &str, n: u128, now: u64) -> u128 {
        let p = &self.p;
        if p.match_ppm == 0 || self.reserve == 0 { return 0; }
        let raw = n * p.match_ppm / MILLION;
        let day_left = (self.supply * p.match_day_ppm / MILLION).saturating_sub(self.matched_last(now, 1));
        let month_left = (self.supply * p.match_month_ppm / MILLION).saturating_sub(self.matched_last(now, 30));
        let acct_left = p.match_account_max.saturating_sub(get(&self.matched_by, a));
        raw.min(self.reserve).min(day_left).min(month_left).min(acct_left)
    }

    /// Any holder except a relief account: put `n` of your own coins into the matching reserve. They can only ever leave as matches
    /// added to gifts to the relief list; there is no way to take them back out. Mints nothing. Returns the reserve afterwards.
    pub fn fund_match(&mut self, a: &str, n: u128, now: u64) -> Result<u128, String> {
        if self.p.relief.iter().any(|x| x == a) { return Err("relief accounts cannot fund the reserve".into()); }
        if n == 0 || get(&self.tok, a) < n { return Err("insufficient balance".into()); }
        sub(&mut self.tok, a, n);
        self.reserve += n; self.funded_total += n;
        self.emit("funded", format!("{{\"account\":{},\"amount\":\"{}\",\"reserve\":\"{}\",\"time\":{}}}", q(a), n, self.reserve, now));
        Ok(self.reserve)
    }

    /// Any holder: send `n` of your own coins to the relief list, split like a mint, topped up by the match when the reserve allows.
    /// Mints nothing, changes no cap and gives the giver no say in anything; the contract only remembers the running total per giver.
    /// Returns (the giver's total given, the match that was added).
    pub fn give(&mut self, a: &str, n: u128, now: u64) -> Result<(u128, u128), String> {
        if self.p.relief.iter().any(|x| x == a) { return Err("relief accounts cannot give".into()); }
        if n == 0 || get(&self.tok, a) < n { return Err("insufficient balance".into()); }
        let m = self.match_for(a, n, now);
        sub(&mut self.tok, a, n);
        self.reserve -= m;
        let relief = self.p.relief.clone();
        for (r, part) in relief.iter().zip(split(n + m)) { add(&mut self.tok, r, part); }
        add(&mut self.given, a, n); self.given_sum += n;
        if m > 0 {
            add(&mut self.matched_by, a, m); self.matched_total += m;
            *self.mbuckets.entry(now / DAY).or_insert(0) += m;
        }
        let total = get(&self.given, a);
        self.emit("gave", format!("{{\"account\":{},\"amount\":\"{}\",\"matched\":\"{}\",\"total\":\"{}\",\"reserve\":\"{}\",\"time\":{}}}", q(a), n, m, total, self.reserve, now));
        Ok((total, m))
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
        assert_eq!(self.supply, self.p.s0 + self.ev.values().map(|e| e.minted).sum::<u128>(), "supply = S0 + quake mints");
        assert_eq!(self.supply, self.tok.values().sum::<u128>() + self.reserve, "balances + reserve = supply");
        assert!(self.given.iter().all(|(a, v)| *v > 0 && !self.p.relief.contains(a)), "givers");
        assert_eq!(self.given_sum, self.given.values().sum::<u128>(), "giver totals");
        assert!(self.matched_total == self.matched_by.values().sum::<u128>() && self.matched_total == self.mbuckets.values().sum::<u128>(), "match totals");
        assert_eq!(self.reserve, self.funded_total - self.matched_total, "the reserve only grows by funding and shrinks by matching");
        assert!(self.matched_by.values().all(|v| *v <= self.p.match_account_max), "per-account match allowance");
        for k in self.mbuckets.keys() {
            assert!(self.matched_last(k * DAY, 1) <= self.supply * self.p.match_day_ppm / MILLION, "daily match budget");
            assert!(self.matched_last(k * DAY, 30) <= self.supply * self.p.match_month_ppm / MILLION, "monthly match budget");
        }
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
