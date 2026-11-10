//! TESTNET RESET TOOL, not part of Tremor: deployed over an old test contract by scripts/deploy.py --reset when testnet refuses to delete an account whose state is large.
//! It removes the storage keys it is given, so the account can then be redeployed fresh. Only the account itself may call it; it keeps no state.
use near_sdk::env;
use near_sdk::json_types::Base64VecU8;

#[no_mangle]
pub extern "C" fn clean() {
    env::setup_panic_hook();
    assert_eq!(env::predecessor_account_id(), env::current_account_id(), "only the account itself");
    let keys: Vec<Base64VecU8> = near_sdk::serde_json::from_slice(&env::input().expect("no input")).expect("bad input");
    for k in keys { env::storage_remove(&k.0); }
}
