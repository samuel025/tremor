# DECISIONS (departures and gaps in the spec)
- D-1: A tie is treated like missing quorum: rejected, every bond and stake returned (spec says a tie is a rejection but only spells out the refund for low turnout).
- D-2: share formula `base_ppm * (mag_x10 - 50) / 10` (floors) matches the spec's 0.5% / 1.0% / 1.5% at M6/M7/M8 and is clipped at max_event_ppm.
- D-3: one vote per account per event; the reporter may vote; claim payouts credit the claimer's bond balance.
- D-4: MAX_OPEN_EVENTS = 64 is a placeholder until measured (open question 6).
- D-5: unchallenged finalize counts at the finalize block time (caps use that day's bucket); GV-1 counts at origin time by test design.
