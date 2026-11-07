# RULES: source of truth for Tremor's math
Exact integer arithmetic; every division floors. TREM has 6 decimals; amounts are base units; ppm = parts per million; time in whole seconds.
Implemented in `reference/tremor_ref.py`; golden vectors in `vectors/` (generated from numbers typed here, never hand-edited, never produced by the reference).

## Mint for one counted event
- `share_ppm = min(max_event_ppm, base_ppm * max(0, mag_x10 - 50) / 10)`  (base at M6.0, 2x at M7.0, 3x at M8.0)
- `gap = min(cooldown_s, min |origin_s - o|)` over the last 16 counted origin times
- `raw = S * share_ppm * gap / (10^6 * cooldown_s)`
- `m7`, `m30` = coins minted in day buckets `floor(block_time / 86400)` over the current day and the previous 6 / 29
- `week_left = max(0, S * week_cap_ppm / 10^6 - m7)`, `month_left = max(0, S * month_cap_ppm / 10^6 - m30)`
- `mint = min(raw, week_left, month_left)`; `clipped = mint < raw`. S is the supply just before this mint.
- Split: each relief account gets `mint / 5`; the remainder (< 5 base units) goes to the first account.
- An event_id mints at most once, ever.

## Bonds and stakes
- report locks `bond` from the reporter's bond balance; challenge locks `bond` from the challenger (not the reporter). Any lock (report, challenge, vote) first tops the deposit balance up from the account's wallet if it is short, so no separate deposit step is needed; it fails only if wallet plus deposit balance are not enough.
- Unchallenged at `reported_at + window_s`: counts, reporter's bond returned.
- Challenged: vote runs `vote_s` from the challenge. One vote per account per event (any amount, one side).
- `turnout < S * quorum_ppm / 10^6` or a tie: rejected, every bond and stake returned (DECISIONS D-1).
- Otherwise the side with more locked coins wins. Winning bonder gets its bond back. Pot = losing bond + `stake * slash_pct / 100` from each losing voter, paid to winning voters on claim: `pot_left * stake / win_stake_left` (in sequence, no dust). If "real" wins the event counts and mints at finalize time.

## Invariants (checked in every test)
1. `S = S0 + sum(mints)`, and token balances + bond balances + locked + open pots = S.
2. No mint exceeds the weekly or monthly allowance at that moment.
3. An event_id mints at most once, and only after it counted.
4. Escrow conserved.
5. Parameters never change after init.
6. Replaying the log reproduces supply, balances and buckets exactly.

## Golden vectors (defaults, S0 = 1,000,000 TREM)
GV-1: E1 M6.0 -> 5,000 (supply 1,005,000; 1,000 each). E2 M7.0, 48h later -> 10,050 (1,015,050; 2,010 each). E3 M6.0, 12h after E2 -> raw 2,537.625, weekly allowance 15,225.75 - 15,050 = 175.75 minted, clipped (35.15 each; relief account total 3,045.15; a 1% holder's share falls 1.4997%).
GV-2: S = 1,015,225.75, min turnout 2,030.4515. Ada 3,000 real; Bayo 1,000 and Chidi 500 not real. Real wins 3,000 to 1,500. Pot 1,300 (1,000 + 200 + 100) all to Ada: Ada 4,300, Bayo 800, Chidi 400, reporter bond returned, escrow 6,500 before and after.
GV-3: only Ada, 1,000 real, under quorum: rejected, no mint, everything returned.
