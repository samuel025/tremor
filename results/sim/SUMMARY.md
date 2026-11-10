# Simulation summary

Real catalog: 28 events of M6.0+ in the committed 60-day window (2026-09-08 to 2026-11-07 UTC; M6.0-6.9: 26, M7.0+: 2). One window is a small sample. Every number comes from the same integer reference that passes the golden vectors. Five fixed bots, three must agree; bots attest 1 to 3 hours after a quake.

Hourly steps, seeds 100..119 (grid uses 100..111), nothing touches the network. Data: U.S. Geological Survey, ANSS ComCat.

## Chosen parameters

base share 0.25% at M6.0 (2x at M7, 3x at M8, max 1.5%), weekly cap 1.5%, monthly cap 5.0%, calm-day dividend 0.01% of supply for holders after each full day with no counted quake (outside the caps, which bound quake mints; every scenario below has it switched on). 4 of 27 grid combinations passed every threshold in docs/DECISIONS.md. Full grid: `grid.csv` (passing rows first).

## Scenario 1: real quakes, five honest bots

| parameters | passive dilution (60d) | worst 30-day loss | weeks with a clipped mint | final supply (TREM) |
|---|---|---|---|---|
| chosen | 6.42% | 5.00% | 25.0% | 1,073,322 |
| spec defaults (0.5% base) | 7.79% | 5.00% | 62.5% | 1,089,350 |

With the spec defaults the weekly cap binds in 62.5% of weeks.

## Scenario 2: a 12-event swarm (M6.0-7.2 inside 36 h) added to the real catalog

Worst trailing-7-day mint: 1.5000% of supply against a 1.5% cap; worst 30-day passive loss 5.00%. Final supply 1,073,211 TREM (real-only: 1,073,322). The monthly cap was already exhausted by the real events, so the swarm adds nothing.

## Scenario 3: bad bots post 10 identical made-up M7.0 quakes in one week

| bad bots (of 5) | fakes that count (of 10, mean of 20 seeds) | extra supply from fakes | worst 7-day mint |
|---|---|---|---|
| 0 | 0.0 | 0.00% | 1.500% |
| 1 | 0.0 | 0.00% | 1.500% |
| 2 | 0.0 | 0.00% | 1.500% |
| 3 | 10.0 | 1.19% | 1.500% |
| 4 | 10.0 | 1.15% | 1.500% |
| 5 | 10.0 | 1.11% | 1.500% |

Below three bad bots no fake can count. At three or more, fakes count, but never past the caps (the real events had already used much of the allowance, so a quieter month would let more through). Honest bots do not stop it: counting needs three matching attestations and nothing else. That is the weak spot: trust sits in the five fixed bots.

## Scenario 4: bots offline for the whole 60 days

| bots offline (of 5) | real events that count | final supply (TREM) |
|---|---|---|
| 0 | 100.0% | 1,073,211 |
| 1 | 100.0% | 1,073,211 |
| 2 | 100.0% | 1,073,211 |
| 3 | 0.0% | 1,006,320 |
| 4 | 0.0% | 1,006,320 |
| 5 | 0.0% | 1,006,320 |

With two or fewer bots offline every real event still counts. With three or more offline nothing counts and nothing is created: the system fails safe rather than minting on too little evidence.

## Scenario 5: claim spam (6 made-up claims an hour from 80 accounts, all 60 days)

- Real events that count: 100.0%. Made-up claims that count: 0 of 8640.
- Most claims open at once: 32 against a limit of 32; the contract refused 4842 claims.
- Claims have their own limit, separate from the limit on events the bots start, so claim spam cannot take the slots the bots need.

## Scenario 6: community giving (holders send their own coins to the relief list)

Assumed behaviour, not measured: 100 holders with 0.1% of the initial supply each and one with 5%, reacting to counted quakes (the variants are written down in docs/DECISIONS.md before the run).

| variant | givers | gifts | coins given (TREM) | given as a share of coins minted | largest giver's share of gifts | supply and mints same as scenario 1 |
|---|---|---|---|---|---|---|
| 6a nobody gives | 0.0 | 0.0 | 0 | 0.0% | n/a | yes |
| 6b a few give after big quakes | 68.3 | 109.5 | 1,091 | 1.6% | 3.7% | yes |
| 6c many give a little after every quake | 100.0 | 1397.4 | 6,774 | 9.8% | 1.4% | yes |
| 6d one large holder gives after M7+ | 1.0 | 2.0 | 9,513 | 13.8% | 100.0% | yes |

Mean of 20 seeds. In every variant and every seed the daily supply and every mint are identical to scenario 1, and the relief accounts end with scenario 1's balances plus exactly the gifts: giving creates nothing and moves no cap. Quakes created 68,895 TREM for the relief list in these 60 days; the gifts above are on top of that, paid by the givers alone. A large holder giving 10% after each M7+ ends with 40,647 TREM of 50,000 and all of the gifts. These numbers follow from the assumed behaviour: they show how the mechanic responds, not how people would act.

## Scenario 7: the calm-day dividend (real quakes, five honest bots, the chosen quake parameters)

| dividend per calm day | calm days that paid (60 days plus the 3 closing days) | created for holders (TREM) | created for relief (TREM) | passive holder's loss of share (60d) | weeks with a clipped quake mint | passes every check |
|---|---|---|---|---|---|---|
| 0.000% (off) | 0 | 0 | 68,672 | 6.43% | 25.0% | yes |
| 0.005% | 43 | 2,209 | 68,786 | 6.42% | 25.0% | yes |
| 0.010% (chosen) | 43 | 4,422 | 68,900 | 6.42% | 25.0% | yes |
| 0.020% | 43 | 8,863 | 69,129 | 6.41% | 25.0% | yes |

The dividend is outside the weekly and monthly caps, which bound quake mints only, so relief's allowance is never spent on holders: relief received 68,900 TREM with the chosen dividend and 68,672 without it (slightly more, because each quake mints a share of a slightly larger supply). Holders received 4,422 TREM. The dividend's own limit is one per day: at most 0.01% of supply a day, about 0.07% a week, on top of the quake caps. Said plainly: the dividend makes a holder's coin count grow (by 0.44% of the starting supply here) but hardly changes their share of the supply, because almost every coin is paid the same percentage. A passive holder's loss of share over the 60 days is 6.42% with it and 6.43% without. Only the relief accounts are left out, and they hold a few percent of the supply, so that is all the share there is to move. Every other account is paid in proportion to its balance, including the launcher.

## Top passing combinations

| base | week | month | s1 dilution | s1 clipped weeks |
|---|---|---|---|---|
| 0.25% | 1.5% | 5.0% | 6.42% | 25.0% |
| 0.25% | 1.5% | 10.0% | 6.43% | 25.0% |
| 0.25% | 3.0% | 10.0% | 7.03% | 0.0% |
| 0.50% | 3.0% | 10.0% | 12.47% | 25.0% |

Charts: `supply.svg` (one panel per scenario). Series: `scenario*.csv` (daily supply, minted, passive holder share in ppm (balance plus unclaimed dividend), coins given so far, dividends created so far, weekly and monthly cap use).
