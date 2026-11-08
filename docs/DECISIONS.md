# DECISIONS (departures and gaps in the spec)
- D-1: A tie is treated like missing quorum: rejected, every bond and stake returned (spec says a tie is a rejection but only spells out the refund for low turnout).
- D-2: share formula `base_ppm * (mag_x10 - 50) / 10` (floors) matches the spec's 0.5% / 1.0% / 1.5% at M6/M7/M8 and is clipped at max_event_ppm.
- D-3: one vote per account per event; the reporter may vote; claim payouts credit the claimer's bond balance.
- D-4: MAX_OPEN_EVENTS = 64 is a placeholder until measured (open question 6).
- D-5: unchallenged finalize counts at the finalize block time (caps use that day's bucket); GV-1 counts at origin time by test design.

## M1: thresholds, logged BEFORE any simulation was run
Grid: base_ppm {0.25%, 0.5%, 1%}; weekly cap {1%, 1.5%, 3%}; monthly cap {3%, 5%, 10%}; slash {10%, 20%, 40%}; quorum {0.1%, 0.2%, 0.5%}. (max_event_ppm fixed at 1.5%, cooldown 24h, bond 1,000 TREM.)
A combination passes only if ALL hold:
- T1 (any scenario): a passive holder never loses more than the monthly cap in any 30 days.
- T2 (scenario 1, real catalog): the weekly cap binds (some mint clipped) in at most 25% of the 8 full weeks.
- T3 (scenario 3, liar, nobody watches): trailing-7-day minting never exceeds the weekly cap.
- T4 (scenario 3, 50% watcher challenge rate): at least 90% of fakes rejected (mean over seeds).
- T5 (scenario 5, 30% selfish voting coins, grid penalty): at least 90% of challenged real events still count (mean over seeds). Reported for every grid penalty; the grid only uses 10/20/40.
- Scenario 2 (swarm): trailing-7-day minting never exceeds the weekly cap (hard check, same as T3).
- Scenario 4 (whale): no pass mark; report blocked real events honestly.
Choice among passing combos: lowest passive-holder dilution in scenario 1, then lowest worst-week mint share in scenario 2, then lowest fake dilution in scenario 3 with nobody watching, then closest to the spec defaults. The human decides at the checkpoint.
Interpretations (the spec is silent): D-6 "half the watchers challenge" = 5 independent watchers, each challenging each fake with probability p; a fake is challenged if at least one does. D-7 holders are modelled as groups (one account per group; weighting is by coins so this is equivalent), honest vote participation each event is uniform in [30%, 100%] of the group's holding, drawn from the committed seeds. D-8 honest reports are posted 1 hour after the event origin. D-9 the real catalog is one 60-day window (28 M6+ events), a small sample.

## M1 results (run after the thresholds above were committed)
- 45 of 243 grid combinations pass. Proposed (NOT yet confirmed by the human): base 0.25%, weekly cap 1.5%, monthly cap 5%, penalty 20%, quorum 0.2%. See results/sim/SUMMARY.md and results/sim/grid.csv.
- Finding F-1: the spec's default base share (0.5%) fails T2 on the real catalog (weekly cap binds in 62.5% of weeks). The proposal halves the base share; it passes T2 exactly at the limit (25%), with no margin.
- Finding F-2: a 40% holder profits from blocking real events when honest turnout is partial (scenario 4). Stated as a limit, not fixed.
- Finding F-3: overlapping disputes lock the same coins, so turnout can fall under quorum even with no selfish voters.
- D-10: sim helpers (sim/simulate.py) drive the real reference state machine; report/grid code lives in sim/run_all.py and sim/report.py.

## Gate A: parameters confirmed by the human (2026-11-07)
base_ppm 2500 (0.25% at M6.0, 2x at M7, 3x at M8, max 1.5%), weekly cap 15000 ppm, monthly cap 50000 ppm, slash 20%, quorum 2000 ppm, bond 1,000 TREM, window 24h, vote 48h, cooldown 24h.
- D-11: hand-written token (see NOTES). All state is one Borsh blob (`Core`) plus an on-chain log vector: simple and exact, but gas grows with the number of events. Fine for a demo, would not scale to a real launch; the README must say so.
- D-12: `vote` side is the string "real" or "not_real" on chain; ft_transfer to yourself is rejected; ft_transfer_call refund is bounded by the receiver's remaining balance.
- D-13: Python reference default base_ppm changed to the Gate A value (2500); golden vectors pin 5000 explicitly.
- D-4 (update): MAX_OPEN_EVENTS stays 64; measured storage 303 B/event and 3 Tgas per report at the limit.
- D-14: sandbox tests use 6 s / 10 s windows (2 s / 3 s was too tight for three sequential votes).

## Automation round (2026-11-07), at the human's request
- D-15: every lock (report, challenge, vote) first tops the deposit balance up from the wallet if short, so there is no separate deposit step. `deposit_bond` and `withdraw_bond` still exist. RULES.md updated; Python reference, Rust engine, the 200-scenario conformance set and a sandbox test cover it.
- D-16: demo windows shortened to 20 s (challenge) and 30 s (vote) because a judge should not wait; the real 24 h / 48 h values are on the Live contract.
- D-17: keeper.mjs became a keeper and watcher: it challenges reports USGS does not confirm (not found, magnitude or time differs by more than 60 s), votes "not real" on those and "real" on real events that someone challenges, finalizes due events and claims payouts. It never challenges on a failed USGS lookup. Its stake per vote is 5,000 TREM, more than a judge's starter coins, so on the demo the bot outvotes a lone liar; that is a demonstration choice, not a claim about real holders.
- D-18: scheduler limits: hosted cron cannot wake every few seconds, so the demo watcher is a long-running loop restarted hourly by GitHub Actions; this may be delayed or against the spirit of GitHub's free-runner terms, and it can be run on any always-on machine instead. `make demo` conflicts with a running watcher (it would challenge the demo's made-up events first), so stop the watcher before running it.

## Design change: five fixed bots replace challenge-and-vote (2026-11-07), decided by the human
Reason: coin-weighted voting gives a majority holder control, and the human does not want "voting power" or liquidity to matter. Earthquakes are published automatically by USGS, so the contract is fed by bots instead.
- D-19: the contract has five fixed publisher accounts (set in `new`, never changed) and a threshold (3). A bot posts an attestation (event id, magnitude to one decimal, origin time) for a quake it found in USGS; when `threshold` DIFFERENT publishers post the SAME triple, the event counts and mints. A publisher can attest an event id once, so two disagreeing versions cannot both reach 3 of 5. No coins are locked, no deposits, no votes, no challenges, no penalties.
- D-20: `min_age_s` replaces the waiting window as the finality delay (an attestation is refused until the event is that old; USGS revises fresh events). Demo 10 s, live 6 h.
- D-21: anyone may submit a CLAIM (id, magnitude, origin) so visitors can try the system: a claim creates a pending event with no attestations. Bots attest it only if USGS confirms it, so a made-up claim stays unconfirmed and mints nothing. Claims cost nothing, so they are bounded: one open claim per account, at most `max_claims` open at once, each open for `claim_wait_s`; bot-posted pending events have their own limit `max_open`, so claim spam cannot block real quakes.
- D-22: trust moves from "whoever holds most coins" to "three of five named accounts". If three bots are bad, fakes mint up to the caps (and real quakes can be blocked); the caps and the fixed relief list still bound the damage. In the demo all five bots are run by us, so independence is only demonstrated, not real. If the bots are offline nothing mints (fails safe).
- D-23: removed: bonds/deposits, challenge, vote, claim_vote, quorum, penalty, dispute scenarios 3-5 of the simulation (replaced by bad-bot, offline-bot and claim-spam scenarios), the dispute replay. Kept: tap, caps, cooldown, relief list, finalize-free minting.

## Simulation under the bot model: thresholds, logged BEFORE the run (2026-11-07)
Grid (the mint math is unchanged, so S1/S2 behave as before): base_ppm {0.25%, 0.5%, 1%}, weekly cap {1%, 1.5%, 3%}, monthly cap {3%, 5%, 10%}; threshold 3 of 5 bots, min age 1 h. A combination passes only if ALL hold:
- T1 (any scenario): a passive holder never loses more than the monthly cap in any 30 days.
- T2 (scenario 1, real catalog, five honest bots): the weekly cap binds in at most 25% of the 8 full weeks.
- T3 (scenario 3, three bad bots post 10 identical fakes in a week): trailing-7-day minting never exceeds the weekly cap.
- T4 (scenario 3, TWO bad bots): zero fakes count.
- T5 (scenario 4, two bots offline): every real event still counts.
- Swarm (scenario 2): trailing-7-day minting never exceeds the weekly cap.
Also reported, no pass mark: bad bots 0..5 (how many fakes count and the extra supply), offline bots 0..5 (the share of real events that count; fails safe below 3 online), and claim spam (a spammer fills the claim limit: real events must still all count, fake claims must never count).
Choice among passing combinations: lowest passive-holder dilution in scenario 1, then lowest worst-week share in scenario 2, then closest to the spec defaults. The human already confirmed 0.25% / 1.5% / 5% at Gate A; if this run picks something else, say so and keep the confirmed values.
Modelling: bots attest 1 h to 3 h after a quake's origin (seeded lags); catalog and seeds as before; the real catalog is one 60-day window (a small sample).

## Publishing the Demo bot keys: considered and rejected (2026-11-08), the human's decision
- D-24: to avoid anyone having to keep the Demo bots running, the page could have played the five bots itself using Demo keys published in the repo (function-call keys limited to `attest` on the Demo contract; built and tested: a claim was counted in 15 s with no bot process running). The human chose NOT to publish any keys. All bot keys therefore stay private (`.state/` and GitHub secrets), and the browser-bots code was dropped before anything was pushed (it lives only on a local branch, `main-with-demo-keys`, which must never be pushed).
- Consequence: the Demo needs the owner's bots running while judges test (`make demo-bots` on a computer that stays on, or the manual GitHub job). To stop a judge mistaking that for a broken app, the page now says "The bots have not answered yet" when a REAL quake (the USGS check matches) has had no attestation for 30 s on the Demo (40 min on Live), and tells them to ask the project owner.
- Still possible later, if the human wants hands-off hosting: an event-driven function on a free hosting account that holds the keys as secrets and signs only for claims USGS confirms.
