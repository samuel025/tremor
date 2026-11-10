# Simulation summary

Real catalog: 28 events of M6.0+ in the committed 60-day window (2026-09-08 to 2026-11-07 UTC). Only quakes whose USGS PAGER alert level (an estimate of expected human impact) is yellow or higher count: 5 of the 28 (23 green, 3 yellow, 2 orange, 0 red). Scenarios 1 to 7 use those 5; scenario 8 sends all 28 to the contract. One window is a small sample. Every number comes from the same integer reference that passes the golden vectors. Five fixed bots, three must agree; bots attest 1 to 3 hours after a quake.

Hourly steps, seeds 100..119 (grid uses 100..111), nothing touches the network. Data: U.S. Geological Survey, ANSS ComCat.

## Chosen parameters

base share 0.25% at M6.0 (2x at M7, 3x at M8, max 1.5%), weekly cap 1.5%, monthly cap 5.0%, calm-day dividend 0.01% of supply for holders after each full day with no counted quake (outside the caps, which bound quake mints; every scenario below has it switched on). 22 of 27 grid combinations passed every threshold in docs/DECISIONS.md. The grid's own pick (lowest passive-holder dilution) is base 0.25%, weekly 1.0%, monthly 5.0%; the confirmed values above are kept because they still pass. Full grid: `grid.csv` (passing rows first).

## Scenario 1: real quakes, five honest bots

| parameters | passive dilution (60d) | worst 30-day loss | weeks with a clipped mint | final supply (TREM) |
|---|---|---|---|---|
| chosen | 1.55% | 1.56% | 0.0% | 1,021,824 |
| spec defaults (0.5% base) | 2.47% | 2.48% | 25.0% | 1,031,451 |

With the spec defaults the weekly cap binds in 25.0% of weeks.

## Scenario 2: a 12-event swarm (M6.0-7.2 inside 36 h) added to the real catalog

Worst trailing-7-day mint: 1.4985% of supply against a 1.5% cap; worst 30-day passive loss 1.99%. Final supply 1,026,226 TREM (real-only: 1,021,824). The monthly cap was already exhausted by the real events, so the swarm adds nothing.

## Scenario 3: bad bots post 10 identical made-up M7.0 quakes in one week

| bad bots (of 5) | fakes that count (of 10, mean of 20 seeds) | extra supply from fakes | worst 7-day mint |
|---|---|---|---|
| 0 | 0.0 | 0.00% | 1.064% |
| 1 | 0.0 | 0.00% | 1.064% |
| 2 | 0.0 | 0.00% | 1.064% |
| 3 | 10.0 | 1.48% | 1.500% |
| 4 | 10.0 | 1.48% | 1.500% |
| 5 | 10.0 | 1.48% | 1.500% |

Below three bad bots no fake can count. At three or more, fakes count, but never past the caps (the real events had already used much of the allowance, so a quieter month would let more through). Honest bots do not stop it: counting needs three matching attestations and nothing else. That is the weak spot: trust sits in the five fixed bots.

## Scenario 4: bots offline for the whole 60 days

| bots offline (of 5) | real events that count | final supply (TREM) |
|---|---|---|
| 0 | 100.0% | 1,021,824 |
| 1 | 100.0% | 1,021,824 |
| 2 | 100.0% | 1,021,824 |
| 3 | 0.0% | 1,006,320 |
| 4 | 0.0% | 1,006,320 |
| 5 | 0.0% | 1,006,320 |

With two or fewer bots offline every real event still counts. With three or more offline nothing counts and nothing is created: the system fails safe rather than minting on too little evidence.

## Scenario 5: claim spam (6 made-up claims an hour from 80 accounts, all 60 days)

- Real events that count: 100.0%. Made-up claims that count: 0 of 8640.
- Most claims open at once: 32 against a limit of 32; the contract refused 4836 claims.
- Claims have their own limit, separate from the limit on events the bots start, so claim spam cannot take the slots the bots need.

## Scenario 6: community giving (holders send their own coins to the relief list)

Assumed behaviour, not measured: 100 holders with 0.1% of the initial supply each and one with 5%, reacting to counted quakes (the variants are written down in docs/DECISIONS.md before the run).

| variant | givers | gifts | coins given (TREM) | given as a share of coins minted | largest giver's share of gifts | giver bonus paid (TREM) | bonus as a share of gifts | supply and mints same as scenario 1 |
|---|---|---|---|---|---|---|---|---|
| 6a nobody gives | 0.0 | 0.0 | 0 | 0.0% | n/a | 0 | n/a | yes |
| 6b a few give after big quakes | 27.0 | 29.9 | 299 | 1.9% | 7.5% | 37 | 12.3% | yes |
| 6c many give a little after every quake | 96.8 | 247.5 | 1,234 | 7.8% | 2.0% | 158 | 12.8% | yes |
| 6d one large holder gives after M7+ | 1.0 | 2.0 | 9,516 | 60.0% | 100.0% | 570 | 6.0% | yes |

Mean of 20 seeds. In every variant and every seed the daily supply and every mint are identical to scenario 1, and the relief accounts end with scenario 1's balances plus exactly the gifts: giving creates nothing and moves no cap. Quakes created 15,868 TREM for the relief list in these 60 days; the gifts above are on top of that, paid by the givers alone. A large holder giving 10% after each M7+ ends with 40,879 TREM of 50,000 and all of the gifts. These numbers follow from the assumed behaviour: they show how the mechanic responds, not how people would act.

- Giver bonus (20% of each calm-day dividend, each coin given earns at most 0.5% a day): a single account giving 10,000 TREM earned 1,203.55 TREM in 60 calm days; fifty accounts giving 200 TREM each earned 1,203.55 TREM in total, so splitting gifts gains nothing (the giver accounts' holdings differ by 34 base units). A lone giver of 1 TREM earned 0.3000 TREM, so tiny gifts cannot farm the pool. A gift takes at least about 200 calm days to earn back; with many givers the shared pool, not the cap, limits it (the 10,000 TREM gift above earned about 12% in 60 days).


## Scenario 7: the calm-day dividend (real quakes, five honest bots, the chosen quake parameters)

| dividend per calm day | calm days that paid (60 days plus the 3 closing days) | created for holders (TREM) | created for relief (TREM) | passive holder's loss of share (60d) | weeks with a clipped quake mint | passes every check |
|---|---|---|---|---|---|---|
| 0.000% (off) | 0 | 0 | 15,813 | 1.56% | 0.0% | yes |
| 0.005% | 59 | 2,974 | 15,840 | 1.55% | 0.0% | yes |
| 0.010% (chosen) | 59 | 5,956 | 15,868 | 1.55% | 0.0% | yes |
| 0.020% | 59 | 11,947 | 15,923 | 1.55% | 0.0% | yes |

The dividend is outside the weekly and monthly caps, which bound quake mints only, so relief's allowance is never spent on holders: relief received 15,868 TREM with the chosen dividend and 15,813 without it (slightly more, because each quake mints a share of a slightly larger supply). Holders received 5,956 TREM. The dividend's own limit is one per day: at most 0.01% of supply a day, about 0.07% a week, on top of the quake caps. Said plainly: the dividend makes a holder's coin count grow (by 0.60% of the starting supply here) but hardly changes their share of the supply, because almost every coin is paid the same percentage. A passive holder's loss of share over the 60 days is 1.55% with it and 1.56% without. Only the relief accounts are left out, and they hold a few percent of the supply, so that is all the share there is to move. Every other account is paid in proportion to its balance, including the launcher.

## Scenario 8: the impact bar (honest bots send every real M6+ quake, green ones too)

- Quakes sent to the contract: 28; below the bar (green): 23; at or above it: 5.
- Green quakes that counted, in any of 20 seeds: 0. Attestations the contract refused as below the bar (mean per run): 125.
- Supply over the 60 days identical to the run that never sends the green quakes: yes.
- With the bar, 5 real quakes count in 60 days (about 2.5 a month), the weekly cap bound in 0.0% of weeks, and a passive holder is diluted by 1.55%. With the bar off (`min_alert` 1, all 28 count) the same parameters gave 6.42% and a cap that bound in 25.0% of weeks.
- Three bad bots can still lie about the alert level as well (they attest anything); the bar stops honest mistakes and spam, not a majority of bad bots. That is the unchanged weak spot.

## Top passing combinations

| base | week | month | s1 dilution | s1 clipped weeks |
|---|---|---|---|---|
| 0.25% | 1.0% | 5.0% | 1.49% | 12.5% |
| 0.25% | 1.0% | 3.0% | 1.49% | 12.5% |
| 0.25% | 1.0% | 10.0% | 1.49% | 12.5% |
| 0.25% | 1.5% | 5.0% | 1.55% | 0.0% |
| 0.25% | 1.5% | 3.0% | 1.55% | 0.0% |
| 0.25% | 1.5% | 10.0% | 1.55% | 0.0% |

Charts: `supply.svg` (one panel per scenario). Series: `scenario*.csv` (daily supply, minted, passive holder share in ppm (balance plus unclaimed dividend), coins given so far, dividends created so far, weekly and monthly cap use).
