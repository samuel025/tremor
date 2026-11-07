# Simulation summary

Real catalog: 28 events of M6.0+ in the committed 60-day window (2026-09-08 to 2026-11-07 UTC; M6.0-6.9: 26, M7.0+: 2). One window is a small sample. Every number comes from the same integer reference that passes the golden vectors. Five fixed bots, three must agree; bots attest 1 to 3 hours after a quake.

Hourly steps, seeds 100..119 (grid uses 100..111), nothing touches the network. Data: U.S. Geological Survey, ANSS ComCat.

## Chosen parameters

base share 0.25% at M6.0 (2x at M7, 3x at M8, max 1.5%), weekly cap 1.5%, monthly cap 5.0%. 5 of 27 grid combinations passed every threshold in docs/DECISIONS.md. Full grid: `grid.csv` (passing rows first).

## Scenario 1: real quakes, five honest bots

| parameters | passive dilution (60d) | worst 30-day loss | weeks with a clipped mint | final supply (TREM) |
|---|---|---|---|---|
| chosen | 6.43% | 4.99% | 25.0% | 1,068,672 |
| spec defaults (0.5% base) | 7.80% | 5.00% | 62.5% | 1,084,620 |

With the spec defaults the weekly cap binds in 62.5% of weeks.

## Scenario 2: a 12-event swarm (M6.0-7.2 inside 36 h) added to the real catalog

Worst trailing-7-day mint: 1.5000% of supply against a 1.5% cap; worst 30-day passive loss 4.99%. Final supply 1,068,672 TREM (real-only: 1,068,672). The monthly cap was already exhausted by the real events, so the swarm adds nothing.

## Scenario 3: bad bots post 10 identical made-up M7.0 quakes in one week

| bad bots (of 5) | fakes that count (of 10, mean of 20 seeds) | extra supply from fakes | worst 7-day mint |
|---|---|---|---|
| 0 | 0.0 | 0.00% | 1.500% |
| 1 | 0.0 | 0.00% | 1.500% |
| 2 | 0.0 | 0.00% | 1.500% |
| 3 | 10.0 | 1.24% | 1.500% |
| 4 | 10.0 | 1.20% | 1.500% |
| 5 | 10.0 | 1.16% | 1.500% |

Below three bad bots no fake can count. At three or more, fakes count, but never past the caps (the real events had already used much of the allowance, so a quieter month would let more through). Honest bots do not stop it: counting needs three matching attestations and nothing else. That is the weak spot: trust sits in the five fixed bots.

## Scenario 4: bots offline for the whole 60 days

| bots offline (of 5) | real events that count | final supply (TREM) |
|---|---|---|
| 0 | 100.0% | 1,068,672 |
| 1 | 100.0% | 1,068,672 |
| 2 | 100.0% | 1,068,672 |
| 3 | 0.0% | 1,000,000 |
| 4 | 0.0% | 1,000,000 |
| 5 | 0.0% | 1,000,000 |

With two or fewer bots offline every real event still counts. With three or more offline nothing counts and nothing is created: the system fails safe rather than minting on too little evidence.

## Scenario 5: claim spam (6 made-up claims an hour from 80 accounts, all 60 days)

- Real events that count: 100.0%. Made-up claims that count: 0 of 8640.
- Most claims open at once: 32 against a limit of 32; the contract refused 4842 claims.
- Claims have their own limit, separate from the limit on events the bots start, so claim spam cannot take the slots the bots need.

## Top passing combinations

| base | week | month | s1 dilution | s1 clipped weeks |
|---|---|---|---|---|
| 0.25% | 1.5% | 5.0% | 6.43% | 25.0% |
| 0.25% | 3.0% | 5.0% | 6.44% | 12.5% |
| 0.25% | 1.5% | 10.0% | 6.44% | 25.0% |
| 0.25% | 3.0% | 10.0% | 7.04% | 0.0% |
| 0.50% | 3.0% | 10.0% | 12.49% | 25.0% |

Charts: `supply.svg` (one panel per scenario). Series: `scenario*.csv` (daily supply, minted, passive holder share in ppm, weekly and monthly cap use).
