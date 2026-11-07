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

## M3 measurements (near-workspaces sandbox, 2026-11-07)
- Q5 answered: block timestamps follow wall-clock time in the sandbox and `fast_forward(100)` advances them about 30 s (about 0.3 s per block), so short real windows work (tests use 6 s / 10 s).
- Q6 answered: one open event costs about 303 bytes of contract storage (about 0.003 NEAR). 64 open events fit easily.
- Q7 answered: gas is tiny. report_event 2-3 Tgas even with 63 open events; finalize (mint to 5 accounts) 2 Tgas; claim_vote 2 Tgas. The 64-event limit is not gas-bound; it only bounds spam. Kept at 64.
- Sandbox suite (`make sandbox-test`): init once, no parameter/owner/upgrade/mint method callable, bad reports, unchallenged mint to five accounts, GV-2, GV-3, cap clipping, 64-open-event gas and storage. 7 passed.

## make demo (2026-11-07, testnet)
`scripts/demo.py` resets the contract account, then runs PRD section 13 steps 1-7 against testnet, printing the Python reference's expected value beside the chain's. Result: 12 PASS, 0 FAIL. Real M6.1 event minted 2,750 TREM; fake-001 rejected by vote; fake-002 (unchallenged) minted 6,016.50 TREM, the honest worst case. The CLI prints the bare JSON result on stdout and its labels on stderr (the first version of the script merged them and crashed). Step 8 (make verify-onchain) is not built yet. The contract account still has 1 access key; keys are deleted last, only on the human's word.

## M4 checking tools (2026-11-07)
- Contract change: event_counted and event_rejected log lines now include the finalize `time`, so the log alone is enough to replay the caps.
- `make replay` (offline, fixtures/testnet-demo.json): 14 checks PASS. `make verify-onchain` (testnet): 15 checks PASS, 1 INFO (the contract still has 1 access key; `--final` will demand an empty list). Replay limits: the log has events, votes and claims but no plain transfers or bond deposits, so it checks supply, mints, caps, outcomes, claim payouts and relief balances, not every holder's balance.
- verify-onchain also parses the deployed wasm's export list and fails if any method outside the intended list exists (no owner, admin, upgrade, set_* or free mint).
- Reporter: `scripts/reporter.py` signs with a function-call key on dayo limited to report_event and finalize (0.25 NEAR allowance); a real report succeeded and `challenge` / `vote` with that key are refused. The key is in .state/reporter_key.json (gitignored); its secret is passed on the command line, fine for a throwaway testnet key, not for anything real. One earlier throwaway key's seed phrase was printed in the session by mistake; that key was deleted from the account.
- The live demo contract now also holds us7000tw8r, reported by the reporter script (so it differs from fixtures/testnet-demo.json; `make demo` resets it).

## Web page (2026-11-07)
- `web/`: static Vite + TypeScript, no backend. Reads the contract over public RPC and USGS from the browser. Build: `make web-build` (output web/dist, relative paths so it can be hosted anywhere). `make web-dev` for development.
- Finding: the official `rpc.testnet.near.org` rate-limits (HTTP 429). Browsers report that as a CORS error, so the page uses the free `test.rpc.fastnear.com` first and falls back to the official one. verify_onchain.py and reporter.py use the same order.
- Checked in headless Chrome at 1280 px and 390 px: no console errors, live data shown (supply, caps meters, event board with USGS match flags, relief balances, access-key count, parameters, unreported quakes, map replay, five simulation charts). Dark mode and slower connections were NOT visually checked.
- Data: data/usgs_60d.csv now also has lat and lon columns (needed for the map); event id, magnitude and origin were verified identical, so the simulation results are unchanged.
- Not built: wallet buttons (deposit bond, report, challenge, vote); the page offers a read-only account lookup instead. Design takes loose inspiration from slush.app (bright blue, big type, soft cards, scroll reveals, ripple animation); only a text summary of that site was available, nothing was copied.
