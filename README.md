# Tremor

**Tremor is a NEAR testnet memecoin whose supply grows a little, and only to a fixed relief list, whenever an earthquake of magnitude 6 or more that USGS expects to affect people (its alert level yellow or higher) is confirmed. Five fixed bots read the official USGS earthquake record and three of them must agree; nobody votes, coins give no say, and every limit is written into the contract. Holders get a small dividend for each day with no counted quake, and can give their own coins to the same relief list, which is recorded on a public givers board.**

> **Testnet prototype. No value, no real donations.** Tremor promises no value, and holding it dilutes you when quakes happen. The five relief accounts are stand-ins that donate nothing real. Nothing here claims real-world impact. Earthquakes cause real harm; this project uses the word "relief" for a mechanism, not for an outcome, and shows no casualty figures.

- Live page: https://samuel025.github.io/tremor/ (or run it yourself: `make web-dev`).
- Live contract (testnet, real timing: a quake is confirmed after it is 6 hours old): `tremor-live.rounds-fund-5928.testnet`
- Demo contract (testnet; used only by `make demo`, the scripted on-chain scene, and not by the page): `tremor.rounds-indep-5928.testnet`
- Demo video and X post: TODO(human): add the links.
- Built for the NEAR HACKATHON, track **Memecoins With Mechanics**. All code was written from Nov 7, 2026.

## Results

Every number below is read from `results/results.json`, which `make results` fills by running the commands. `make check-readme` fails if this README is out of date.

- `make test`: 16 Python tests pass (2026-11-10), including the eight golden vectors.
- `make conformance`: the Rust contract logic and the Python reference agree on 202 seeded random scenarios, 27,797 steps, 0 mismatches (2026-11-10).
- `make sandbox-test`: 11 simulated-network tests pass, 0 fail (2026-11-10). One pending event costs about 327 bytes of storage; `attest` burns about 3 Tgas with 63 events pending.
- `make conformance-web`: the TypeScript rules engine behind the page's simulation matches the Python reference on 202 seeded scenarios, 27,797 steps, 0 mismatches, and golden vectors 1, 5, 6, 7 and 8 (2026-11-10).
- `make replay` (offline): 14 checks pass, 0 fail (2026-11-10).
- `make verify-onchain` (demo, `tremor.rounds-indep-5928.testnet`): 16 checks pass, 0 fail (2026-11-10). The contract still has 1 access key; every key is deleted only as the very last step, on the human's word, and `python3 scripts/verify_onchain.py --net demo --final` then demands an empty list.
- `make verify-onchain` (live, `tremor-live.rounds-fund-5928.testnet`): 13 checks pass, 0 fail (2026-11-10). The contract still has 1 access key; every key is deleted only as the very last step, on the human's word, and `python3 scripts/verify_onchain.py --net live --final` then demands an empty list.
- `make demo` (testnet): 35 of 35 checks matched the reference's expected values (2026-11-10).
- `make sim`: 27 parameter combinations were tried on 352 real events (28 of M6.0 or more, 5 of them with USGS expected impact of yellow or higher, which is what counts); 22 passed every threshold that was written down before the run (`docs/DECISIONS.md`). Chosen: 0.25% base share, 1.5% weekly cap, 5% monthly cap. A passive holder is diluted by 1.55% over the 60 real days. See `results/sim/SUMMARY.md`.

## Try it in five minutes (do X, see Y)

| Do | See |
|---|---|
| `make web-dev`, then open the printed address | A guided four-step walkthrough, an event board showing which of the five bots attested each quake, the weekly and monthly cap meters, the relief list, a 60-day earthquake map with a replay, and the contract's rules and access-key count, all read live from testnet. No wallet needed to look. |
| `make test` | The Python reference reproduces the five golden vectors (`vectors/gv-1.json` to `vectors/gv-5.json`) exactly. |
| `make conformance` | The Rust contract logic and the Python reference agree on 202 seeded random scenarios, with 0 mismatches. |
| `make sim` | The eight simulation scenarios on the real catalog (honest bots, a swarm, bad bots, offline bots, claim spam, holders giving, the calm-day dividend, the impact bar); `results/sim/SUMMARY.md` and `results/sim/supply.svg`. |
| `make replay` | An offline recomputation of a saved testnet log (`fixtures/testnet-demo.json`): every check PASS. |
| `make verify-onchain` | Both live contracts are read and compared with the reference: every check PASS, plus an INFO line about the access key. |
| `make conformance-web` | The TypeScript copy of the rules, used by the page's simulation, matches the Python reference: 202 scenarios, 27,797 steps, 0 mismatches. |
| `make demo` | The scripted scene on testnet with the reference's expected value next to the real one at each step. Needs your own funded testnet accounts in `.state/` and no bots running; takes a couple of minutes. |

## Take part as a judge

**The interactive part of the page is a simulation that runs in your browser.** No wallet, no testnet, nothing to install, and nothing that can be offline. It uses the same rules code as the contract (`web/src/sim/engine.ts`), and `make conformance-web` proves that copy identical to the Python reference on the same 202 random scenarios the Rust contract is checked against. Nothing in the simulation is on the blockchain, and the page says so.

1. Pick a quake: one of the real ones from the committed USGS catalog, or make one up.
2. Set each of the five bots to **Honest** (attests only quakes the USGS has), **Bad** (attests anything) or **Offline**.
3. Press the button and watch the bots decide one by one. A quake counts when three attest the same record. Then see the coins created, the split between the five relief accounts, the weekly and monthly caps, and what the cooldown does to a quake near another one.
4. Or press a scenario: a real quake, a made-up quake, two bad bots, three bad bots, three bots offline. Two bad bots mint nothing; three can push a made-up quake through (to the caps); three offline bots mint nothing. "Skip ahead a week" shows the weekly cap resetting.
5. You hold 5,000 simulated TREM. Watch your share of the supply shrink a little with each counted quake. Press **Let a calm day pass** to see the dividend arrive (and see that the day after a quake pays nothing), and press **Give** to send some of your own coins to the relief accounts: the supply and the caps do not move.

**The real thing is the Live contract**, shown on the same page: its event board, caps, relief balances and rules are read from testnet, kept up to date by the real bots. Live is slow on purpose: a quake is only confirmed once it is 6 hours old, and the bots run every 20 minutes. A judge with a free Meteor wallet can still claim a quake on Live: the "Want to see it on the real blockchain?" bar under the simulation opens that walkthrough; a claim creates nothing by itself, and made-up claims are never confirmed. **Watch the bots decide** replays a recorded real run on testnet, including the honest worst case. The tap gives 5,000 free starter TREM once per account if you want to hold coins; it creates no new coins.

**Who plays the bots on Live.** `bots/bots.mjs`, run every 20 minutes by `.github/workflows/bots-live.yml`; the bot keys are private and never in this repo. The Demo contract has no bots running: it exists so `make demo` can replay a scripted scene on testnet.

## The mechanic in brief

A confirmed big earthquake creates new coins equal to a small share of the supply, split equally among five fixed relief accounts. Everyone else is diluted by that small amount, and caps limit how much any week or month can dilute. The exact integer rules are in `RULES.md`.

- **Five fixed bots.** At launch five publisher accounts are set forever, like the relief list. Only they can attest a quake. No coin holder has any say.
- **Attest.** A bot posts a quake it found in USGS: its event ID, magnitude to one decimal, origin time and USGS alert level. The contract refuses it if the magnitude is below 6.0, the alert level is below yellow, the time is in the future or too old, or the quake is not yet old enough (USGS revises fresh events; this delay is the finality delay).
- **Impact bar.** USGS publishes a PAGER alert level for each quake (green, yellow, orange, red): its estimate of expected human and economic impact. Only quakes at yellow or higher count, so a deep or remote quake that USGS expects to affect few people never mints. In the committed 60 days, 5 of the 28 M6+ quakes pass (23 are green). The alert is an estimate, not a count of people, and the page shows only the level word and no casualty figures or loss estimates.
- **Agree.** When **3 different bots** attest exactly the same record (including the alert level), the quake counts. A bot can attest an event once, so two different versions can never both reach 3 of 5.
- **Mint.** A counted event mints 0.25% of supply at M6.0 (twice that at M7, three times at M8, never above 1.5%), less if it follows another event within 24 hours, clipped to a weekly cap of 1.5% and a monthly cap of 5%, split equally between the five relief accounts.
- **Calm days.** For each full UTC day in which no quake was counted, the contract creates 0.01% of the supply for holders: every account except the five relief accounts, in proportion to its balance. It is outside the weekly and monthly caps, which bound quake mints only, so relief's allowance is never spent on holders; its own limit is one dividend per day. Nobody triggers it: every transaction first settles the days that have passed, and settling late gives exactly the same result as settling on time. A holder's share is credited when their balance next changes, or when they call `claim_dividend`.
- **Give.** Any holder may call `give(amount)`: their own coins are split between the five relief accounts exactly like a mint. No coins are created, no cap moves, and a later quake mints exactly what it would have. The contract keeps each giver's running total, shown on the page as a givers board with tiers (Bronze, Silver, Gold by total given) and a count of the quake rounds the account gave in. Giving buys no say in anything.
- **Giver bonus.** 20% of each calm day's dividend is set aside for givers, shared by how much each has given, and each coin ever given can earn at most 0.5% of a coin a day. Both limits are linear in what an account gave, so giving through many accounts gains nothing, and a gift takes at least about 200 calm days to earn back. What givers do not take goes to holders, so the dividend's total does not change. It is a softened cost, not a profit: nothing can pay givers more than they gave without creating extra coins.
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
| Three or more bad bots | None beyond the caps and the fixed relief list | Made-up quakes can count: with 3 bad bots 10 of 10 did, adding 1.48% to supply (the real quakes had already used much of the allowance, so a quiet month would allow more), never past the caps. **This is the weak spot:** trust sits in the five fixed bots. For this demo all five run on one server; a real launch would have five separate operators. |
| Bots offline | The system fails safe | With 2 bots offline 100% of real quakes still counted; with 3 offline 0% did, and nothing was created. |
| Bots disagree (USGS revises a quake) | Different records never combine; the minimum age waits out early revisions | A quake some bots record differently needs three matching bots, or it waits. |
| Duplicate or aftershock spam | An event ID mints once, ever; a cooldown scales aftershock mints down | The cooldown is a time rule, not geography. |
| Claim spam | Claims have their own limits (one open per account, 32 at once) | A spammer can fill the claim box but not stop the bots from starting events. |
| One data source | None | Everything depends on USGS. |

## Honest limits

- The five bots are chosen at launch by whoever launches, and three of them decide. If three are bad, fakes count up to the caps and real quakes can be blocked. The caps and the fixed relief list bound the damage; they do not remove it.
- **The bots share one server only for this demo.** On Live all five run in a single scheduled job, because one entrant cannot be five operators. That shows the mechanism working; it is not how a real launch would run. There, each bot would be run by a different operator on its own machine with its own key, so no single break-in reaches the three needed to agree. The next step beyond that is running the bots inside attested hardware enclaves, so a key cannot be taken out and the running code can be proven.
- The bots trust one source, USGS, and USGS revises events. The relief list is chosen by whoever launches; here its five accounts are stand-ins on testnet.
- The relief list holds account names, not keys, so an organisation can rotate its keys without any change here. But the list can never change: if a relief account is fully taken over, whoever holds it keeps its balance and its fifth of every later mint, and nothing can stop that. A real launch would need each relief account to be a multisig account created and controlled by the organisation itself, and no organisation may be named without its agreement.
- Removing votes also removed the incentive structure: nobody is rewarded for reporting or punished for lying, and bots are not paid. A bad bot loses nothing on chain.
- The simulation uses one real 60-day window (352 events of M5+, 28 of M6+): a small sample. The bad-bot and offline scenarios hold by the rules (three of five), so they confirm the contract rather than discover anything.
- With the impact bar, few quakes count (about two or three a month), so on the real data the weekly cap binds in 0% of weeks and a passive holder loses 1.55% of their share over 60 days (without the bar: 6.42%, cap binding in 25% of weeks). The caps now mainly bound what bad bots could do. The parameters were chosen at 0.25% / 1.5% / 5% before the bar existed; with the bar 22 grid combinations pass and the grid's own pick would have been a weekly cap of 1%, so those confirmed values were kept on purpose.
- The alert level is a USGS estimate that can be revised, and some quakes have none yet. A green quake can still affect people, and a yellow one can turn out mild. The bots wait for USGS to publish a level and attest only what it says; bots that see different levels do not match, and the quake waits. Live will often show nothing new for days.
- The calm-day dividend grows a holder's coin count but hardly changes their share of the supply: on the 60 real days a passive holder loses 1.55% of their share with it and 1.56% without it. Almost every coin is paid the same percentage; only the five relief accounts are left out, and they hold a few percent of the supply. It was first built inside the caps, where it did more for holders but took about 2% from relief; it was moved outside so relief loses nothing (15,867 TREM for relief with it, 15,812 without, 5,955 for holders over 59 paid days). So total creation can exceed the quake caps by up to 0.01% of supply a day. It is paid by balance, so the launcher and the starter-coin pool, which hold most coins in this demo, receive most of it.
- The simulated network cannot jump days, so the day-by-day dividend arithmetic is checked on the engine (conformance and `vectors/gv-5.json`), and only the wiring is checked on a deployed contract. Replay checks how much dividend was created and when, not which holder was credited.
- The giver bonus is small and slow: in the simulation one account giving 10,000 TREM earned 1,203.55 TREM over 60 calm days, fifty accounts giving 200 each earned the same in total, and a lone giver of 1 TREM earned 0.3000 TREM. When several people give, the shared pool (not the cap) limits it. Non-givers receive about 80% of the dividend while givers exist. The tiers and quake rounds are labels computed in the browser from the public log, not powers.
- Giving is a gift first: the bonus only softens what it costs. The givers board ranks by amount, so a large holder can top it. The giving scenarios in the simulation use assumed behaviour (written down before the run); they show that gifts never change supply or mints, not how real people would act.
- The contract keeps all state in one Borsh blob, which is fine for a demo and would not scale to a real launch.
- `make replay` and `make verify-onchain` check supply, mints, caps, which events counted, who attested what, and relief balances. The on-chain log does not record plain transfers, so they do not check every holder's balance.
- The page's wallet buttons (Meteor wallet, testnet) call only contract functions that the tests above exercise, but the author has not completed a full wallet round trip in a real browser session. The command-line path (`make demo`) does the same calls.
- The tap pool is finite and any account can use it. Anyone can also claim made-up quakes; they never count.
- The Live bots run on a GitHub scheduled job, which can be delayed or skipped. While they are down nothing new is confirmed on Live and nothing is created.
- The interactive demo is a simulation, not the chain. It can show the rules, but not a wallet signing a transaction; the Live contract shows the real thing, slowly. The simulation's bots are scripted, so it demonstrates the mechanism, not the trustworthiness of any real bot.
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
| `deployments.json`, `docs/LIVE.md` | Which contracts the page and tools use, and how Live and the scripted Demo differ |
| `.github/workflows/` | The Live bot schedule and the page hosting |
| `web/` | The static page (Vite and TypeScript; reads the chain and USGS in the browser); `web/src/sim/engine.ts` is the rules engine behind the simulation and `web/tests/conformance.ts` proves it matches the reference |
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
