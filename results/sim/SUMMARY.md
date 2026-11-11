# Simulation summary

Real catalog: 28 events of M6.0+ in the committed 60-day window (2026-09-08 to 2026-11-07 UTC). Only quakes whose USGS PAGER alert level (an estimate of expected human impact) is yellow or higher count: 5 of the 28 (23 green, 3 yellow, 2 orange, 0 red). Scenarios 1 to 7 use those 5; scenario 8 sends all 28 to the contract. One window is a small sample. Every number comes from the same integer reference that passes the golden vectors. Five fixed bots, three must agree; bots attest 1 to 3 hours after a quake.

Hourly steps, seeds 100..119 (grid uses 100..111), nothing touches the network. Data: U.S. Geological Survey, ANSS ComCat.

## Chosen parameters

base share 0.25% at M6.0 (2x at M7, 3x at M8, max 1.5%), weekly cap 1.5%, monthly cap 5.0%. Holding promises no return: supply changes only by quake mints. Scenario 7 adds the donation match. 22 of 27 grid combinations passed every threshold in docs/DECISIONS.md. The grid's own pick (lowest passive-holder dilution) is base 0.25%, weekly 1.0%, monthly 5.0%; the confirmed values above are kept because they still pass. Full grid: `grid.csv` (passing rows first).

## Scenario 1: real quakes, five honest bots

| parameters | passive dilution (60d) | worst 30-day loss | weeks with a clipped mint | final supply (TREM) |
|---|---|---|---|---|
| chosen | 1.56% | 1.56% | 0.0% | 1,015,813 |
| spec defaults (0.5% base) | 2.48% | 2.48% | 25.0% | 1,025,381 |

With the spec defaults the weekly cap binds in 25.0% of weeks.

## Scenario 2: a 12-event swarm (M6.0-7.2 inside 36 h) added to the real catalog

Worst trailing-7-day mint: 1.4985% of supply against a 1.5% cap; worst 30-day passive loss 1.99%. Final supply 1,020,289 TREM (real-only: 1,015,813). The monthly cap was already exhausted by the real events, so the swarm adds nothing.

## Scenario 3: bad bots post 10 identical made-up M7.0 quakes in one week

| bad bots (of 5) | fakes that count (of 10, mean of 20 seeds) | extra supply from fakes | worst 7-day mint |
|---|---|---|---|
| 0 | 0.0 | 0.00% | 1.064% |
| 1 | 0.0 | 0.00% | 1.064% |
| 2 | 0.0 | 0.00% | 1.064% |
| 3 | 10.0 | 1.54% | 1.500% |
| 4 | 10.0 | 1.54% | 1.500% |
| 5 | 10.0 | 1.54% | 1.500% |

Below three bad bots no fake can count. At three or more, fakes count, but never past the caps (the real events had already used much of the allowance, so a quieter month would let more through). Honest bots do not stop it: counting needs three matching attestations and nothing else. That is the weak spot: trust sits in the five fixed bots.

## Scenario 4: bots offline for the whole 60 days

| bots offline (of 5) | real events that count | final supply (TREM) |
|---|---|---|
| 0 | 100.0% | 1,015,813 |
| 1 | 100.0% | 1,015,813 |
| 2 | 100.0% | 1,015,813 |
| 3 | 0.0% | 1,000,000 |
| 4 | 0.0% | 1,000,000 |
| 5 | 0.0% | 1,000,000 |

With two or fewer bots offline every real event still counts. With three or more offline nothing counts and nothing is created: the system fails safe rather than minting on too little evidence.

## Scenario 5: claim spam (6 made-up claims an hour from 80 accounts, all 60 days)

- Real events that count: 100.0%. Made-up claims that count: 0 of 8640.
- Most claims open at once: 32 against a limit of 32; the contract refused 4836 claims.
- Claims have their own limit, separate from the limit on events the bots start, so claim spam cannot take the slots the bots need.

## Scenario 6: community giving (holders send their own coins to the relief list)

Assumed behaviour, not measured: 100 holders with 0.1% of the initial supply each and one with 5%, reacting to counted quakes (the variants are written down in docs/DECISIONS.md before the run).

| variant | givers | gifts | coins given (TREM) | given as a share of coins minted | largest giver's share of gifts | supply and mints same as scenario 1 |
|---|---|---|---|---|---|---|
| 6a nobody gives | 0.0 | 0.0 | 0 | 0.0% | n/a | yes |
| 6b a few give after big quakes | 27.0 | 29.9 | 299 | 1.9% | 7.5% | yes |
| 6c many give a little after every quake | 96.8 | 247.5 | 1,231 | 7.8% | 2.0% | yes |
| 6d one large holder gives after M7+ | 1.0 | 2.0 | 9,500 | 60.1% | 100.0% | yes |

Mean of 20 seeds. In every variant and every seed the daily supply and every mint are identical to scenario 1, and the relief accounts end with scenario 1's balances plus exactly the gifts: giving creates nothing and moves no cap. Quakes created 15,813 TREM for the relief list in these 60 days; the gifts above are on top of that, paid by the givers alone. A large holder giving 10% after each M7+ ends with 40,500 TREM of 50,000 and all of the gifts. These numbers follow from the assumed behaviour: they show how the mechanic responds, not how people would act.


## Scenario 7: the donation match (the same giving behaviours, with a 100,000 TREM reserve)

Launch values: the match adds 10% of a gift, at most 0.5% of supply a day and 2% over 30 days, and at most 1,000 TREM per account; the launcher puts 100,000 TREM in the reserve first. The match goes to the relief accounts, not to the giver, and creates no coins. Mean of 20 seeds.

| variant | coins given (TREM) | matched from the reserve (TREM) | matched as a share of gifts | reserve left at day 60 (TREM) | days the daily budget was used up | the largest giver's share of the match | supply and mints same as scenario 1 |
|---|---|---|---|---|---|---|---|
| 6a nobody gives | 0 | 0 | n/a | 100,000 | 0.0 | n/a | yes |
| 6b a few give after big quakes | 299 | 30 | 10.0% | 99,970 | 0.0 | 7.5% | yes |
| 6c many give a little after every quake | 1,231 | 123 | 10.0% | 99,877 | 0.0 | 2.0% | yes |
| 6d one large holder gives after M7+ | 9,500 | 950 | 10.0% | 99,050 | 0.0 | 100.0% | yes |

In every variant and every seed the daily supply and every quake mint are identical to scenario 1, the relief accounts end with scenario 1's balances plus exactly the gifts plus exactly what was matched, and the reserve plus everything matched equals what was put in (checks M1 and M2). No day's match exceeded the daily budget and no 30-day window the monthly budget (check M3, tested on every step). Said plainly about the limit that can be bypassed (check M4): one account giving 10,000 TREM gets 1,000 TREM of match (its allowance), but fifty accounts each giving 10,000 TREM on one day get 5,000 TREM in total: the daily budget stops them, not the per-account allowance, because the contract cannot tell that the accounts belong to one person. Whoever gives first on a day takes that day's budget.

## Scenario 8: the impact bar (honest bots send every real M6+ quake, green ones too)

- Quakes sent to the contract: 28; below the bar (green): 23; at or above it: 5.
- Green quakes that counted, in any of 20 seeds: 0. Attestations the contract refused as below the bar (mean per run): 125.
- Supply over the 60 days identical to the run that never sends the green quakes: yes.
- With the bar, 5 real quakes count in 60 days (about 2.5 a month), the weekly cap bound in 0.0% of weeks, and a passive holder is diluted by 1.56%. With the bar off (`min_alert` 1, all 28 count) the same parameters gave 6.43% and a cap that bound in 25.0% of weeks.
- Three bad bots can still lie about the alert level as well (they attest anything); the bar stops honest mistakes and spam, not a majority of bad bots. That is the unchanged weak spot.

## Top passing combinations

| base | week | month | s1 dilution | s1 clipped weeks |
|---|---|---|---|---|
| 0.25% | 1.0% | 5.0% | 1.49% | 12.5% |
| 0.25% | 1.0% | 3.0% | 1.49% | 12.5% |
| 0.25% | 1.0% | 10.0% | 1.49% | 12.5% |
| 0.25% | 1.5% | 5.0% | 1.56% | 0.0% |
| 0.25% | 1.5% | 3.0% | 1.56% | 0.0% |
| 0.25% | 1.5% | 10.0% | 1.56% | 0.0% |

Charts: `supply.svg` (one panel per scenario). Series: `scenario*.csv` (daily supply, minted, passive holder share in ppm, coins given so far, reserve left, coins matched so far, weekly and monthly cap use).
