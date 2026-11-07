# Tremor

**Tremor is a NEAR testnet memecoin whose supply grows a little, and only to a fixed relief list, whenever an earthquake of magnitude 6 or more is confirmed. Anyone can report an event, anyone can challenge it, and every limit is written into the contract.**

> **Testnet prototype. No value, no real donations.** Tremor promises no value, and holding it dilutes you when quakes happen. The five relief accounts are stand-ins that donate nothing real. Nothing here claims real-world impact. Earthquakes cause real harm; this project uses the word "relief" for a mechanism, not for an outcome, and shows no casualty figures.

- Live page: TODO(human): add the hosted URL. Until then run it yourself: `make web-dev`.
- Live contract (testnet, real 24 h and 48 h windows, kept busy by a bot): `{{verify.live}}`
- Demo contract (testnet, 20 second and 30 second windows so a whole round takes about a minute): `{{verify.demo}}`
- Demo video and X post: TODO(human): add the links.
- Built for the NEAR HACKATHON, track **Memecoins With Mechanics**. All code was written from Nov 7, 2026.

## Results

Every number below is read from `results/results.json`, which `make results` fills by running the commands. `make check-readme` fails if this README is out of date.

{{RESULTS}}

## Try it in five minutes (do X, see Y)

| Do | See |
|---|---|
| `make web-dev`, then open the printed address | An event board with a USGS match flag on each report, the weekly and monthly cap meters, the relief list, a 60-day earthquake map with a replay, and the contract's rules and access-key count, all read live from testnet. No wallet needed. |
| `make test` | The Python reference reproduces the three golden vectors (`vectors/gv-1.json`, `vectors/gv-2.json`, `vectors/gv-3.json`) exactly. |
| `make conformance` | The Rust contract logic and the Python reference agree on {{conformance.scenarios}} seeded random scenarios, with 0 mismatches. |
| `make sim` | The five simulation scenarios on the real catalog; `results/sim/SUMMARY.md` and `results/sim/supply.svg`. |
| `make replay` | An offline recomputation of a saved testnet log (`fixtures/testnet-demo.json`): every check PASS. |
| `make verify-onchain` | The live contract is read and compared with the reference: every check PASS, plus an INFO line about the access key. |
| `make demo` | The scripted scene on testnet with the reference's expected value next to the real one at each step. Needs your own funded testnet accounts in `.state/`; takes about 10 minutes because the demo windows are 120 s and 180 s. |

## Take part as a judge

The page opens on the **Demo** contract and walks you through the whole process in five steps. The current step is worked out from the chain and your wallet, so it moves on by itself:

1. Connect a free testnet wallet (Meteor, set to testnet). Logging in gives the page a key that can call Tremor and nothing else.
2. Get {{tap}} starter TREM from the tap (once per account; it comes from a pool the launcher filled and creates no new coins).
3. Report a real earthquake (picked for you from USGS) or make up a fake one. The 1,000 TREM deposit is taken from your wallet automatically; it is returned if you are right.
4. Wait for the safety window (20 seconds on Demo, the real 24 hours on Live), with a countdown. A watcher bot checks every report against USGS and settles the result by itself; a fallback button appears if it is slow.
5. See what it did: how many new coins were created and what each relief account received.

If you report a made-up quake, the watcher bot challenges it (USGS has no such event), votes it down, and finalizes it as rejected within seconds. For a challenge between two humans, the page also includes **Watch a challenge play out**, a narrated replay of a real recorded run, and with two wallets you can challenge and vote on any event from the event board.

The bots are `keeper/keeper.mjs`. On Live it runs every 20 minutes (`.github/workflows/keeper.yml`): it reports real M6+ quakes from USGS, challenges reports USGS does not confirm, votes, finalizes events whose window has ended, and claims payouts. On Demo a watcher (`.github/workflows/demo-watcher.yml`) does the same except reporting, in a loop that polls every few seconds because the windows are so short. Details and limits are in `docs/LIVE.md`.

## The mechanic in brief

A confirmed big earthquake creates new coins equal to a small share of the supply, split equally among five fixed relief accounts. Everyone else is diluted by that small amount, and caps limit how much any week or month can dilute. The exact integer rules are in `RULES.md`.

- **Report.** Anyone posts a USGS event ID, its magnitude to one decimal, and its time, locking a bond of {{bond}} TREM.
- **Wait.** The event sits for a fixed window (24 hours in the spec; 20 seconds on the demo contract). USGS sometimes revises or removes events, so the window doubles as the finality delay.
- **Challenge.** During the window anyone can challenge with a matching bond. Holders then lock coins on "real" or "not real".
- **Count.** With no challenge the event counts. With a challenge the side with more locked coins wins, if turnout reaches the minimum; otherwise it is rejected and everything is refunded.
- **Mint.** A counted event mints {{params.base}}% of supply at M6.0 (twice that at M7, three times at M8, never above 1.5%), less if it follows another event within 24 hours, clipped to a weekly cap of {{params.week}}% and a monthly cap of {{params.month}}%.
- **Settle.** The wrong side loses its bond, and wrong voters lose {{params.slash}}% of their locked coins, paid to the right side.

Chosen parameters (picked by the simulation, then confirmed by the human; see `docs/DECISIONS.md`): base share {{params.base}}%, weekly cap {{params.week}}%, monthly cap {{params.month}}%, wrong-vote penalty {{params.slash}}%, minimum turnout {{params.quorum}}% of supply.

The first golden vector (`vectors/gv-1.json`, spec-default 0.5% base share, 1,000,000 TREM supply):

{{GV1}}

## How events are confirmed and what a liar can do

The contract cannot check that an earthquake happened. The design rule is that a lie gains nobody anything and costs little: new coins go only to a fixed relief list, every mint is capped, and a wrong claim costs the claimant a deposit.

| Attack | Defence | What is left over |
|---|---|---|
| Fake event, nobody challenges | Waiting window, the page flags reports not found in USGS, per-event, weekly and monthly caps | A griefer can dilute everyone up to the cap at no cost, since the bond comes back. In the simulation, ten fakes with nobody watching added {{sim.fake_extra}}% to supply (the real events had already used most of the month's allowance, so a quieter month would allow more). |
| Fake event, challenged | The wrong side loses its bond; wrong voters lose {{params.slash}}% of locked coins | With 5 watchers each challenging half the fakes, {{sim.fakes_rejected}}% of fakes were rejected. A majority holder can still win a vote. |
| Blocking a real event | Caps are unaffected; the page shows the blocked event and the vote | A holder with 40% of supply blocked {{sim.whale}}% of real events in the simulation, and made money doing it. A majority holder can censor relief. |
| Selfish "no" votes | The penalty is far above the dilution one event can cause | With 30% of voting coins selfish, {{sim.selfish}}% of challenged real events still counted. With 60% selfish most were blocked: the design needs an honest majority. |
| Duplicate or aftershock spam | An event ID mints once, ever; a cooldown scales aftershock mints down | The cooldown is a time rule, not geography. |
| Report spam | A bond per report and a limit of 64 open events | Bonded spam can fill the limit for a while. |
| Many wallets | Votes and bonds are weighted by coins, so splitting gains nothing | One actor can still run many reporters. |
| Nobody reports a real quake | `keeper/keeper.mjs` posts unreported USGS events on Live | There is no reward for reporting, by design. |

## Honest limits

- Anyone who controls most of the coins controls challenge votes.
- The relief list is chosen by whoever launches; here its five accounts are stand-ins on testnet.
- The data is only as good as USGS, which revises events.
- On testnet the coins are free, so bonds and penalties show how the rules work but deter no one.
- Overlapping disputes lock the same coins, so turnout can fall under the minimum even with no selfish voters (simulation finding F-3 in `docs/DECISIONS.md`).
- The simulation uses one real 60-day window ({{sim.catalog_events}} events of M5+, {{sim.catalog_m6}} of M6+): a small sample. Voters in it are not strategic.
- The chosen parameters pass the cap-binding threshold ({{sim.clipped_pct}}% of weeks against a 25% limit) with no margin. The spec's own default 0.5% base share fails it ({{sim.default_clipped}}% of weeks).
- The contract keeps all state in one Borsh blob, which is fine for a demo and would not scale to a real launch.
- `make replay` and `make verify-onchain` check supply, mints, caps, event outcomes, vote payouts and relief balances. The on-chain log does not record plain transfers or bond deposits, so they do not check every holder's balance.
- The page's wallet buttons (Meteor wallet, testnet) call only contract functions that the tests above exercise, but the author has not completed a full wallet round trip in a real browser session. If a button misbehaves, the command-line path (`scripts/tn.sh`, `scripts/demo.py`) does the same calls.
- The tap pool is finite and any account can use it; anyone can also report made-up events on the contracts. Both are deliberate on testnet and written up in `docs/LIVE.md`.
- Deposits are now taken from the wallet automatically when a report, challenge or vote needs them. That is a rule change from the first spec, logged in `docs/DECISIONS.md`.
- The watcher bots challenge by checking USGS, so they trust one data source, and while a bot is down a made-up quake on that contract is not challenged and counts up to the caps. The Demo watcher runs on a scheduled GitHub job that can be delayed or skipped.
- The keeper runs on GitHub's scheduled jobs, which can be delayed or paused, and it stops if its small gas allowance or bond balance runs out.
- The USGS licence terms were not verified (their policy page blocked automated access). Read them before making this repo public.
- Public testnet RPC endpoints rate-limit. The page and the check scripts try `test.rpc.fastnear.com` first and fall back to `rpc.testnet.near.org`.

## The case against Tremor

A coin that dilutes its holders gives no one a reason to hold it. The relief is symbolic here, since the five accounts are stand-ins. When a cap is hit, a big event can mint nothing, so the coin stops reacting to magnitude (this happens in the simulation). The whole mechanism depends on one data source. And the people best placed to decide disputes are the people being diluted.

Why it is still worth building: it is a small, fully specified mechanic whose worst case is written in code and measured, whose rules cannot be changed after launch (the deployed code exports no owner, admin or upgrade method, and `make verify-onchain` checks that), and whose weak points are listed above rather than hidden.

## Repo map

| Path | What |
|---|---|
| `RULES.md` | The math, rounding rules and golden vectors: the source of truth |
| `reference/` | Python reference implementation and log replay |
| `contract/` | Rust NEAR contract (`contract/src/engine.rs` pure logic, `contract/src/lib.rs` NEP-141 wrapper), a conformance test, and near-workspaces tests in `contract/sandbox/` |
| `vectors/` | Golden vectors and the 200-scenario conformance set |
| `sim/`, `results/sim/` | The simulation and its committed output |
| `data/usgs_60d.csv` | The committed 60-day USGS catalog extract (M5+) with query URL and retrieval date |
| `scripts/` | Deploy, demo, replay, verify-onchain, README generation and checks |
| `keeper/` | The bot that reports real quakes and finalizes events on the Live contract |
| `deployments.json`, `docs/LIVE.md` | Which contracts the page and tools use, and how Live and Demo differ |
| `.github/workflows/` | The keeper schedule and the page hosting |
| `web/` | The static page (Vite and TypeScript; reads the chain and USGS in the browser) |
| `docs/NOTES.md`, `docs/DECISIONS.md` | What was learned, and every departure from the spec |
| `AGENTS.md` | Rules for coding agents working in this repo |

## Two projects, one entrant

Other NEAR HACKATHON project by the same entrant: Rounds (TODO(human): add the link). The two are independent: different code, different track.

## AI assistance, libraries, licence, data

- Written with Claude Code (Anthropic) working from a build spec, with a human making the decisions at each checkpoint. Check the claims by running the commands, not by trusting this README.
- Libraries and tools: near-sdk {{libs.near_sdk}}, near-workspaces {{libs.near_workspaces}}, cargo-near, NEAR CLI, Vite {{libs.vite}}, TypeScript {{libs.typescript}}, near-wallet-selector {{libs.wallet_selector}}, near-api-js {{libs.near_api_js}} (keeper). The Python code uses only the standard library.
- Licence: MIT (`LICENSE`).
- Earthquake data: U.S. Geological Survey, Earthquake Hazards Program, ANSS ComCat (FDSN event web service). Please credit the USGS when reusing it.
- Testnet keys are throwaway and live in `.state/`, which is gitignored. Never commit keys.
