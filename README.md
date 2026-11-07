# Tremor

**Tremor is a NEAR testnet memecoin whose supply grows a little, and only to a fixed relief list, whenever an earthquake of magnitude 6 or more is confirmed. Five fixed bots read the official USGS earthquake record and three of them must agree; nobody votes, coins give no say, and every limit is written into the contract.**

> **Testnet prototype. No value, no real donations.** Tremor promises no value, and holding it dilutes you when quakes happen. The five relief accounts are stand-ins that donate nothing real. Nothing here claims real-world impact. Earthquakes cause real harm; this project uses the word "relief" for a mechanism, not for an outcome, and shows no casualty figures.

- Live page: TODO(human): add the hosted URL. Until then run it yourself: `make web-dev`.
- Live contract (testnet, real timing: a quake is confirmed after it is 6 hours old): `tremor-live.rounds-fund-5928.testnet`
- Demo contract (testnet, a quake can be confirmed after 10 seconds so a whole round takes about a minute): `tremor.rounds-indep-5928.testnet`
- Demo video and X post: TODO(human): add the links.
- Built for the NEAR HACKATHON, track **Memecoins With Mechanics**. All code was written from Nov 7, 2026.

## Results

Every number below is read from `results/results.json`, which `make results` fills by running the commands. `make check-readme` fails if this README is out of date.

- `make test`: 3 Python tests pass (2026-11-07), including the three golden vectors.
- `make conformance`: the Rust contract logic and the Python reference agree on 200 seeded random scenarios, 28,021 steps, 0 mismatches (2026-11-07).
- `make sandbox-test`: 8 simulated-network tests pass, 0 fail (2026-11-07). One pending event costs about 308 bytes of storage; `attest` burns about 3 Tgas with 63 events pending.
- `make replay` (offline): 14 checks pass, 0 fail (2026-11-07).
- `make verify-onchain` (demo, `tremor.rounds-indep-5928.testnet`): 15 checks pass, 0 fail (2026-11-07). The contract still has 1 access key; every key is deleted only as the very last step, on the human's word, and `python3 scripts/verify_onchain.py --net demo --final` then demands an empty list.
- `make verify-onchain` (live, `tremor-live.rounds-fund-5928.testnet`): 14 checks pass, 0 fail (2026-11-07). The contract still has 1 access key; every key is deleted only as the very last step, on the human's word, and `python3 scripts/verify_onchain.py --net live --final` then demands an empty list.
- `make demo` (testnet): 27 of 27 checks matched the reference's expected values (2026-11-07).
- `make sim`: 27 parameter combinations were tried on 352 real events (28 of M6.0 or more); 5 passed every threshold that was written down before the run (`docs/DECISIONS.md`). Chosen: 0.25% base share, 1.5% weekly cap, 5% monthly cap. A passive holder is diluted by 6.43% over the 60 real days. See `results/sim/SUMMARY.md`.

## Try it in five minutes (do X, see Y)

| Do | See |
|---|---|
| `make web-dev`, then open the printed address | A guided four-step walkthrough, an event board showing which of the five bots attested each quake, the weekly and monthly cap meters, the relief list, a 60-day earthquake map with a replay, and the contract's rules and access-key count, all read live from testnet. No wallet needed to look. |
| `make test` | The Python reference reproduces the three golden vectors (`vectors/gv-1.json`, `vectors/gv-2.json`, `vectors/gv-3.json`) exactly. |
| `make conformance` | The Rust contract logic and the Python reference agree on 200 seeded random scenarios, with 0 mismatches. |
| `make sim` | The five simulation scenarios on the real catalog; `results/sim/SUMMARY.md` and `results/sim/supply.svg`. |
| `make replay` | An offline recomputation of a saved testnet log (`fixtures/testnet-demo.json`): every check PASS. |
| `make verify-onchain` | Both live contracts are read and compared with the reference: every check PASS, plus an INFO line about the access key. |
| `make demo` | The scripted scene on testnet with the reference's expected value next to the real one at each step. Needs your own funded testnet accounts in `.state/` and no bots running; takes a couple of minutes. |

## Take part as a judge

The page opens on the **Demo** contract and walks you through the whole process in four steps. The current step is worked out from the chain and your wallet, so it moves on by itself:

1. Connect a free testnet wallet (Meteor, set to testnet). Logging in gives the page a key that can call Tremor and nothing else.
2. Tell the contract about an earthquake. The page picks a real, recent one from USGS for you. A claim creates nothing by itself.
3. Watch the five bots decide. Each bot checks the USGS record on its own; when three attest the same record, the quake counts.
4. See what it did: how many new coins were created and what each relief account received.

You can also claim a **made-up** quake and watch the bots ignore it: it stays unconfirmed and creates nothing. No deposits, no coins, no votes are involved, so a wallet with no coins works. If you want to hold some coins to see them diluted, the **tap** gives 5,000 free starter TREM once per account; it creates no new coins.

**Watch the bots decide** replays a recorded real run on testnet: a claim confirmed by three bots, a quake the bots disagree about, and the honest worst case where three bad bots attest a made-up quake.

The bots are `bots/bots.mjs`. On Live they run every 20 minutes (`.github/workflows/bots-live.yml`) and attest every recent M6+ quake. On Demo they only confirm visitors' claims, in a loop that polls every few seconds (`.github/workflows/bots-demo.yml`, started by hand on judging days). Details and limits are in `docs/LIVE.md`.

## The mechanic in brief

A confirmed big earthquake creates new coins equal to a small share of the supply, split equally among five fixed relief accounts. Everyone else is diluted by that small amount, and caps limit how much any week or month can dilute. The exact integer rules are in `RULES.md`.

- **Five fixed bots.** At launch five publisher accounts are set forever, like the relief list. Only they can attest a quake. No coin holder has any say.
- **Attest.** A bot posts a quake it found in USGS: its event ID, magnitude to one decimal, and origin time. The contract refuses it if the magnitude is below 6.0, the time is in the future or too old, or the quake is not yet old enough (USGS revises fresh events; this delay is the finality delay).
- **Agree.** When **3 different bots** attest exactly the same record, the quake counts. A bot can attest an event once, so two different versions can never both reach 3 of 5.
- **Mint.** A counted event mints 0.25% of supply at M6.0 (twice that at M7, three times at M8, never above 1.5%), less if it follows another event within 24 hours, clipped to a weekly cap of 1.5% and a monthly cap of 5%, split equally between the five relief accounts.
- **Claims.** Anyone may tell the contract about a quake. A claim mints nothing; it only waits for the bots. Claims are limited (one open per account, at most 32 at once) and have their own limit, so spam cannot stop the bots.

Chosen parameters (picked by the simulation, then confirmed by the human; see `docs/DECISIONS.md`): base share 0.25%, weekly cap 1.5%, monthly cap 5%.

The first golden vector (`vectors/gv-1.json`, spec-default 0.5% base share, 1,000,000 TREM supply, each event confirmed by three bots at its origin time):

| Event | Magnitude | New coins (TREM) | Supply after (TREM) | Each relief account gets (TREM) | Cut by a cap |
|---|---|---|---|---|---|
| E1 | M6.0 | 5,000 | 1,005,000 | 1,000 | no |
| E2 | M7.0 | 10,050 | 1,015,050 | 2,010 | no |
| E3 | M6.0 | 175.75 | 1,015,225.75 | 35.15 | yes |

## How events are confirmed and what a liar can do

The contract cannot look at the internet, so someone has to carry the earthquake record in. Here that is five fixed bots, and the contract only checks that three of them say exactly the same thing. This replaced an earlier design where holders locked coins and voted on disputed reports; that design let whoever held most of the coins decide, and the human did not want voting power or liquidity to matter (`docs/DECISIONS.md`).

| Attack or failure | Defence | What is left over |
|---|---|---|
| Someone claims a made-up quake | A claim creates nothing; the bots attest only what USGS has | It stays pending and expires. In the simulation 0 of 8,640 spam claims counted, and every real quake still counted (100%). |
| One or two bad bots | Three must attest the same record | In the simulation, with 2 bad bots 0 of 10 made-up quakes counted. |
| Three or more bad bots | None beyond the caps and the fixed relief list | Made-up quakes can count: with 3 bad bots 10 of 10 did, adding 1.24% to supply (the real quakes had already used much of the allowance, so a quiet month would allow more), never past the caps. **This is the weak spot:** trust sits in the five fixed bots. In the demo all five are run by us, so their independence is only demonstrated. |
| Bots offline | The system fails safe | With 2 bots offline 100% of real quakes still counted; with 3 offline 0% did, and nothing was created. |
| Bots disagree (USGS revises a quake) | Different records never combine; the minimum age waits out early revisions | A quake some bots record differently needs three matching bots, or it waits. |
| Duplicate or aftershock spam | An event ID mints once, ever; a cooldown scales aftershock mints down | The cooldown is a time rule, not geography. |
| Claim spam | Claims have their own limits (one open per account, 32 at once) | A spammer can fill the claim box but not stop the bots from starting events. |
| One data source | None | Everything depends on USGS. |

## Honest limits

- The five bots are chosen at launch by whoever launches, and three of them decide. If three are bad, fakes count up to the caps and real quakes can be blocked. The caps and the fixed relief list bound the damage; they do not remove it.
- In the demo and on Live, all five bots run in one process from one place. That demonstrates the mechanism, not independence. A real launch would need five independent operators.
- The bots trust one source, USGS, and USGS revises events. The relief list is chosen by whoever launches; here its five accounts are stand-ins on testnet.
- Removing votes also removed the incentive structure: nobody is rewarded for reporting or punished for lying, and bots are not paid. A bad bot loses nothing on chain.
- The simulation uses one real 60-day window (352 events of M5+, 28 of M6+): a small sample. The bad-bot and offline scenarios hold by the rules (three of five), so they confirm the contract rather than discover anything.
- The chosen parameters pass the cap-binding threshold (25% of weeks against a 25% limit) with no margin. The spec's own default 0.5% base share fails it (62.5% of weeks).
- The contract keeps all state in one Borsh blob, which is fine for a demo and would not scale to a real launch.
- `make replay` and `make verify-onchain` check supply, mints, caps, which events counted, who attested what, and relief balances. The on-chain log does not record plain transfers, so they do not check every holder's balance.
- The page's wallet buttons (Meteor wallet, testnet) call only contract functions that the tests above exercise, but the author has not completed a full wallet round trip in a real browser session. The command-line path (`make demo`) does the same calls.
- The tap pool is finite and any account can use it. Anyone can also claim made-up quakes; they never count.
- The bots run on GitHub's scheduled jobs, which can be delayed or skipped, and the Demo bot loop is started by hand. While the bots are down nothing is confirmed and nothing is created.
- The USGS licence terms were not verified (their policy page blocked automated access). Read them before making this repo public.
- Public testnet RPC endpoints rate-limit. The page and the check scripts try `test.rpc.fastnear.com` first and fall back to `rpc.testnet.near.org`.

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
| `bots/` | The five publisher bots that read USGS and attest quakes |
| `deployments.json`, `docs/LIVE.md` | Which contracts the page and tools use, and how Live and Demo differ |
| `.github/workflows/` | The bot schedules and the page hosting |
| `web/` | The static page (Vite and TypeScript; reads the chain and USGS in the browser) |
| `docs/NOTES.md`, `docs/DECISIONS.md` | What was learned, and every departure from the spec |
| `AGENTS.md` | Rules for coding agents working in this repo |

## Two projects, one entrant

Other NEAR HACKATHON project by the same entrant: Rounds (TODO(human): add the link). The two are independent: different code, different track.

## AI assistance, libraries, licence, data

- Written with Claude Code (Anthropic) working from a build spec, with a human making the decisions at each checkpoint. Check the claims by running the commands, not by trusting this README.
- Libraries and tools: near-sdk 5.30.1, near-workspaces 0.24.0, cargo-near, NEAR CLI, Vite 5.4.21, TypeScript 5.6.3, near-wallet-selector 10.1.4, near-api-js 5.1.1 (bots). The Python code uses only the standard library.
- Licence: MIT (`LICENSE`).
- Earthquake data: U.S. Geological Survey, Earthquake Hazards Program, ANSS ComCat (FDSN event web service). Please credit the USGS when reusing it.
- Testnet keys are throwaway and live in `.state/`, which is gitignored. Never commit keys.
