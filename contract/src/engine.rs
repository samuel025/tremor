//! Pure Tremor logic: a line-for-line port of reference/tremor_ref.py (RULES.md is the source of truth).
//! No NEAR types here, so it is tested natively against the Python reference.
use near_sdk::borsh::{BorshDeserialize, BorshSerialize};
use std::collections::{BTreeMap, BTreeSet};

pub const DAY: u64 = 86_400;
pub const MAX_OPEN_EVENTS: usize = 64; // PLACEHOLDER until measured (DECISIONS D-4)
const MILLION: u128 = 1_000_000;

#[derive(BorshSerialize, BorshDeserialize, Clone, Debug)]
#[borsh(crate = "near_sdk::borsh")]
pub struct Params {
    pub s0: u128,
    pub min_mag_x10: u32,
    pub base_ppm: u128,
    pub max_event_ppm: u128,
    pub cooldown_s: u64,
    pub week_cap_ppm: u128,
    pub month_cap_ppm: u128,
    pub bond: u128,
    pub window_s: u64,
    pub vote_s: u64,
    pub slash_pct: u128,
    pub quorum_ppm: u128,
    pub max_age_s: u64,
    pub relief: Vec<String>,
}

impl Params {
    pub fn validate(&self) -> Result<(), String> {
        if self.week_cap_ppm == 0 || self.month_cap_ppm == 0 || self.base_ppm == 0 || self.max_event_ppm == 0
            || self.cooldown_s == 0 || self.bond == 0 {
            return Err("caps and shares must be nonzero".into());
        }
        if self.slash_pct > 100 { return Err("slash_pct must be 0..100".into()); }
        let set: BTreeSet<&String> = self.relief.iter().collect();
        if self.relief.len() != 5 || set.len() != 5 { return Err("need 5 distinct relief accounts".into()); }
        Ok(())
    }
}

#[derive(BorshSerialize, BorshDeserialize, Clone, Copy, PartialEq, Eq, Debug)]
#[borsh(crate = "near_sdk::borsh")]
pub enum Status { Waiting, Challenged, Counted, Rejected }
impl Status {
    pub fn as_str(&self) -> &'static str {
        match self { Status::Waiting => "waiting", Status::Challenged => "challenged", Status::Counted => "counted", Status::Rejected => "rejected" }
    }
}

#[derive(BorshSerialize, BorshDeserialize, Clone, Debug)]
#[borsh(crate = "near_sdk::borsh")]
pub struct Ev {
    pub mag_x10: u32,
    pub origin_s: u64,
    pub reporter: String,
    pub reported_at: u64,
    pub status: Status,
    pub challenger: Option<String>,
    pub challenged_at: u64,
    pub votes: BTreeMap<String, (bool, u128)>, // account -> (side is "real", amount)
    pub pot: u128,
    pub win_left: u128,
    pub winner: Option<bool>, // Some(true) = "real", Some(false) = "not real", None = everything returned
    pub claimed: BTreeSet<String>,
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
    pub bal: BTreeMap<String, u128>,    // unlocked bond balance (escrowed in the contract)
    pub locked: BTreeMap<String, u128>, // locked bonds and stakes
    pub supply: u128,
    pub ev: BTreeMap<String, Ev>,
    pub recent: Vec<u64>,               // last 16 counted origin times
    pub buckets: BTreeMap<u64, u128>,   // day -> minted
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
        Ok(Core { supply: p.s0, p, tok, bal: BTreeMap::new(), locked: BTreeMap::new(), ev: BTreeMap::new(),
                  recent: vec![], buckets: BTreeMap::new(), pending_log: vec![] })
    }

    fn emit(&mut self, event: &str, data: String) { self.pending_log.push((event.to_string(), data)); }

    // ---- token + escrow
    pub fn ft_balance_of(&self, a: &str) -> u128 { get(&self.tok, a) }
    pub fn bond_balance_of(&self, a: &str) -> u128 { get(&self.bal, a) }

    pub fn ft_transfer(&mut self, f: &str, t: &str, n: u128) -> Result<(), String> {
        if n == 0 || get(&self.tok, f) < n { return Err("insufficient balance".into()); }
        sub(&mut self.tok, f, n);
        add(&mut self.tok, t, n);
        Ok(())
    }
    pub fn deposit_bond(&mut self, a: &str, n: u128) -> Result<(), String> {
        if n == 0 || get(&self.tok, a) < n { return Err("insufficient balance".into()); }
        sub(&mut self.tok, a, n);
        add(&mut self.bal, a, n);
        Ok(())
    }
    pub fn withdraw_bond(&mut self, a: &str, n: u128) -> Result<(), String> {
        if n == 0 || get(&self.bal, a) < n { return Err("insufficient bond balance".into()); }
        sub(&mut self.bal, a, n);
        add(&mut self.tok, a, n);
        Ok(())
    }
    fn lock(&mut self, a: &str, n: u128) -> Result<(), String> {
        if get(&self.bal, a) < n { return Err("insufficient bond balance".into()); }
        sub(&mut self.bal, a, n);
        add(&mut self.locked, a, n);
        Ok(())
    }
    fn unlock(&mut self, a: &str, n: u128) {
        sub(&mut self.locked, a, n);
        add(&mut self.bal, a, n);
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

    fn count(&mut self, eid: &str, now: u64) -> (u128, u128, bool) {
        let (mag, origin) = { let e = &self.ev[eid]; (e.mag_x10, e.origin_s) };
        let gap = cooldown_gap(origin, &self.recent, self.p.cooldown_s);
        let (m, raw, clipped) = mint_amount(&self.p, self.supply, mag, gap, self.minted_last(now, 7), self.minted_last(now, 30));
        let relief = self.p.relief.clone();
        for (a, n) in relief.iter().zip(split(m)) { add(&mut self.tok, a, n); }
        self.supply += m;
        *self.buckets.entry(now / DAY).or_insert(0) += m;
        self.recent.push(origin);
        if self.recent.len() > 16 { self.recent.remove(0); }
        let e = self.ev.get_mut(eid).unwrap();
        e.status = Status::Counted; e.minted = m; e.clipped = clipped;
        self.emit("event_counted", format!("{{\"event_id\":{},\"minted\":\"{}\",\"clipped\":{},\"supply\":\"{}\"}}", q(eid), m, clipped, self.supply));
        (m, raw, clipped)
    }

    fn get_ev(&self, eid: &str) -> Result<&Ev, String> { self.ev.get(eid).ok_or_else(|| "unknown event".to_string()) }

    // ---- events
    pub fn report_event(&mut self, a: &str, eid: &str, mag_x10: u32, origin_s: u64, now: u64) -> Result<(), String> {
        let p = self.p.clone();
        if mag_x10 < p.min_mag_x10 || mag_x10 > 100 { return Err("magnitude out of range".into()); }
        if origin_s > now { return Err("origin in the future".into()); }
        if now - origin_s > p.max_age_s { return Err("origin too old".into()); }
        if eid.is_empty() || eid.len() > 32 || !eid.is_ascii() { return Err("bad event id".into()); }
        if self.ev.contains_key(eid) { return Err("event id already exists".into()); }
        let open = self.ev.values().filter(|e| matches!(e.status, Status::Waiting | Status::Challenged)).count();
        if open >= MAX_OPEN_EVENTS { return Err("too many open events".into()); }
        self.lock(a, p.bond)?;
        self.ev.insert(eid.to_string(), Ev { mag_x10, origin_s, reporter: a.to_string(), reported_at: now, status: Status::Waiting,
            challenger: None, challenged_at: 0, votes: BTreeMap::new(), pot: 0, win_left: 0, winner: None,
            claimed: BTreeSet::new(), minted: 0, clipped: false });
        self.emit("event_posted", format!("{{\"event_id\":{},\"mag_x10\":{},\"origin_s\":{},\"reporter\":{},\"time\":{}}}", q(eid), mag_x10, origin_s, q(a), now));
        Ok(())
    }

    pub fn challenge(&mut self, a: &str, eid: &str, now: u64) -> Result<(), String> {
        let (status, rep_at, reporter) = { let e = self.get_ev(eid)?; (e.status, e.reported_at, e.reporter.clone()) };
        if status != Status::Waiting || now >= rep_at + self.p.window_s { return Err("window closed".into()); }
        if a == reporter { return Err("reporter cannot challenge".into()); }
        let bond = self.p.bond;
        self.lock(a, bond)?;
        let e = self.ev.get_mut(eid).unwrap();
        e.status = Status::Challenged; e.challenger = Some(a.to_string()); e.challenged_at = now;
        self.emit("event_challenged", format!("{{\"event_id\":{},\"challenger\":{},\"time\":{}}}", q(eid), q(a), now));
        Ok(())
    }

    pub fn vote(&mut self, a: &str, eid: &str, real: Option<bool>, n: u128, now: u64) -> Result<(), String> {
        let (status, ch_at, voted) = { let e = self.get_ev(eid)?; (e.status, e.challenged_at, e.votes.contains_key(a)) };
        if status != Status::Challenged || now >= ch_at + self.p.vote_s { return Err("not in vote period".into()); }
        let real = real.ok_or_else(|| "bad side".to_string())?;
        if voted { return Err("already voted".into()); }
        if n == 0 { return Err("zero amount".into()); }
        self.lock(a, n)?;
        self.ev.get_mut(eid).unwrap().votes.insert(a.to_string(), (real, n));
        self.emit("vote_cast", format!("{{\"event_id\":{},\"voter\":{},\"side\":{},\"amount\":\"{}\"}}", q(eid), q(a), q(if real { "real" } else { "not" }), n));
        Ok(())
    }

    /// Ok(None): no mint. Ok(Some((mint, raw, clipped))).
    pub fn finalize(&mut self, eid: &str, now: u64) -> Result<Option<(u128, u128, bool)>, String> {
        let p = self.p.clone();
        let e = self.get_ev(eid)?.clone();
        match e.status {
            Status::Waiting => {
                if now < e.reported_at + p.window_s { return Err("window still open".into()); }
                self.unlock(&e.reporter, p.bond);
                Ok(Some(self.count(eid, now)))
            }
            Status::Challenged => {
                if now < e.challenged_at + p.vote_s { return Err("vote still open".into()); }
                let real: u128 = e.votes.values().filter(|v| v.0).map(|v| v.1).sum();
                let no: u128 = e.votes.values().filter(|v| !v.0).map(|v| v.1).sum();
                let challenger = e.challenger.clone().unwrap();
                if real + no < self.supply * p.quorum_ppm / MILLION || real == no {
                    let ev = self.ev.get_mut(eid).unwrap();
                    ev.status = Status::Rejected; ev.winner = None;
                    self.unlock(&e.reporter, p.bond);
                    self.unlock(&challenger, p.bond);
                    self.emit("event_rejected", format!("{{\"event_id\":{},\"reason\":\"no_quorum_or_tie\"}}", q(eid)));
                    return Ok(None);
                }
                let win_real = real > no;
                let (win_bonder, lose_bonder) = if win_real { (e.reporter.clone(), challenger) } else { (challenger, e.reporter.clone()) };
                self.unlock(&win_bonder, p.bond);
                sub(&mut self.locked, &lose_bonder, p.bond); // forfeited into the pot
                let mut pot = p.bond;
                for (v, (side, n)) in e.votes.iter() {
                    if *side != win_real {
                        let pen = n * p.slash_pct / 100;
                        sub(&mut self.locked, v, pen); // slashed coins move into the pot now
                        pot += pen;
                    }
                }
                {
                    let ev = self.ev.get_mut(eid).unwrap();
                    ev.winner = Some(win_real); ev.pot = pot; ev.win_left = if win_real { real } else { no };
                }
                if win_real { return Ok(Some(self.count(eid, now))); }
                self.ev.get_mut(eid).unwrap().status = Status::Rejected;
                self.emit("event_rejected", format!("{{\"event_id\":{},\"reason\":\"voted_down\"}}", q(eid)));
                Ok(None)
            }
            _ => Err("already final".into()),
        }
    }

    pub fn claim_vote(&mut self, a: &str, eid: &str) -> Result<u128, String> {
        let p = self.p.clone();
        let e = self.get_ev(eid)?.clone();
        if !matches!(e.status, Status::Counted | Status::Rejected) { return Err("not final".into()); }
        let (side, n) = match e.votes.get(a) { Some(v) if !e.claimed.contains(a) => *v, _ => return Err("nothing to claim".into()) };
        let ev = self.ev.get_mut(eid).unwrap();
        ev.claimed.insert(a.to_string());
        let out;
        match e.winner {
            None => { sub(&mut self.locked, a, n); add(&mut self.bal, a, n); out = n; }
            Some(w) if w == side => {
                let share = e.pot * n / e.win_left;
                ev.pot -= share; ev.win_left -= n;
                sub(&mut self.locked, a, n); add(&mut self.bal, a, n + share); out = n + share;
            }
            Some(_) => {
                let pen = n * p.slash_pct / 100;
                sub(&mut self.locked, a, n - pen); add(&mut self.bal, a, n - pen); out = n - pen;
            }
        }
        self.emit("claimed", format!("{{\"event_id\":{},\"account\":{},\"paid\":\"{}\"}}", q(eid), q(a), out));
        Ok(out)
    }

    // ---- invariants (RULES.md section 6)
    pub fn escrow(&self) -> u128 {
        self.bal.values().sum::<u128>() + self.locked.values().sum::<u128>() + self.ev.values().map(|e| e.pot).sum::<u128>()
    }
    pub fn check_invariants(&self) {
        assert_eq!(self.supply, self.p.s0 + self.ev.values().map(|e| e.minted).sum::<u128>(), "supply = S0 + mints");
        assert_eq!(self.supply, self.tok.values().sum::<u128>() + self.escrow(), "balances + escrow = supply");
        for e in self.ev.values() { assert!(e.minted == 0 || e.status == Status::Counted); }
        for k in self.buckets.keys() {
            assert!(self.minted_last(k * DAY, 7) <= self.supply * self.p.week_cap_ppm / MILLION, "weekly cap");
            assert!(self.minted_last(k * DAY, 30) <= self.supply * self.p.month_cap_ppm / MILLION, "monthly cap");
        }
    }
}
