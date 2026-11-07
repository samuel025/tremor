# Live and demo deployments (testnet)

Two copies of the same contract code run on NEAR testnet. Both have fixed parameters, no owner and no upgrade path (`make verify-onchain` checks the deployed code).

| | Demo | Live |
|---|---|---|
| Contract | `deployments.json` > `demo` | `deployments.json` > `live` |
| Waiting window / vote | 20 s / 30 s | 24 h / 48 h (the spec values) |
| Oldest reportable event | 60 days (so the committed catalog can be replayed) | 14 days |
| Who reports | The visitor (or `make demo`) | the keeper bot every 20 minutes, plus visitors |
| Bot | `watcher` (challenges reports USGS does not confirm, votes, finalizes, claims; no reporting) | `keeper` (all of that, plus reporting new real M6+ quakes) |
| How it runs | `.github/workflows/demo-watcher.yml`: a loop that polls every 4 s, restarted hourly | `.github/workflows/keeper.yml`: once every 20 minutes |
| Starter coins (`tap`) | 5,000 TREM once per account, from a 300,000 TREM pool | same |

## Setting up
- `python3 scripts/deploy.py demo [--reset]` and `python3 scripts/deploy.py live` create the accounts, deploy, and fill the tap pool. They need funded testnet parents in `.state/` and cost test coins only.
- The bot account holds coins in its wallet (reports and votes take their deposit from the wallet automatically) and one function-call key limited to `report_event`, `challenge`, `vote`, `finalize` and `claim_vote`. Secrets: `KEEPER_PRIVATE_KEY` (live) and `DEMO_WATCHER_PRIVATE_KEY` (demo), from `.state/keeper_key_live.json` and `.state/keeper_key_demo.json`. Never commit them. If one leaks, run `deploy.py <net> --rekey`; a leaked key can only call those five methods and only spend the bot's worthless coins.
- The page is built by `.github/workflows/pages.yml` (Settings > Pages > Source: GitHub Actions).

## Limits worth knowing
- The tap pool is finite (60 accounts) and any account can use it, so someone could drain it; it is testnet.
- Anyone with a testnet account can report, challenge and vote on the live contract, including with made-up events. That is the point of the demo.
- On Live, a judge's own report finishes tomorrow (24 h window). Use Demo for a result in seconds.
- If the demo watcher is not running, a made-up quake on the demo is not challenged and counts up to the caps (the honest worst case). The recorded challenge on the page still shows the full dispute.
- A bot stops if its function-call key runs out of gas allowance (1 NEAR when created), its account runs out of NEAR for gas, or its wallet runs out of TREM (each report locks 1,000, each vote 5,000).
- GitHub disables scheduled workflows on repos with no activity for 60 days.

- `make demo` expects nobody else to challenge its made-up events: stop the demo watcher before running it, or it will challenge them first.
