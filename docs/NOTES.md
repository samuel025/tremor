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

## M3 notes: first testnet deployment (2026-11-07)
- Faucet (`sponsor-by-faucet-service`) returned 429 for this machine; 4 retries over ~7 min failed. Used the existing testnet account rounds-indep-5928.testnet (a Rounds account, with the human's OK) as the parent of the 10 Tremor accounts: tremor.*, ada, bayo, chidi, dayo, relief1..relief5 under it. Keys live in `.state/home/.near-credentials` (gitignored). A copy of the parent's key is also in `.state/` so sub-accounts could be created; delete it when done.
- Optimised wasm (cargo near build non-reproducible-wasm) is 266 KB, about 2.7 NEAR of storage; the plain cargo build was 556 KB.
- Live demo contract: tremor.rounds-indep-5928.testnet, demo windows 120 s / 180 s, max_age 60 days.
- Verified on testnet: real event us7000twg9 (M6.1) reported, counted after 120 s: minted 2,750 TREM (same as the Python reference), 550 to each relief account. Fake event fake-001 (M7.4) challenged and voted down: supply unchanged, reporter lost its 1,000 bond and 1,000 (20% of 5,000) of its stake, Ada got 31,500 and Chidi 10,500 (1,500 + 500 from the pot), Bayo's challenger bond returned.
- Not done yet: near-workspaces sandbox tests, on-chain cap-clipping test, reporter function-call key, make demo, make verify-onchain, gas and storage measurements.
