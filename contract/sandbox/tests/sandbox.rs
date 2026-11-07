//! near-workspaces sandbox tests (RUN: `cargo near build non-reproducible-wasm --no-abi` in contract/ first).
//! Windows are 6 s / 10 s; amounts follow RULES.md (6 decimals).
use near_workspaces::{network::Sandbox, types::{Gas, NearToken}, Account, Contract, Worker};
use serde_json::{json, Value};
use std::time::Duration;

const U: u128 = 1_000_000;
const Y1: NearToken = NearToken::from_yoctonear(1);
const NONE: NearToken = NearToken::from_yoctonear(0);

struct Env { w: Worker<Sandbox>, c: Contract, root: Account, acc: Vec<Account>, relief: Vec<Account> }
impl Env {
    fn who(&self, n: &str) -> &Account { self.acc.iter().find(|a| a.id().as_str().starts_with(&format!("{n}."))).unwrap() }
}

fn params(over: Value) -> Value {
    let mut p = json!({"s0": (1_000_000 * U).to_string(), "min_mag_x10": 60, "base_ppm": 5000, "max_event_ppm": 15000, "cooldown_s": 86400,
        "week_cap_ppm": 15000, "month_cap_ppm": 50000, "bond": (1000 * U).to_string(), "window_s": 6, "vote_s": 10, "slash_pct": 20,
        "quorum_ppm": 2000, "max_age_s": 5_184_000, "relief_accounts": null});
    for (k, v) in over.as_object().unwrap() { p[k] = v.clone(); }
    p
}

/// Deploys, inits (launcher = ada), registers and funds ada, bayo, chidi, dayo, ngo and deposits bonds.
async fn setup(over: Value) -> anyhow::Result<Env> {
    let w = near_workspaces::sandbox().await?;
    let wasm = std::fs::read(concat!(env!("CARGO_MANIFEST_DIR"), "/../target/near/tremor.wasm"))?;
    let root = w.root_account()?;
    async fn mk(root: &Account, n: &str, near: u128) -> anyhow::Result<Account> {
        Ok(root.create_subaccount(n).initial_balance(NearToken::from_near(near)).transact().await?.into_result()?)
    }
    let c = mk(&root, "tremor", 30).await?.deploy(&wasm).await?.into_result()?;
    let mut acc = vec![];
    for n in ["ada", "bayo", "chidi", "dayo", "ngo"] { acc.push(mk(&root, n, 10).await?); }
    let mut relief = vec![];
    for i in 1..=5 { relief.push(root.create_subaccount(&format!("relief{i}")).initial_balance(NearToken::from_near(1)).transact().await?.into_result()?); }
    let ids: Vec<String> = relief.iter().map(|a| a.id().to_string()).collect();
    root.call(c.id(), "new").args_json(json!({"params": params(over), "relief_accounts": ids, "launcher": acc[0].id()})).max_gas().transact().await?.into_result()?;
    let e = Env { w, c, root, acc, relief };
    for n in ["bayo", "chidi", "dayo", "ngo"] {
        e.who(n).call(e.c.id(), "storage_deposit").args_json(json!({})).deposit(NearToken::from_millinear(2)).max_gas().transact().await?.into_result()?;
        e.who("ada").call(e.c.id(), "ft_transfer").args_json(json!({"receiver_id": e.who(n).id(), "amount": (100_000 * U).to_string()})).deposit(Y1).max_gas().transact().await?.into_result()?;
    }
    for n in ["ada", "bayo", "chidi", "dayo", "ngo"] { e.call(n, "deposit_bond", json!({"amount": (20_000 * U).to_string()}), Y1).await?.into_result()?; }
    Ok(e)
}

impl Env {
    async fn call(&self, who: &str, m: &str, args: Value, dep: NearToken) -> anyhow::Result<near_workspaces::result::ExecutionFinalResult> {
        Ok(self.who(who).call(self.c.id(), m).args_json(args).deposit(dep).max_gas().transact().await?)
    }
    async fn ok(&self, who: &str, m: &str, args: Value) -> anyhow::Result<Gas> {
        let r = self.call(who, m, args, NONE).await?; let g = r.total_gas_burnt; r.into_result()?; Ok(g)
    }
    async fn fails(&self, who: &str, m: &str, args: Value, needle: &str) -> anyhow::Result<()> {
        let r = self.call(who, m, args, NONE).await?;
        assert!(r.is_failure(), "{m} should have failed");
        let msg = format!("{:?}", r.into_result().err().unwrap());
        assert!(msg.contains(needle), "expected '{needle}' in: {msg}");
        Ok(())
    }
    async fn view(&self, m: &str, args: Value) -> anyhow::Result<Value> { Ok(self.c.view(m).args_json(args).await?.json()?) }
    async fn now(&self) -> u64 { self.view("get_state", json!({})).await.unwrap()["now_s"].as_u64().unwrap() }
    async fn bal(&self, who: &str) -> u128 { self.view("bond_balance_of", json!({"account_id": self.who(who).id()})).await.unwrap().as_str().unwrap().parse().unwrap() }
    async fn tok(&self, id: &str) -> u128 { self.view("ft_balance_of", json!({"account_id": id})).await.unwrap().as_str().unwrap().parse().unwrap() }
    async fn supply(&self) -> u128 { self.view("ft_total_supply", json!({})).await.unwrap().as_str().unwrap().parse().unwrap() }
    async fn report(&self, who: &str, id: &str, mag: u32) -> anyhow::Result<Gas> { let n = self.now().await; self.ok(who, "report_event", json!({"event_id": id, "mag_x10": mag, "origin_s": n - 5})).await }
    async fn wait(&self, s: u64) { tokio::time::sleep(Duration::from_secs(s)).await; self.w.fast_forward(2).await.unwrap(); }
}

#[tokio::test]
async fn init_once_and_no_parameter_methods() -> anyhow::Result<()> {
    let e = setup(json!({})).await?;
    let r = e.root.call(e.c.id(), "new").args_json(json!({"params": params(json!({})), "relief_accounts": e.relief.iter().map(|a| a.id().to_string()).collect::<Vec<_>>(), "launcher": e.who("ada").id()})).max_gas().transact().await?;
    assert!(r.is_failure(), "second new must panic");
    let p = e.view("get_params", json!({})).await?;
    assert_eq!(p["window_s"], 6); assert_eq!(p["relief_accounts"].as_array().unwrap().len(), 5);
    for m in ["set_params", "update_params", "set_owner", "owner_id", "upgrade", "update_contract", "set_window", "set_caps", "set_relief", "mint", "ft_mint", "migrate"] {
        let r = e.call("ada", m, json!({}), NONE).await?;
        assert!(r.is_failure(), "method {m} must not exist");
    }
    Ok(())
}

#[tokio::test]
async fn bad_reports_rejected() -> anyhow::Result<()> {
    let e = setup(json!({})).await?; let n = e.now().await;
    e.fails("dayo", "report_event", json!({"event_id":"a","mag_x10":59,"origin_s":n-5}), "magnitude").await?;
    e.fails("dayo", "report_event", json!({"event_id":"a","mag_x10":101,"origin_s":n-5}), "magnitude").await?;
    e.fails("dayo", "report_event", json!({"event_id":"a","mag_x10":65,"origin_s":n+1000}), "future").await?;
    e.fails("dayo", "report_event", json!({"event_id":"a","mag_x10":65,"origin_s":n-6_000_000}), "too old").await?;
    e.fails("dayo", "report_event", json!({"event_id":"","mag_x10":65,"origin_s":n-5}), "bad event id").await?;
    e.fails("dayo", "report_event", json!({"event_id":"x".repeat(33),"mag_x10":65,"origin_s":n-5}), "bad event id").await?;
    e.report("dayo", "dup1", 65).await?;
    e.fails("bayo", "report_event", json!({"event_id":"dup1","mag_x10":65,"origin_s":n-5}), "already exists").await?;
    assert_eq!(e.bal("dayo").await, 19_000 * U); // only the one good report locked a bond
    Ok(())
}

#[tokio::test]
async fn unchallenged_event_counts_and_mints_to_five() -> anyhow::Result<()> {
    let e = setup(json!({})).await?;
    e.report("dayo", "ok1", 60).await?;
    e.fails("bayo", "finalize", json!({"event_id":"ok1"}), "window still open").await?;
    e.wait(7).await;
    let g = e.ok("bayo", "finalize", json!({"event_id":"ok1"})).await?;
    eprintln!("GAS finalize (mint to 5): {} Tgas", g.as_gas() / 1_000_000_000_000);
    assert_eq!(e.supply().await, 1_005_000 * U);
    for r in &e.relief { assert_eq!(e.tok(r.id().as_str()).await, 1000 * U); }
    assert_eq!(e.bal("dayo").await, 20_000 * U); // bond returned
    e.fails("bayo", "finalize", json!({"event_id":"ok1"}), "already final").await?;
    let log = e.view("get_log", json!({"from":0,"limit":10})).await?;
    assert!(log.as_array().unwrap().iter().any(|l| l.as_str().unwrap().contains("event_counted")));
    Ok(())
}

async fn dispute(e: &Env, id: &str, votes: &[(&str, &str, u128)]) -> anyhow::Result<()> {
    e.report("dayo", id, 60).await?;
    e.ok("ngo", "challenge", json!({"event_id": id})).await?;
    e.fails("dayo", "challenge", json!({"event_id": id}), "window closed").await?;
    for (who, side, n) in votes { e.ok(who, "vote", json!({"event_id": id, "side": side, "amount": (n * U).to_string()})).await?; }
    e.fails("ada", "vote", json!({"event_id": id, "side": "real", "amount": "1"}), "already voted").await.ok();
    e.fails("bayo", "finalize", json!({"event_id": id}), "vote still open").await?;
    e.wait(11).await;
    Ok(())
}

#[tokio::test]
async fn gv2_challenge_survives() -> anyhow::Result<()> {
    // Quorum in this test: 0.2% of supply (about 2,000 TREM). Ada 3,000 real; Bayo 1,000 and Chidi 500 not real.
    let e = setup(json!({})).await?;
    let before: [u128; 3] = [e.bal("ada").await, e.bal("bayo").await, e.bal("chidi").await];
    dispute(&e, "gv2", &[("ada", "real", 3000), ("bayo", "not_real", 1000), ("chidi", "not_real", 500)]).await?;
    let g = e.ok("bayo", "finalize", json!({"event_id":"gv2"})).await?;
    eprintln!("GAS finalize after vote: {} Tgas", g.as_gas() / 1_000_000_000_000);
    assert!(e.supply().await > 1_000_000 * U, "real wins, so it mints");
    let mut gas = 0;
    for w in ["ada", "bayo", "chidi"] { gas = gas.max(e.ok(w, "claim_vote", json!({"event_id":"gv2"})).await?.as_gas()); }
    eprintln!("GAS claim_vote (max): {} Tgas", gas / 1_000_000_000_000);
    assert_eq!(e.bal("ada").await, before[0] + 1300 * U, "Ada gets the whole 1,300 pot");
    assert_eq!(e.bal("bayo").await, before[1] - 200 * U);
    assert_eq!(e.bal("chidi").await, before[2] - 100 * U);
    assert_eq!(e.bal("dayo").await, 20_000 * U, "reporter bond returned");
    assert_eq!(e.bal("ngo").await, 19_000 * U, "challenger bond forfeited");
    e.fails("ada", "claim_vote", json!({"event_id":"gv2"}), "nothing to claim").await?;
    Ok(())
}

#[tokio::test]
async fn gv3_too_little_turnout() -> anyhow::Result<()> {
    let e = setup(json!({})).await?;
    dispute(&e, "gv3", &[("ada", "real", 1000)]).await?;
    e.ok("bayo", "finalize", json!({"event_id":"gv3"})).await?;
    assert_eq!(e.supply().await, 1_000_000 * U, "no mint");
    e.ok("ada", "claim_vote", json!({"event_id":"gv3"})).await?;
    for w in ["ada", "dayo", "ngo"] { assert_eq!(e.bal(w).await, 20_000 * U, "{w} gets everything back"); }
    let ev = e.view("get_event", json!({"event_id":"gv3"})).await?; assert_eq!(ev["status"], "rejected");
    Ok(())
}

#[tokio::test]
async fn caps_clip_a_mint() -> anyhow::Result<()> {
    // Base 1% (2% at M7.0) is cut to the 1.5% per-event ceiling: 15,000 TREM. The weekly cap (1.5% of supply)
    // then leaves floor(1,015,000 * 1.5%) - 15,000 = 225 TREM for the second event, which is clipped.
    let e = setup(json!({"base_ppm": 10000, "cooldown_s": 3})).await?;
    e.report("dayo", "c1", 70).await?; e.wait(7).await; e.ok("bayo", "finalize", json!({"event_id":"c1"})).await?;
    assert_eq!(e.supply().await, 1_015_000 * U);
    let st = e.view("get_state", json!({})).await?; assert_eq!(st["week_left"], (225 * U).to_string());
    e.report("dayo", "c2", 70).await?; e.wait(7).await; e.ok("bayo", "finalize", json!({"event_id":"c2"})).await?;
    assert_eq!(e.supply().await, 1_015_225 * U, "the second event is cut to what the week still allows");
    let ev = e.view("get_event", json!({"event_id":"c2"})).await?; assert_eq!(ev["status"], "counted"); assert_eq!(ev["clipped"], true);
    // the allowance is recomputed on the grown supply: 1.5% of 1,015,225 = 15,228.375, minus 15,225 already minted
    assert_eq!(e.view("get_state", json!({})).await?["week_left"], "3375000");
    Ok(())
}

#[tokio::test]
async fn gas_and_storage_with_many_open_events() -> anyhow::Result<()> {
    let e = setup(json!({"window_s": 600})).await?;
    let used = |e: &Env| { let c = e.c.id().clone(); let w = e.w.clone(); async move { w.view_account(&c).await.unwrap().storage_usage } };
    let s0 = used(&e).await; let mut first = 0; let mut last = 0;
    for i in 0..64u32 {
        let who = ["dayo", "bayo", "chidi", "ngo"][(i % 4) as usize];
        let g = e.report(who, &format!("ev-{i:04}"), 60).await?.as_gas();
        if i == 0 { first = g; } last = g;
    }
    let s1 = used(&e).await;
    eprintln!("STORAGE per open event: {} bytes (64 events)", (s1 - s0) / 64);
    eprintln!("GAS report_event with 0 open: {} Tgas ; with 63 open: {} Tgas", first / 1_000_000_000_000, last / 1_000_000_000_000);
    e.fails("ada", "report_event", json!({"event_id":"overflow","mag_x10":60,"origin_s": e.now().await - 5}), "too many open events").await?;
    assert!(last < 250_000_000_000_000, "report must fit in 250 Tgas at the open-event limit");
    Ok(())
}
