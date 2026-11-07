//! Tremor: NEP-141 token + earthquake event system in one contract. No owner, no upgrade path,
//! every parameter is fixed in `new`. Testnet prototype; the coin has no value.
pub mod engine;

use engine::{Core, Params, Status};
use near_sdk::json_types::U128;
use near_sdk::store::{LookupSet, Vector};
use near_sdk::{
    assert_one_yocto, env, ext_contract, near, require, AccountId, Gas, NearToken, PanicOnDefault, Promise, PromiseOrValue,
};

const STORAGE_MIN: NearToken = NearToken::from_yoctonear(1_250_000_000_000_000_000_000); // 0.00125 NEAR, flat
const GAS_RESOLVE: Gas = Gas::from_tgas(5);
const GAS_MIN_TRANSFER_CALL: Gas = Gas::from_tgas(30);

#[ext_contract(ext_receiver)]
pub trait FtReceiver {
    fn ft_on_transfer(&mut self, sender_id: AccountId, amount: U128, msg: String) -> PromiseOrValue<U128>;
}
#[ext_contract(ext_self)]
pub trait FtResolver {
    fn ft_resolve_transfer(&mut self, sender_id: AccountId, receiver_id: AccountId, amount: U128) -> U128;
}

/// JSON form of the launch parameters (big numbers as strings).
#[near(serializers = [json])]
#[derive(Clone)]
pub struct ParamsArg {
    pub s0: U128,
    pub min_mag_x10: u32,
    pub base_ppm: u32,
    pub max_event_ppm: u32,
    pub cooldown_s: u64,
    pub week_cap_ppm: u32,
    pub month_cap_ppm: u32,
    pub bond: U128,
    pub window_s: u64,
    pub vote_s: u64,
    pub slash_pct: u32,
    pub quorum_ppm: u32,
    pub max_age_s: u64,
    pub tap_amount: U128, // starter coins per account from the tap pool; "0" disables the tap
    pub relief_accounts: Option<Vec<AccountId>>, // only filled by get_params
}

#[near(serializers = [json])]
pub struct StateView {
    pub supply: U128,
    pub initial_supply: U128,
    pub minted_7d: U128,
    pub minted_30d: U128,
    pub week_left: U128,
    pub month_left: U128,
    pub open_events: u32,
    pub tap_pool: U128,
    pub log_len: u64,
    pub now_s: u64,
}

#[near(serializers = [json])]
pub struct EventView {
    pub event_id: String,
    pub mag_x10: u32,
    pub origin_s: u64,
    pub reporter: AccountId,
    pub reported_at: u64,
    pub status: String,
    pub challenger: Option<AccountId>,
    pub challenged_at: u64,
    pub window_ends: u64,
    pub vote_ends: Option<u64>,
    pub real_locked: U128,
    pub not_real_locked: U128,
    pub minted: U128,
    pub clipped: bool,
    pub pot: U128,
}

#[near(serializers = [json])]
pub struct StorageBalance { pub total: NearToken, pub available: NearToken }
#[near(serializers = [json])]
pub struct StorageBalanceBounds { pub min: NearToken, pub max: Option<NearToken> }
#[near(serializers = [json])]
pub struct FtMetadata {
    pub spec: String, pub name: String, pub symbol: String, pub icon: Option<String>,
    pub reference: Option<String>, pub reference_hash: Option<String>, pub decimals: u8,
}

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct Contract {
    core: Core,
    log: Vector<String>,
    registered: LookupSet<AccountId>,
}

fn now_s() -> u64 { env::block_timestamp() / 1_000_000_000 }
fn caller() -> String { env::predecessor_account_id().to_string() }
fn unwrap_or_panic<T>(r: Result<T, String>) -> T { match r { Ok(v) => v, Err(e) => env::panic_str(&e) } }

#[near]
impl Contract {
    /// Fixed forever. There is no owner, no admin method and no way to change a parameter afterwards.
    #[init]
    pub fn new(params: ParamsArg, relief_accounts: Vec<AccountId>, launcher: AccountId) -> Self {
        let p = Params {
            s0: params.s0.0, min_mag_x10: params.min_mag_x10, base_ppm: params.base_ppm as u128,
            max_event_ppm: params.max_event_ppm as u128, cooldown_s: params.cooldown_s,
            week_cap_ppm: params.week_cap_ppm as u128, month_cap_ppm: params.month_cap_ppm as u128, bond: params.bond.0,
            window_s: params.window_s, vote_s: params.vote_s, slash_pct: params.slash_pct as u128,
            quorum_ppm: params.quorum_ppm as u128, max_age_s: params.max_age_s, tap_amount: params.tap_amount.0,
            relief: relief_accounts.iter().map(|a| a.to_string()).collect(),
        };
        let core = unwrap_or_panic(Core::new(p, launcher.as_str()));
        let mut registered = LookupSet::new(b"r");
        let launcher_s = launcher.to_string();
        registered.insert(launcher);
        registered.insert(env::current_account_id()); // the contract holds the tap pool, so it must be able to receive coins
        for a in relief_accounts { registered.insert(a); }
        let s0 = core.supply;
        let c = Self { core, log: Vector::new(b"l"), registered };
        c.emit_standard("ft_mint", format!("[{{\"owner_id\":\"{}\",\"amount\":\"{}\",\"memo\":\"initial supply\"}}]", launcher_s, s0));
        c
    }

    // ---------------- NEP-141
    #[payable]
    pub fn ft_transfer(&mut self, receiver_id: AccountId, amount: U128, memo: Option<String>) {
        assert_one_yocto();
        let sender = env::predecessor_account_id();
        self.do_transfer(&sender, &receiver_id, amount.0, memo);
    }

    #[payable]
    pub fn ft_transfer_call(&mut self, receiver_id: AccountId, amount: U128, memo: Option<String>, msg: String) -> PromiseOrValue<U128> {
        assert_one_yocto();
        require!(env::prepaid_gas() > GAS_MIN_TRANSFER_CALL.saturating_add(GAS_RESOLVE), "More gas is required");
        let sender = env::predecessor_account_id();
        self.do_transfer(&sender, &receiver_id, amount.0, memo);
        let call_gas = env::prepaid_gas().saturating_sub(env::used_gas()).saturating_sub(GAS_RESOLVE);
        ext_receiver::ext(receiver_id.clone()).with_static_gas(call_gas.saturating_sub(Gas::from_tgas(2)))
            .ft_on_transfer(sender.clone(), amount, msg)
            .then(ext_self::ext(env::current_account_id()).with_static_gas(GAS_RESOLVE).ft_resolve_transfer(sender, receiver_id, amount))
            .into()
    }

    #[private]
    pub fn ft_resolve_transfer(&mut self, sender_id: AccountId, receiver_id: AccountId, amount: U128) -> U128 {
        let unused = match env::promise_result_checked(0, 64) {
            Ok(v) => near_sdk::serde_json::from_slice::<U128>(&v).map(|u| u.0.min(amount.0)).unwrap_or(amount.0),
            Err(_) => amount.0,
        };
        if unused > 0 {
            let refund = unused.min(self.core.ft_balance_of(receiver_id.as_str())); // bounded by what the receiver still holds
            if refund > 0 {
                let _ = self.core.ft_transfer(receiver_id.as_str(), sender_id.as_str(), refund);
                self.emit_standard("ft_transfer", format!("[{{\"old_owner_id\":\"{}\",\"new_owner_id\":\"{}\",\"amount\":\"{}\",\"memo\":\"refund\"}}]", receiver_id, sender_id, refund));
                return U128(amount.0 - refund);
            }
        }
        U128(amount.0 - 0)
    }

    pub fn ft_total_supply(&self) -> U128 { U128(self.core.supply) }
    pub fn ft_balance_of(&self, account_id: AccountId) -> U128 { U128(self.core.ft_balance_of(account_id.as_str())) }
    pub fn ft_metadata(&self) -> FtMetadata {
        FtMetadata { spec: "ft-1.0.0".into(), name: "Tremor (testnet, no value)".into(), symbol: "TREM".into(), icon: None,
                     reference: None, reference_hash: None, decimals: 6 }
    }

    // ---------------- NEP-145 (flat minimum)
    #[payable]
    pub fn storage_deposit(&mut self, account_id: Option<AccountId>, _registration_only: Option<bool>) -> StorageBalance {
        let who = account_id.unwrap_or_else(env::predecessor_account_id);
        let dep = env::attached_deposit();
        if self.registered.contains(&who) {
            if dep.as_yoctonear() > 0 { let _ = Promise::new(env::predecessor_account_id()).transfer(dep); }
        } else {
            require!(dep >= STORAGE_MIN, "The attached deposit is less than the minimum storage balance");
            self.registered.insert(who);
            let refund = dep.saturating_sub(STORAGE_MIN);
            if refund.as_yoctonear() > 0 { let _ = Promise::new(env::predecessor_account_id()).transfer(refund); }
        }
        StorageBalance { total: STORAGE_MIN, available: NearToken::from_yoctonear(0) }
    }
    pub fn storage_balance_of(&self, account_id: AccountId) -> Option<StorageBalance> {
        self.registered.contains(&account_id).then(|| StorageBalance { total: STORAGE_MIN, available: NearToken::from_yoctonear(0) })
    }
    pub fn storage_balance_bounds(&self) -> StorageBalanceBounds { StorageBalanceBounds { min: STORAGE_MIN, max: Some(STORAGE_MIN) } }

    // ---------------- bonds and events
    #[payable]
    pub fn deposit_bond(&mut self, amount: U128) {
        assert_one_yocto();
        unwrap_or_panic(self.core.deposit_bond(&caller(), amount.0));
        self.flush();
    }
    #[payable]
    pub fn withdraw_bond(&mut self, amount: U128) {
        assert_one_yocto();
        unwrap_or_panic(self.core.withdraw_bond(&caller(), amount.0));
        self.flush();
    }
    pub fn report_event(&mut self, event_id: String, mag_x10: u32, origin_s: u64) {
        unwrap_or_panic(self.core.report_event(&caller(), &event_id, mag_x10, origin_s, now_s()));
        self.flush();
    }
    pub fn challenge(&mut self, event_id: String) {
        unwrap_or_panic(self.core.challenge(&caller(), &event_id, now_s()));
        self.flush();
    }
    /// side: "real" or "not_real"
    pub fn vote(&mut self, event_id: String, side: String, amount: U128) {
        let real = match side.as_str() { "real" => Some(true), "not_real" => Some(false), _ => None };
        unwrap_or_panic(self.core.vote(&caller(), &event_id, real, amount.0, now_s()));
        self.flush();
    }
    pub fn finalize(&mut self, event_id: String) {
        let minted = unwrap_or_panic(self.core.finalize(&event_id, now_s()));
        if let Some((m, _raw, _clipped)) = minted {
            let parts: Vec<String> = self.core.p.relief.iter().zip(engine::split(m))
                .map(|(a, n)| format!("{{\"owner_id\":\"{}\",\"amount\":\"{}\",\"memo\":\"{}\"}}", a, n, event_id)).collect();
            self.emit_standard("ft_mint", format!("[{}]", parts.join(",")));
        }
        self.flush();
    }
    pub fn claim_vote(&mut self, event_id: String) -> U128 {
        let out = unwrap_or_panic(self.core.claim_vote(&caller(), &event_id));
        self.flush();
        U128(out)
    }

    /// Starter coins for judges and newcomers: once per account, paid from the pool the launcher filled by sending coins to this
    /// contract's own account. Mints nothing and gives nobody any power. An unregistered caller attaches the flat storage deposit (the excess is refunded).
    #[payable]
    pub fn tap(&mut self) {
        let who = env::predecessor_account_id();
        let dep = env::attached_deposit();
        if self.registered.contains(&who) {
            if dep.as_yoctonear() > 0 { let _ = Promise::new(who.clone()).transfer(dep); }
        } else {
            require!(dep >= STORAGE_MIN, "Attach at least 0.00125 NEAR to register for storage");
            self.registered.insert(who.clone());
            let refund = dep.saturating_sub(STORAGE_MIN);
            if refund.as_yoctonear() > 0 { let _ = Promise::new(who.clone()).transfer(refund); }
        }
        unwrap_or_panic(self.core.tap(who.as_str(), env::current_account_id().as_str()));
        self.flush();
    }
    pub fn has_tapped(&self, account_id: AccountId) -> bool { self.core.tapped.contains(account_id.as_str()) }

    // ---------------- views
    pub fn get_params(&self) -> ParamsArg {
        let p = &self.core.p;
        ParamsArg { s0: U128(p.s0), min_mag_x10: p.min_mag_x10, base_ppm: p.base_ppm as u32, max_event_ppm: p.max_event_ppm as u32,
            cooldown_s: p.cooldown_s, week_cap_ppm: p.week_cap_ppm as u32, month_cap_ppm: p.month_cap_ppm as u32, bond: U128(p.bond),
            window_s: p.window_s, vote_s: p.vote_s, slash_pct: p.slash_pct as u32, quorum_ppm: p.quorum_ppm as u32, max_age_s: p.max_age_s, tap_amount: U128(p.tap_amount),
            relief_accounts: Some(p.relief.iter().map(|a| a.parse().unwrap()).collect()) }
    }
    pub fn get_state(&self) -> StateView {
        let now = now_s();
        let (m7, m30, wl, ml) = self.core.state(now);
        StateView { supply: U128(self.core.supply), initial_supply: U128(self.core.p.s0), minted_7d: U128(m7), minted_30d: U128(m30),
            week_left: U128(wl), month_left: U128(ml), tap_pool: U128(self.core.ft_balance_of(env::current_account_id().as_str())),
            open_events: self.core.ev.values().filter(|e| matches!(e.status, Status::Waiting | Status::Challenged)).count() as u32,
            log_len: self.log.len() as u64, now_s: now }
    }
    pub fn get_event(&self, event_id: String) -> Option<EventView> { self.core.ev.get(&event_id).map(|e| self.view(&event_id, e)) }
    pub fn list_events(&self, from: u32, limit: u32) -> Vec<EventView> {
        self.core.ev.iter().skip(from as usize).take(limit.min(100) as usize).map(|(k, e)| self.view(k, e)).collect()
    }
    pub fn get_log(&self, from: u64, limit: u64) -> Vec<String> {
        (from..self.log.len() as u64).take(limit.min(100) as usize).map(|i| self.log.get(i as u32).unwrap().clone()).collect()
    }
    pub fn bond_balance_of(&self, account_id: AccountId) -> U128 { U128(self.core.bond_balance_of(account_id.as_str())) }
}

impl Contract {
    fn view(&self, id: &str, e: &engine::Ev) -> EventView {
        let sum = |real: bool| U128(e.votes.values().filter(|v| v.0 == real).map(|v| v.1).sum());
        EventView { event_id: id.to_string(), mag_x10: e.mag_x10, origin_s: e.origin_s, reporter: e.reporter.parse().unwrap(),
            reported_at: e.reported_at, status: e.status.as_str().to_string(), challenger: e.challenger.as_ref().map(|c| c.parse().unwrap()),
            challenged_at: e.challenged_at, window_ends: e.reported_at + self.core.p.window_s,
            vote_ends: e.challenger.as_ref().map(|_| e.challenged_at + self.core.p.vote_s),
            real_locked: sum(true), not_real_locked: sum(false), minted: U128(e.minted), clipped: e.clipped, pot: U128(e.pot) }
    }
    fn do_transfer(&mut self, sender: &AccountId, receiver: &AccountId, amount: u128, memo: Option<String>) {
        require!(sender != receiver, "Sender and receiver should be different");
        require!(amount > 0, "The amount should be a positive number");
        require!(self.registered.contains(receiver), "The account is not registered");
        unwrap_or_panic(self.core.ft_transfer(sender.as_str(), receiver.as_str(), amount));
        self.emit_standard("ft_transfer", format!("[{{\"old_owner_id\":\"{}\",\"new_owner_id\":\"{}\",\"amount\":\"{}\"{}}}]", sender, receiver, amount,
            memo.map(|m| format!(",\"memo\":{}", near_sdk::serde_json::to_string(&m).unwrap())).unwrap_or_default()));
    }
    fn emit_standard(&self, event: &str, data: String) {
        env::log_str(&format!("EVENT_JSON:{{\"standard\":\"nep141\",\"version\":\"1.0.0\",\"event\":\"{}\",\"data\":{}}}", event, data));
    }
    /// Append the core's pending log lines to the on-chain log and emit them as NEP-297 events.
    fn flush(&mut self) {
        for (event, data) in std::mem::take(&mut self.core.pending_log) {
            let line = format!("{{\"event\":\"{}\",\"data\":{}}}", event, data);
            env::log_str(&format!("EVENT_JSON:{{\"standard\":\"tremor\",\"version\":\"1.0.0\",\"event\":\"{}\",\"data\":[{}]}}", event, data));
            self.log.push(line);
        }
    }
}
