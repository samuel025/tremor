# Simulation summary

Real catalog: 28 events of M6.0+ in the committed 60-day window (2026-09-08 to 2026-11-07 UTC; M6.0-6.9: 26, M7.0+: 2). One window is a small sample; a quieter or busier 60 days would give different numbers. Every number comes from the same integer reference that passes GV-1..GV-3.

Hourly steps, seeds 100..159 (grid uses 100..111), nothing touches the network. Data: U.S. Geological Survey, ANSS ComCat.

## Chosen parameters (proposal for the human to confirm)

base share 0.25% at M6.0 (2x at M7, 3x at M8, max 1.5%), weekly cap 1.5%, monthly cap 5.0%, wrong-vote penalty 20%, minimum turnout 0.20% of supply. 45 of 243 grid combinations passed every threshold in docs/DECISIONS.md. Full grid: `grid.csv` (passing rows first).

Why this one: the lowest passive-holder dilution among passing combinations (tie-breaks in DECISIONS.md). Caution: it passes the 25%-of-weeks cap-binding threshold exactly at the limit (2 of 8 weeks), so this choice has no safety margin on T2.

## Scenario 1: real quakes, everyone honest

| parameters | passive dilution (60d) | worst 30-day loss | weeks with a clipped mint | final supply (TREM) |
|---|---|---|---|---|
| chosen | 6.43% | 4.82% | 25.0% | 1,068,672 |
| spec defaults (0.5% base) | 7.80% | 5.00% | 62.5% | 1,084,620 |

With the spec defaults the weekly cap binds in 62.5% of weeks, above the 25% threshold (T2), so the spec's own default parameters fail its own test on this window.

## Scenario 2: a 12-event swarm (M6.0-7.2 inside 36 h) added to the real catalog

Worst trailing-7-day mint: 1.5000% of supply against a 1.5% cap; worst 30-day passive loss 4.82%. Final supply 1,068,672 TREM (real-only: 1,068,672). The monthly cap was already exhausted by the real events, so the swarm adds nothing: this is the cap doing its job, and it also means a real swarm would mint no extra relief.

## Scenario 3: a liar posts 10 fake M7.0 events in one week; 5 watchers each challenge a fake with probability p

| p | fakes rejected (mean of 60 seeds) | extra supply from fakes vs real-only | liar's net bond change (TREM, mean) |
|---|---|---|---|
| 0% | 0.0% | 1.22% | 0 |
| 50% | 96.8% | 0.14% | -8,133 |
| 100% | 98.5% | 0.07% | -8,267 |

With nobody watching the fakes mint until a cap stops them (at most the weekly cap in any 7 days). In these runs the real events had already used the monthly cap, so the extra from fakes is small or zero; a quiet month would let fakes mint up to the full caps. That is the stated worst case.

## Scenario 4: a holder with 40% of supply (honest voters hold 45%, each event 30-100% of them vote)

- Challenging and voting no on every real event: the whale blocks 48.2% of real events (mean over 60 seeds). Whale net coins change: 276,333 TREM (it loses bonds when it is outvoted and gains penalties when it is not).
- Voting yes on 10 fakes that watchers challenge: 24.2% of fakes still count. Whale net coins change: 67,906 TREM.
- A majority holder can censor real events and can pass fakes, as the README must say plainly. The caps and the fixed relief list bound the damage; they do not prevent it.

## Scenario 5: selfish voters (voters hold 30% of supply; every real event is challenged)

Share of challenged real events that still count, mean of 60 seeds.

| selfish share of voting coins | penalty 5% | 10% | 20% | 40% |
|---|---|---|---|---|
| 0% | 96.4% | 96.4% | 96.4% | 96.4% |
| 30% | 89.7% | 91.7% | 94.9% | 96.4% |
| 60% | 21.1% | 17.3% | 15.4% | 24.6% |

Voters here are not strategic: a fixed share votes no. The penalty matters only because slashing shrinks a losing side's stake over repeated events, and at 60% selfish the selfish side usually wins, so real events are blocked whatever the penalty. The mechanism assumes an honest majority. Even with 0% selfish voters not every real event counts: when disputes overlap, the honest group's coins are already locked in earlier votes (coins cannot vote twice), turnout can fall under the minimum, and the event is rejected with every bond refunded. The same effect explains why 100% watcher challenge rejects 98.5% rather than 100% of fakes in scenario 3. With many simultaneous disputes the design is weaker, and turnout needs to be high.

## Top passing combinations

| base | week | month | slash | quorum | s1 dilution | s1 clipped weeks |
|---|---|---|---|---|---|---|
| 0.25% | 1.5% | 5.0% | 20% | 0.20% | 6.43% | 25.0% |
| 0.25% | 1.5% | 5.0% | 10% | 0.20% | 6.43% | 25.0% |
| 0.25% | 1.5% | 5.0% | 20% | 0.10% | 6.43% | 25.0% |
| 0.25% | 1.5% | 5.0% | 10% | 0.10% | 6.43% | 25.0% |
| 0.25% | 1.5% | 5.0% | 40% | 0.20% | 6.43% | 25.0% |
| 0.25% | 1.5% | 5.0% | 20% | 0.50% | 6.43% | 25.0% |

Charts: `supply.svg` (one panel per scenario). Series: `scenario*.csv` (daily supply, minted, passive holder share in ppm, weekly and monthly cap use).
