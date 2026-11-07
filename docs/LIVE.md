# Live and demo deployments (testnet)

Two copies of the same contract code run on NEAR testnet. Both have fixed parameters, no owner and no upgrade path (`make verify-onchain` checks the deployed code).

| | Demo | Live |
|---|---|---|
| Contract | `deployments.json` > `demo` | `deployments.json` > `live` |
| Waiting window / vote | 2 min / 3 min | 24 h / 48 h (the spec values) |
| Oldest reportable event | 60 days (so the committed catalog can be replayed) | 14 days |
| Who reports | The visitor (or `make demo`) | `keeper/keeper.mjs` every 20 minutes, plus visitors |
| Starter coins (`tap`) | 5,000 TREM once per account, from a 300,000 TREM pool | same |

## Setting up
- `python3 scripts/deploy.py demo [--reset]` and `python3 scripts/deploy.py live` create the accounts, deploy, and fill the tap pool. They need funded testnet parents in `.state/` and cost test coins only.
- The keeper account holds a bond balance and one function-call key limited to `report_event` and `finalize`. Its secret goes into the GitHub Actions secret `KEEPER_PRIVATE_KEY` (see `.github/workflows/keeper.yml`). Never commit it. If it leaks, delete that key from the keeper account and make a new one; the key can touch nothing but those two methods.
- The page is built by `.github/workflows/pages.yml` (Settings > Pages > Source: GitHub Actions).

## Limits worth knowing
- The tap pool is finite (60 accounts) and any account can use it, so someone could drain it; it is testnet.
- Anyone with a testnet account can report, challenge and vote on the live contract, including with made-up events. That is the point of the demo.
- On Live, a judge's own report finishes tomorrow (24 h window). Use Demo for a result in minutes.
- The keeper stops if its function-call key runs out of gas allowance (0.3 NEAR when created) or its bond balance (20,000 TREM, 1,000 locked per open report).
- GitHub disables scheduled workflows on repos with no activity for 60 days.
