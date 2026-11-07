# NOTES (M0)
## USGS feed (verified 2026-11-07)
- `https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2026-09-08&endtime=2026-11-07&minmagnitude=5&orderby=time-asc` returns 352 events with no key; 28 are M6.0+.
- Browser access works: response carries `access-control-allow-origin: *`.
- Stable fields: `id`, `properties.mag`, `properties.time` (ms), `properties.status`. All 352 are `reviewed` (older events; fresh ones are usually `automatic`, not yet checked). `type` filtered to `earthquake`.
- NOT verified: USGS licence/attribution terms. The policy page returned 403 to curl. Read it in a browser before the catalog is committed to a public repo (human to confirm). Open question: should the window wait for `reviewed`?
- Not yet verified: impact alert levels in the feed; how revisions/removals look.
## Open questions (section 17) still unanswered
near-contract-standards minting, sandbox time travel, storage per event, gas, novelty search.

## M2 notes
- Open question 4 (answered): near-contract-standards 5.30.1 CAN mint after launch (`FungibleToken.total_supply` and `internal_deposit` are public). We still hand-wrote the token (NEP-141 + flat NEP-145 + NEP-148) so one pure Rust module (`contract/src/engine.rs`) holds all balances, bonds and caps and can be tested against the Python reference with no NEAR runtime. Decision logged in DECISIONS D-11.
- near-sdk 5.30.1 will not compile natively without the `unit-testing` feature; it is enabled only under dev-dependencies.
- Compiled contract exports (checked from the wasm): bond_balance_of, challenge, claim_vote, contract_source_metadata, deposit_bond, finalize, ft_*, get_event, get_log, get_params, get_state, list_events, new, report_event, storage_*, vote, withdraw_bond. No owner, admin or upgrade method.
- Still unanswered (M3): sandbox time travel, storage per event, gas of finalize/claim_vote, real MAX_OPEN_EVENTS.
