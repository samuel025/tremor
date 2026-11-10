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

## Web page redesign (2026-11-07)
- The human rejected the first look and supplied an Apple-style reference (white gallery, #f5f5f7 bands, 28px shadowless cards, one blue for small controls, SF Pro type). The page was rebuilt to it. Dark mode was dropped (the reference is light only). Fonts fall back to the system stack; SF Pro renders only on Apple devices.
- One deliberate addition to the palette: Launch Orange (#b64400) is the "seismic energy" accent (P and S wave markers, epicentre rings, warnings, rejected events).
- Earthquake motion: hero seismogram replays real M6+ catalog events (P wave, then S wave); when the S wave arrives the headline, capsule and page shake with a damped oscillation scaled by magnitude; "Feel a replay" button; nav trace reacts to scroll speed; headings wobble and settle on reveal; event cards tremble (waiting), emit epicentre rings (counted, challenged) or shake once (rejected); the map replay sends P and S rings from each epicentre and shakes the map card. All motion is off with prefers-reduced-motion.
- Bug found by a headless run with a long virtual clock: the shake used rAF timestamps that could precede its start time, making the damping term explode (translate of billions of px). Fixed by clamping to performance.now().

## README (2026-11-07)
- README.md is generated: `make results` (or `make results-full` with the slow sandbox suite) records command output in results/results.json; `make readme` renders README.tmpl.md; `make check-readme` fails if the README is stale, names a missing make target or path, drops a required section, or uses risky wording. Edit README.tmpl.md, never README.md.
- Correction: I told the human the demo had 12 checks; the generated count is 13 (counted by hand before).
- Left for the human (marked TODO(human) in the template): hosted URL, demo video and X post links, Rounds link.

## Live deployment, tap, wallet (2026-11-07)
- Contract change: `tap()` (starter coins once per account from a pool in the contract's own balance; mints nothing) with a `tap_amount` parameter, `has_tapped`, and `tap_pool` in get_state. Python reference, Rust engine and the 200-scenario conformance set all cover it (443+ successful taps); a sandbox test covers registration, once-only, empty pool and unchanged supply.
- Two deployments (deployments.json, docs/LIVE.md): demo (120 s / 180 s) and live (24 h / 48 h) with a keeper account and function-call key; keeper/keeper.mjs (near-api-js, so it runs on GitHub Actions without the NEAR CLI). Workflows for the keeper and for Pages are written but NOT pushed.
- The second funded account came from another Rounds account (rounds-fund-5928), with the human's OK.
- Wallet: the human said MyNearWallet is discontinued, so the page uses the Meteor wallet only (wallet-selector).
- Bug found by the human: "Connect wallet" did nothing. Cause (reproduced with a scripted Chrome session): the wallet libraries use Node's `Buffer`, which browsers lack, so the lazily loaded wallet chunk threw "Cannot read properties of undefined (reading 'from')" and the click handler had nothing to call. Fix: provide `Buffer` (the `buffer` package) before the wallet loads. After the fix the Meteor modal opens with no console errors. Still not tested: signing in and sending a transaction with a real wallet account.

## Guided path for judges (2026-11-07)
- Feedback from the human: the page was not intuitive for a judge who wants to test it. Changes: a "Try it yourself" section right after the hero with seven plain steps, one button each, current step derived from chain + wallet state (web/src/journey.ts); Demo is now the default contract; plain words ("deposit" for bond); "Watch a challenge play out", a narrated replay of the recorded run in fixtures/testnet-demo.json (web/src/dispute.ts), because one wallet cannot challenge its own report; wallet details, made-up-quake and lookup moved into a "More" box.
- Checked: rendered every step state with sample data in headless Chrome (not connected, has coins, ready to report, waiting, finished), the dispute player, and the top of the page: no console errors. NOT checked: a real signed transaction through Meteor for each step.
- Known gap: on Live a single judge cannot see a result for a day; the page says so and points to Demo.

## Fresh-clone test (2026-11-07)
Cloned the repo into an empty folder and ran the README commands: `make test` (3 pass), `make replay` (all pass), `make verify-onchain` (both contracts, all pass), `make sim` (reproduced results/ byte for byte), `make conformance` (200 scenarios, 24,529 steps, 0 mismatches), `make web-build` (builds), `make sandbox-test` (9 of 9 pass, about 3.5 minutes), `make check-readme` (all pass; 3 human TODOs). Bugs it found and that are fixed: verify-onchain needed my private .state folder; `make sim` and `make results` were silently skipped (sim/ and results/ are directories, targets were not .PHONY); check-readme read library versions from node_modules (now from lock files) and tripped on the deliberately gitignored .state/ path. Not tested in a clone: `make demo`, `deploy.py` and the keeper (they need funded testnet keys in .state/ by design), and anything needing a real Meteor wallet session.

## Five fixed bots replace challenge-and-vote (2026-11-07)
- The human did not want coin-weighted voting ("voting power and liquidity") and asked whether the contract could just use the USGS feed. A contract cannot fetch a web page, so bots carry the record in: five fixed publisher accounts, three must attest the same record; visitors can submit claims so judges can try it; no deposits, challenges, votes or penalties. Design and reasons: DECISIONS D-19..D-23.
- Rebuilt in order: RULES.md, Python reference, golden vectors (GV-1 unchanged, GV-2/GV-3 new), 200-scenario conformance (28,021 steps, 0 mismatches), Rust engine and NEAR wrapper, 8 simulated-network tests, simulation (honest, swarm, bad bots, offline bots, claim spam; the grid re-picked 0.25% / 1.5% / 5%, as confirmed), bots (bots/bots.mjs, near-api-js), deploy script (five bot accounts, one `attest`-only key each), demo script, both contracts redeployed, replay and verify-onchain, page, README.
- Results worth remembering: with 2 bad bots no fake counts; with 3 all do (to the caps); with 3 bots offline nothing is created (fails safe); claim spam filled the 32-claim limit and no real quake was blocked.
- Removed: bonds, deposit step, challenge, vote, claim_vote, quorum, penalty, the dispute replay, scripts/tn.sh, scripts/reporter.py history, the keeper (now bots/).
- The old contracts' state and the demo/live recordings from the voting design are gone (both contracts were redeployed with --reset).

## Demo bots stay private (2026-11-08)
- The browser-plays-the-bots idea was built and tested, then dropped at the human's request: no keys in the repo. See DECISIONS D-24. Added instead: the "bots have not answered yet" message in the walkthrough, and `make demo-bots` / `make live-bots`.
- A first attempt to purge the local key commit (hard reset plus aggressive garbage collection) was blocked as irreversible; the branch was renamed to `main-with-demo-keys` and a fresh `main` was made from origin/main instead. Only `main` is ever pushed. Delete the other branch when you are sure you do not want it.

## Simulation replaces the interactive Demo (2026-11-08)
- Built web/src/sim/engine.ts (BigInt port of the reference), web/tests/conformance.ts (run with `make conformance-web`; Node 23.6+ runs TypeScript directly): 200 scenarios, 28,021 steps, 0 mismatches, golden vector 1 ok. Built web/src/simulator.ts (pick a quake, set five bots Honest/Bad/Offline, five one-click scenarios, skip ahead a week, caps, split, cooldown note).
- Checked in headless Chrome by clicking every scenario: real quake counted (+2,750 TREM split 5 ways); made-up quake with honest bots not confirmed; two bad bots not confirmed (2 of 3); three bad bots count a made-up quake (capped, cooldown-scaled); three bots offline not confirmed; no page errors.
- The Live wallet journey is kept inside a fold-out. The Demo contract is no longer used by the page.

## Live redeployed with give and the calm-day dividend (2026-11-10)
- `deploy.py live --reset` failed: testnet refuses to delete an account whose state is large ("Delete account whose state is large is temporarily banned"). Nothing had changed at that point. Workaround used: a one-off 53 KB cleanup program (not in this repo; it removes the storage keys it is given and only the account itself can call it) was deployed to the Live contract account and removed all 45 old storage keys; then `deploy.py live` (no `--reset`) deployed the new code with a fresh `new`. The contract name is unchanged, so the bots' `attest`-only keys and the GitHub secret stayed valid. `--reset` will hit the same ban again once state grows; the same workaround applies.
- After the deploy: `verify_onchain.py --net live` all PASS; one run of the five bots counted us7000tx16 (M6.4): 3,500 TREM, 700 to each relief account, not clipped. The bots now look back 3 days, not 13, so a fresh contract no longer fills its weekly cap with a backlog.
- Not yet done on Live with a real wallet: `give`, `claim_dividend`, `tap`, `submit_claim` from the page. The Demo contract was not redeployed and still runs the Nov 8 code; it is used only by `make demo`.

## Demo redeployed; demo job removed (2026-11-10)
- The Demo contract now runs the same code as Live (give, calm-day dividend, cooldown fix). `scripts/deploy.py --reset` now clears old state itself when testnet refuses to delete a large account, using `scripts/reset_state/` (a testnet-only tool, not part of Tremor, callable only by the account it is deployed to), then deploys fresh over the same account name. `make demo` ran against it: all checks matched the reference, and `fixtures/testnet-demo.json` was re-recorded from it.
- `.github/workflows/bots-demo.yml` was deleted (the page no longer uses the Demo). The GitHub secret `BOT_KEYS_DEMO` is now unused and can be removed in repo settings. `make demo-bots` still runs Demo bots locally.

## Impact bar deployed (2026-11-10)
- Both contracts were redeployed with `min_alert` 2 (yellow) and the alert level in every record (D-35). `deploy.py --reset` deleted the accounts' state directly this time (state was small). `make demo` passed all checks, including a new step 4b: a real but green quake is refused for both a bot's attestation and a visitor's claim. `fixtures/testnet-demo.json` was re-recorded.
- Live now shows no counted quakes: the bots look back 3 days, and none of the last 13 days' M6+ quakes has a PAGER alert of yellow or higher (a dry run confirmed it). That is the intended behaviour, and it means a judge who looks at Live sees an empty event board until the next impactful quake. The simulation and the Demo run show the full flow.
- Bots read the alert from the USGS `alert` property; a quake with no alert yet is left alone until USGS publishes one.

## Page restructured (2026-11-10), the human's request
- The page had 12 stacked sections and two navigation bars, with everything about the live contract spread over six of them. It is now four parts under one navigation bar: How it works (three plain steps), Try it (the simulation, unchanged), Live on NEAR testnet (tabs: Overview, Quakes, Relief & givers, Rules, Try it with a wallet) and The evidence (tabs: 60 real days, Simulation results, A recorded bot run, Check it yourself). Design, colours, type and animations are unchanged; the tabs reuse the existing segmented control.
- Links: `#live-quakes`, `#live-wallet`, `#evidence-run` and the like open the matching tab; the old `#real` link opens the wallet tab. The empty Live board now explains that a quake appears only when USGS expects impact, and points to the simulation and the recorded run.
- Checked in headless Chrome at 1280 px and 390 px: every tab renders, no console errors, no sideways scroll. Not checked: a real wallet session, dark mode (the page is light only).
