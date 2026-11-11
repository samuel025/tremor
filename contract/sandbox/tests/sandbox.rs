//! near-workspaces sandbox tests (RUN: `cargo near build non-reproducible-wasm --no-abi` in contract/ first).
//! Amounts follow RULES.md (6 decimals). Five fixed publisher accounts (bot1..bot5); an event counts when 3 of them attest the same record.
use near_workspaces::{network::Sandbox, types::{Gas, NearToken}, Account, Contract, Worker};
use serde_json::{json, Value};

const U: u128 = 1_000_000;
const Y1: NearToken = NearToken::from_yoctonear(1);
const NONE: NearToken = NearToken::from_yoctonear(0);

struct Env { w: Worker<Sandbox>, c: Contract, root: Account, acc: Vec<Account>, relief: Vec<Account> }
impl Env {
    fn who(&self, n: &str) -> &Account { self.acc.iter().find(|a| a.id().as_str().starts_with(&format!("{n}."))).unwrap() }
}

fn params(over: Value) -> Value {
    let mut p = json!({"s0": (1_000_000 * U).to_string(), "min_mag_x10": 60, "min_alert": 2, "base_ppm": 5000, "max_event_ppm": 15000, "cooldown_s": 86400,
        "week_cap_ppm": 15000, "month_cap_ppm": 50000, "min_age_s": 0, "max_age_s": 5_184_000, "max_open": 64, "max_claims": 32, "claim_wait_s": 3600,
        "threshold": 3, "match_ppm": 0, "match_day_ppm": 0, "match_month_ppm": 0, "match_account_max": "0", "tap_amount": "0", "publisher_accounts": null, "relief_accounts": null});
    for (k, v) in over.as_object().unwrap() { p[k] = v.clone(); }
    p
}

/// Deploys and inits (launcher = ada; publishers bot1..bot5; five relief accounts) and registers judge and ada.
async fn setup(over: Value) -> anyhow::Result<Env> {
    let w = near_workspaces::sandbox().await?;
    let wasm = std::fs::read(concat!(env!("CARGO_MANIFEST_DIR"), "/../target/near/tremor.wasm"))?;
    let root = w.root_account()?;
    async fn mk(root: &Account, n: &str, near: u128) -> anyhow::Result<Account> {
        Ok(root.create_subaccount(n).initial_balance(NearToken::from_near(near)).transact().await?.into_result()?)
    }
    let c = mk(&root, "tremor", 30).await?.deploy(&wasm).await?.into_result()?;
    let mut acc = vec![];
    for n in ["ada", "judge", "liar", "bot1", "bot2", "bot3", "bot4", "bot5"] { acc.push(mk(&root, n, 10).await?); }
    let mut relief = vec![];
    for i in 1..=5 { relief.push(root.create_subaccount(&format!("relief{i}")).initial_balance(NearToken::from_near(1)).transact().await?.into_result()?); }
    let pubs: Vec<String> = (1..=5).map(|i| acc.iter().find(|a| a.id().as_str().starts_with(&format!("bot{i}."))).unwrap().id().to_string()).collect();
    let rel: Vec<String> = relief.iter().map(|a| a.id().to_string()).collect();
    root.call(c.id(), "new").args_json(json!({"params": params(over), "publisher_accounts": pubs, "relief_accounts": rel, "launcher": acc[0].id()})).max_gas().transact().await?.into_result()?;
    Ok(Env { w, c, root, acc, relief })
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
        assert!(r.is_failure(), "{m} by {who} should have failed");
        let msg = format!("{:?}", r.into_result().err().unwrap());
        assert!(msg.contains(needle), "expected '{needle}' in: {msg}");
        Ok(())
    }
    async fn view(&self, m: &str, args: Value) -> anyhow::Result<Value> { Ok(self.c.view(m).args_json(args).await?.json()?) }
    async fn now(&self) -> u64 { self.view("get_state", json!({})).await.unwrap()["now_s"].as_u64().unwrap() }
    async fn tok(&self, id: &str) -> u128 { self.view("ft_balance_of", json!({"account_id": id})).await.unwrap().as_str().unwrap().parse().unwrap() }
    async fn supply(&self) -> u128 { self.view("ft_total_supply", json!({})).await.unwrap().as_str().unwrap().parse().unwrap() }
    /// publishers `bots` (1-based) attest the same record
    async fn attest(&self, bots: &[u32], id: &str, mag: u32, origin: u64) -> anyhow::Result<Gas> {
        let mut g = Gas::from_gas(0);
        for b in bots { g = self.ok(&format!("bot{b}"), "attest", json!({"event_id": id, "mag_x10": mag, "origin_s": origin, "alert": 2})).await?; }
        Ok(g)
    }
}

#[tokio::test]
async fn init_once_and_nobody_can_change_anything() -> anyhow::Result<()> {
    let e = setup(json!({})).await?;
    let r = e.root.call(e.c.id(), "new").args_json(json!({"params": params(json!({})), "publisher_accounts": [], "relief_accounts": [], "launcher": e.who("ada").id()})).max_gas().transact().await?;
    assert!(r.is_failure(), "second new must panic");
    let p = e.view("get_params", json!({})).await?;
    assert_eq!(p["threshold"], 3); assert_eq!(p["publisher_accounts"].as_array().unwrap().len(), 5); assert_eq!(p["relief_accounts"].as_array().unwrap().len(), 5);
    // no method exists to change parameters, publishers or recipients, to mint, to own, to upgrade, or the removed deposit / challenge / vote methods
    for m in ["set_params", "set_publishers", "add_publisher", "remove_publisher", "set_threshold", "set_relief", "set_owner", "owner_id", "upgrade", "update_contract",
              "migrate", "mint", "ft_mint", "report_event", "challenge", "vote", "claim_vote", "finalize", "deposit_bond", "withdraw_bond"] {
        let r = e.call("ada", m, json!({}), NONE).await?;
        assert!(r.is_failure(), "method {m} must not exist");
    }
    Ok(())
}

#[tokio::test]
async fn only_publishers_attest_and_bad_records_are_refused() -> anyhow::Result<()> {
    let e = setup(json!({"min_age_s": 3600})).await?; let n = e.now().await; let old = n - 7200;
    e.fails("judge", "attest", json!({"event_id": "a", "mag_x10": 65, "origin_s": old, "alert": 2}), "not a publisher").await?;
    e.fails("ada", "attest", json!({"event_id": "a", "mag_x10": 65, "origin_s": old, "alert": 2}), "not a publisher").await?; // not even the launcher
    e.fails("bot1", "attest", json!({"event_id": "a", "mag_x10": 59, "origin_s": old, "alert": 2}), "magnitude").await?;
    e.fails("bot1", "attest", json!({"event_id": "a", "mag_x10": 101, "origin_s": old, "alert": 2}), "magnitude").await?;
    e.fails("bot1", "attest", json!({"event_id": "a", "mag_x10": 65, "origin_s": n + 1000, "alert": 2}), "future").await?;
    e.fails("bot1", "attest", json!({"event_id": "a", "mag_x10": 65, "origin_s": n - 6_000_000, "alert": 2}), "too old").await?;
    e.fails("bot1", "attest", json!({"event_id": "a", "mag_x10": 65, "origin_s": n - 5, "alert": 2}), "too recent").await?; // finality delay (min_age_s)
    e.fails("bot1", "attest", json!({"event_id": "", "mag_x10": 65, "origin_s": old, "alert": 2}), "bad event id").await?;
    e.fails("bot1", "attest", json!({"event_id": "x".repeat(33), "mag_x10": 65, "origin_s": old, "alert": 2}), "bad event id").await?;
    assert_eq!(e.view("get_state", json!({})).await?["pending_events"], 0, "none of the refused records left anything behind");
    Ok(())
}

#[tokio::test]
async fn three_of_five_mint_and_split() -> anyhow::Result<()> {
    let e = setup(json!({})).await?; let o = e.now().await - 60;
    e.attest(&[1, 2], "q1", 60, o).await?;
    assert_eq!(e.supply().await, 1_000_000 * U, "two of five is not enough");
    assert_eq!(e.view("get_event", json!({"event_id": "q1"})).await?["status"], "pending");
    let g = e.attest(&[3], "q1", 60, o).await?;
    eprintln!("GAS attest that mints (3rd of 5): {} Tgas", g.as_gas() / 1_000_000_000_000);
    assert_eq!(e.supply().await, 1_005_000 * U);
    for r in &e.relief { assert_eq!(e.tok(r.id().as_str()).await, 1000 * U); }
    e.fails("bot4", "attest", json!({"event_id": "q1", "mag_x10": 60, "origin_s": o, "alert": 2}), "already counted").await?;
    let log = e.view("get_log", json!({"from": 0, "limit": 20})).await?;
    let text = log.as_array().unwrap().iter().map(|l| l.as_str().unwrap()).collect::<Vec<_>>().join("\n");
    assert!(text.contains("attested") && text.contains("event_counted"));
    Ok(())
}

#[tokio::test]
async fn only_quakes_with_expected_impact_count() -> anyhow::Result<()> {
    // GV-6 on a simulated network. alert: 1 green, 2 yellow, 3 orange, 4 red; the bar is yellow.
    let e = setup(json!({})).await?; let o = e.now().await - 60;
    let rec = |id: &str, alert: u32| json!({"event_id": id, "mag_x10": 60, "origin_s": o, "alert": alert});
    e.fails("bot1", "attest", rec("g1", 1), "expected impact too low").await?;
    e.fails("judge", "submit_claim", rec("g2", 1), "expected impact too low").await?;
    e.fails("bot1", "attest", rec("g3", 0), "alert level out of range").await?;
    e.fails("bot1", "attest", rec("g3", 5), "alert level out of range").await?;
    assert!(e.view("get_event", json!({"event_id": "g1"})).await?.is_null(), "a refused record leaves no trace");
    for (b, a) in [("bot1", 3), ("bot2", 3), ("bot3", 2)] { e.ok(b, "attest", rec("a2", a)).await?; }
    assert_eq!(e.supply().await, 1_000_000 * U, "two orange and one yellow are different records");
    e.ok("bot4", "attest", rec("a2", 3)).await?;
    assert_eq!(e.supply().await, 1_005_000 * U);
    let ev = e.view("get_event", json!({"event_id": "a2"})).await?;
    assert_eq!((ev["status"].as_str(), ev["alert"].as_u64()), (Some("counted"), Some(3)));
    assert_eq!(e.view("get_params", json!({})).await?["min_alert"], 2);
    Ok(())
}

#[tokio::test]
async fn disagreement_and_repeats_do_not_mint() -> anyhow::Result<()> {
    let e = setup(json!({})).await?; let o = e.now().await - 60;
    e.attest(&[1, 2], "d1", 60, o).await?;
    e.attest(&[3], "d1", 61, o).await?; // a different magnitude: a separate version with one attestation
    assert_eq!(e.supply().await, 1_000_000 * U);
    e.fails("bot3", "attest", json!({"event_id": "d1", "mag_x10": 60, "origin_s": o, "alert": 2}), "already attested").await?; // one attestation per publisher
    e.attest(&[4], "d1", 60, o).await?; // the third matching one counts
    assert_eq!(e.supply().await, 1_005_000 * U);
    let ev = e.view("get_event", json!({"event_id": "d1"})).await?; assert_eq!(ev["mag_x10"], 60);
    Ok(())
}

#[tokio::test]
async fn visitor_claims_need_bots_to_confirm_and_fakes_never_mint() -> anyhow::Result<()> {
    let e = setup(json!({"max_claims": 2})).await?; let o = e.now().await - 60;
    e.ok("judge", "submit_claim", json!({"event_id": "real-1", "mag_x10": 63, "origin_s": o, "alert": 2})).await?;
    e.ok("liar", "submit_claim", json!({"event_id": "fake-1", "mag_x10": 74, "origin_s": o, "alert": 2})).await?;
    e.fails("judge", "submit_claim", json!({"event_id": "real-2", "mag_x10": 63, "origin_s": o, "alert": 2}), "already have an open claim").await?;
    e.fails("bot1", "submit_claim", json!({"event_id": "real-3", "mag_x10": 63, "origin_s": o, "alert": 2}), "too many open claims").await?; // limit of 2 open claims
    e.fails("judge", "submit_claim", json!({"event_id": "real-1", "mag_x10": 63, "origin_s": o, "alert": 2}), "already exists").await?;
    assert_eq!(e.supply().await, 1_000_000 * U, "a claim alone mints nothing");
    // the bots found real-1 in USGS and confirm it; nobody finds fake-1
    e.attest(&[1, 2, 3], "real-1", 63, o).await?;
    assert!(e.supply().await > 1_000_000 * U);
    let real = e.view("get_event", json!({"event_id": "real-1"})).await?; assert_eq!(real["status"], "counted"); assert_eq!(real["claimer"], e.who("judge").id().as_str());
    let fake = e.view("get_event", json!({"event_id": "fake-1"})).await?; assert_eq!(fake["status"], "pending"); assert_eq!(fake["attestations"], 0);
    // a bot-started event is not blocked by claims: the limits are separate
    e.attest(&[1], "bot-started", 65, o).await?;
    Ok(())
}

#[tokio::test]
async fn caps_clip_a_mint() -> anyhow::Result<()> {
    // Base 1% (2% at M7.0) is cut to the 1.5% per-event ceiling: 15,000 TREM. The weekly cap (1.5% of supply)
    // then leaves floor(1,015,000 * 1.5%) - 15,000 = 225 TREM for the second event, which is clipped.
    let e = setup(json!({"base_ppm": 10000, "cooldown_s": 3})).await?; let o = e.now().await - 60;
    e.attest(&[1, 2, 3], "c1", 70, o).await?;
    assert_eq!(e.supply().await, 1_015_000 * U);
    assert_eq!(e.view("get_state", json!({})).await?["week_left"], (225 * U).to_string());
    e.attest(&[1, 2, 3], "c2", 70, o + 30).await?;
    assert_eq!(e.supply().await, 1_015_225 * U, "the second event is cut to what the week still allows");
    let ev = e.view("get_event", json!({"event_id": "c2"})).await?; assert_eq!(ev["status"], "counted"); assert_eq!(ev["clipped"], true);
    assert_eq!(e.view("get_state", json!({})).await?["week_left"], "3375000");
    Ok(())
}

#[tokio::test]
async fn tap_gives_starter_coins_once_and_mints_nothing() -> anyhow::Result<()> {
    let e = setup(json!({"tap_amount": (500 * U).to_string()})).await?;
    e.who("ada").call(e.c.id(), "ft_transfer").args_json(json!({"receiver_id": e.c.id(), "amount": (1000 * U).to_string()})).deposit(Y1).max_gas().transact().await?.into_result()?;
    assert_eq!(e.view("get_state", json!({})).await?["tap_pool"], (1000 * U).to_string());
    let mut judges = vec![];
    for n in ["judge1", "judge2", "judge3"] { judges.push(e.root.create_subaccount(n).initial_balance(NearToken::from_near(2)).transact().await?.into_result()?); }
    let r = judges[0].call(e.c.id(), "tap").max_gas().transact().await?; assert!(r.is_failure(), "an unregistered account must attach the storage deposit");
    judges[0].call(e.c.id(), "tap").deposit(NearToken::from_millinear(2)).max_gas().transact().await?.into_result()?;
    assert_eq!(e.tok(judges[0].id().as_str()).await, 500 * U);
    assert!(e.view("has_tapped", json!({"account_id": judges[0].id()})).await?.as_bool().unwrap());
    let again = judges[0].call(e.c.id(), "tap").max_gas().transact().await?; assert!(again.is_failure(), "second tap must fail");
    judges[1].call(e.c.id(), "tap").deposit(NearToken::from_millinear(2)).max_gas().transact().await?.into_result()?;
    let empty = judges[2].call(e.c.id(), "tap").deposit(NearToken::from_millinear(2)).max_gas().transact().await?; assert!(empty.is_failure(), "pool is empty");
    assert_eq!(e.supply().await, 1_000_000 * U, "the tap mints nothing");
    Ok(())
}

#[tokio::test]
async fn give_moves_own_coins_to_relief_and_mints_nothing() -> anyhow::Result<()> {
    // GV-4 on a simulated network
    let e = setup(json!({})).await?;
    let no_yocto = e.call("ada", "give", json!({"amount": "12000003"}), NONE).await?; assert!(no_yocto.is_failure(), "give needs one yoctoNEAR, like a transfer");
    let r = e.call("ada", "give", json!({"amount": "12000003"}), Y1).await?; let gas = r.total_gas_burnt; r.into_result()?;
    eprintln!("MEASURE give: {} Tgas", gas.as_tgas());
    e.call("ada", "give", json!({"amount": (1 * U).to_string()}), Y1).await?.into_result()?;
    assert_eq!(e.tok(e.relief[0].id().as_str()).await, 2_600_003); assert_eq!(e.tok(e.relief[4].id().as_str()).await, 2_600_000);
    assert_eq!(e.view("given_of", json!({"account_id": e.who("ada").id()})).await?, "13000003");
    let empty = e.call("judge", "give", json!({"amount": "1"}), Y1).await?; assert!(empty.is_failure(), "an account with no coins cannot give");
    let zero = e.call("ada", "give", json!({"amount": "0"}), Y1).await?; assert!(zero.is_failure());
    let rel = e.relief[0].call(e.c.id(), "give").args_json(json!({"amount": "1"})).deposit(Y1).gas(Gas::from_tgas(30)).transact().await?; assert!(rel.is_failure(), "a relief account cannot give");
    let st = e.view("get_state", json!({})).await?;
    assert_eq!((st["given_total"].as_str(), st["givers"].as_u64()), (Some("13000003"), Some(1)));
    assert_eq!(e.view("list_givers", json!({"from": 0, "limit": 10})).await?[0]["given"], "13000003");
    assert_eq!(e.supply().await, 1_000_000 * U, "giving mints nothing");
    // a quake after the gifts mints exactly what it would have without them
    let o = e.now().await - 60; e.attest(&[1, 2, 3], "E1", 60, o).await?;
    assert_eq!(e.supply().await, 1_005_000 * U);
    assert_eq!(e.tok(e.relief[1].id().as_str()).await, 1_002_600_000);
    Ok(())
}

#[tokio::test]
async fn donation_match_tops_up_gifts_from_the_reserve_and_creates_nothing() -> anyhow::Result<()> {
    // GV-5 on a simulated network (the sandbox cannot jump days, so the daily and 30-day budgets are checked on the same engine code by
    // the conformance test and GV-7/GV-8; here: the methods are wired, the reserve is drained only by gifts, and the supply never moves).
    let e = setup(json!({"match_ppm": 100000, "match_day_ppm": 5000, "match_month_ppm": 20000, "match_account_max": (10_000 * U).to_string()})).await?;
    let prm = e.view("get_params", json!({})).await?;
    assert_eq!((&prm["match_ppm"], &prm["match_day_ppm"], &prm["match_month_ppm"], &prm["match_account_max"]), (&json!(100000), &json!(5000), &json!(20000), &json!((10_000 * U).to_string())));
    let no_yocto = e.call("ada", "fund_match", json!({"amount": (50_000 * U).to_string()}), NONE).await?; assert!(no_yocto.is_failure(), "funding needs one yoctoNEAR, like a transfer");
    e.call("ada", "fund_match", json!({"amount": (50_000 * U).to_string()}), Y1).await?.into_result()?;
    let st = e.view("get_state", json!({})).await?;
    assert_eq!((st["reserve"].as_str(), st["funded_total"].as_str(), st["supply"].as_str()), (Some((50_000 * U).to_string().as_str()), Some((50_000 * U).to_string().as_str()), Some((1_000_000 * U).to_string().as_str())));
    assert_eq!(e.tok(e.who("ada").id().as_str()).await, 950_000 * U);
    let rel = e.relief[0].call(e.c.id(), "fund_match").args_json(json!({"amount": "1"})).deposit(Y1).gas(Gas::from_tgas(30)).transact().await?; assert!(rel.is_failure(), "a relief account cannot fund the reserve");
    assert_eq!(e.view("match_preview", json!({"account_id": e.who("ada").id(), "amount": (1_000 * U).to_string()})).await?, (100 * U).to_string());
    let r = e.call("ada", "give", json!({"amount": (1_000 * U).to_string()}), Y1).await?; let gas = r.total_gas_burnt; r.into_result()?;
    eprintln!("MEASURE give with a match: {} Tgas", gas.as_tgas());
    assert_eq!(e.tok(e.relief[0].id().as_str()).await, 220 * U);
    assert_eq!(e.tok(e.relief[4].id().as_str()).await, 220 * U);
    let st = e.view("get_state", json!({})).await?;
    assert_eq!((st["reserve"].as_str(), st["matched_total"].as_str(), st["given_total"].as_str()), (Some((49_900 * U).to_string().as_str()), Some((100 * U).to_string().as_str()), Some((1_000 * U).to_string().as_str())));
    assert_eq!(e.view("matched_of", json!({"account_id": e.who("ada").id()})).await?, (100 * U).to_string());
    assert_eq!(e.supply().await, 1_000_000 * U, "matching creates no coins");
    assert!(e.view("get_log", json!({"from": 0, "limit": 10})).await?.as_array().unwrap().iter().any(|l| l.as_str().unwrap().contains("\"event\":\"gave\"") && l.as_str().unwrap().contains("\"matched\":\"100000000\"")), "the log records the match");
    // a quake still mints exactly as before
    let o = e.now().await - 60; e.attest(&[1, 2, 3], "E1", 60, o).await?;
    assert_eq!(e.supply().await, 1_005_000 * U);
    Ok(())
}

#[tokio::test]
async fn gas_and_storage_with_many_pending_events() -> anyhow::Result<()> {
    let e = setup(json!({"max_open": 64})).await?; let o = e.now().await - 60;
    let used = |e: &Env| { let c = e.c.id().clone(); let w = e.w.clone(); async move { w.view_account(&c).await.unwrap().storage_usage } };
    let s0 = used(&e).await; let mut first = 0; let mut last = 0;
    for i in 0..64u32 {
        let g = e.attest(&[1], &format!("ev-{i:04}"), 60, o - i as u64).await?.as_gas();
        if i == 0 { first = g; } last = g;
    }
    let s1 = used(&e).await;
    eprintln!("STORAGE per pending event: {} bytes (64 events)", (s1 - s0) / 64);
    eprintln!("GAS attest with 0 pending: {} Tgas ; with 63 pending: {} Tgas", first / 1_000_000_000_000, last / 1_000_000_000_000);
    e.fails("bot1", "attest", json!({"event_id": "overflow", "mag_x10": 60, "origin_s": o, "alert": 2}), "too many pending").await?; // fails safe: nothing new starts
    e.ok("judge", "submit_claim", json!({"event_id": "still-ok", "mag_x10": 60, "origin_s": o, "alert": 2})).await?; // claims have their own limit
    assert!(last < 250_000_000_000_000, "attest must fit in 250 Tgas at the pending-event limit");
    Ok(())
}
