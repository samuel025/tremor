> **Update 2026-11-08:** the page no longer uses the Demo contract. Its interactive part is an in-browser simulation (DECISIONS D-25). The Demo contract below is kept only for `make demo`, and nothing runs bots on it. Everything about Live still applies.

# Live and demo deployments (testnet)

Two copies of the same contract code run on NEAR testnet. Both have fixed parameters, five fixed publisher bots, five fixed relief accounts, no owner and no upgrade path (`make verify-onchain` checks the deployed code).

| | Demo | Live |
|---|---|---|
| Contract | `deployments.json` > `demo` | `deployments.json` > `live` |
| A quake must be this old before bots confirm it | 10 s (so a catalog quake can be confirmed at once) | 6 h (USGS revises fresh events) |
| Oldest quake that can count | 60 days (the committed catalog) | 14 days |
| Who confirms | The five bots, **only visitors' claims** (`--claims-only`): the demo starts empty | The five bots, every recent M6+ quake whose USGS expected impact is yellow or higher, plus claims |
| How the bots run | `make demo-bots` (= `bots/bots.mjs --net demo --claims-only --loop 4`) on a computer that stays on (no GitHub job: the page no longer uses the Demo) | `.github/workflows/bots-live.yml`, every 20 minutes |
| Starter coins (`tap`) | 5,000 TREM once per account, from a 300,000 TREM pool | same |
| Donation match reserve | 100,000 TREM put in by the launcher at deploy (`fund_match`); gifts are topped up by 10% | same |

## How the deciding works
Five publisher accounts (`bot1` to `bot5`, set in `new`, never changed) are the only accounts that can call `attest`. A quake counts when three different bots attest exactly the same (id, magnitude, origin time). Each bot reads USGS on its own and attests only what it finds there. Visitors can `submit_claim` a quake; a claim mints nothing and the bots attest it only if USGS has it, so a made-up claim stays pending and expires.

## Setting up
- `python3 scripts/deploy.py demo [--reset]` and `python3 scripts/deploy.py live [--reset]` create the accounts (launcher, five relief accounts, five bots), deploy, fill the tap pool, put 100,000 TREM in the donation-matching reserve and make each bot a function-call key that can only call `attest`. They need funded testnet parents in `.state/` and cost test coins only. `--rekey` makes new bot keys.
- Bot keys: `.state/bot_keys_live.json` and `.state/bot_keys_demo.json` (a JSON object {account: private key}). They go into the GitHub Actions secrets `BOT_KEYS_LIVE` and `BOT_KEYS_DEMO`. Never commit them. If one leaks, run `deploy.py <net> --rekey`; a leaked key can only call `attest` on that contract (and only as that one bot), and the bots hold no coins.
- The bots need NEAR in their accounts for gas (0.25 NEAR each when created, about a thousand attestations). The page is built by `.github/workflows/pages.yml` (Settings > Pages > Source: GitHub Actions).

## Limits worth knowing
- All five bots run in one scheduled job on one server. That is for the demo only; a real launch would have five separate operators, each with its own machine and key. If three bots were bad, made-up quakes could count (up to the caps); if three are down, nothing is confirmed.
- The tap pool is finite (60 accounts) and any account can use it, so someone could drain it; it is testnet.
- Anyone with a testnet account can claim quakes, including made-up ones. Claims are limited (one open per account, 32 at once) and never mint by themselves.
- On Live, a visitor's claim of a real but not-yet-confirmed quake is confirmed within the 20 minute bot schedule once it is 6 hours old, so a result there can take hours. Use Demo for a result in seconds.
- If the demo bots are not running, nothing is confirmed on the demo: a claim just stays pending, then shows as not confirmed. The recorded run on the page still shows the whole story.
- `make demo` redeploys the demo contract and attests with the bot accounts' full keys itself: stop any running `bots.mjs --net demo` first, or the bots will confirm its quakes before it does.
- GitHub may delay or skip scheduled runs, disables scheduled jobs in a public repo after 60 days without activity, and its terms are meant for project automation. The Live job fits that. There is no Demo job in GitHub; run the Demo bots with `make demo-bots` on any machine that stays on.

- If the Demo bots are not running when a judge claims a real quake, the page tells the judge "The bots have not answered yet" and to ask the project owner. Start them before judging with `make demo-bots`, and watch that the process stays alive (it stops if the computer sleeps).
