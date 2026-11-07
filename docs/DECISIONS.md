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
