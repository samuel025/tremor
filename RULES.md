# RULES: source of truth for Tremor's math
Exact integer arithmetic; every division floors. TREM has 6 decimals; amounts are base units; ppm = parts per million; time in whole seconds.
Implemented in `reference/tremor_ref.py` and `contract/src/engine.rs`; golden vectors in `vectors/` (numbers typed here, never hand-edited, never produced by the reference).

## Who decides that a quake happened
Five fixed publisher accounts (set at launch, never changed) are bots that read USGS. A quake is a record `(event_id, mag_x10, origin_s)`.
- `attest(event_id, mag_x10, origin_s)` is allowed only for a publisher, once per publisher per event id, and only if: `min_mag_x10 <= mag_x10 <= 100`; the origin is not in the future; `now - origin_s <= max_age_s`; `now - origin_s >= min_age_s` (the finality delay: USGS revises fresh events); the id is 1 to 32 ASCII characters.
- An event counts when `threshold` (3) DIFFERENT publishers have attested exactly the same record. Because a publisher attests an id once, two different records cannot both reach 3 of 5. Counting happens in the attestation that completes the set, at that block time. An event id mints at most once, ever.
- `submit_claim(event_id, mag_x10, origin_s)` is open to anyone so visitors can try the system. It checks the same record rules except the minimum age, refuses an existing id, allows one open claim per account and at most `max_claims` open at once (a claim is open for `claim_wait_s`). A claim creates a pending event with no attestations; it mints only if publishers attest it. Bots attest what USGS itself says, so a made-up claim stays pending and never mints.
- Bot-started pending events are limited to `max_open` (still within `max_age_s`), separately from claims, so claim spam cannot block real quakes.
- No coins are locked, deposited, staked or voted with. Nothing in the rules gives a coin holder any say.

## Mint for one counted event
- `share_ppm = min(max_event_ppm, base_ppm * max(0, mag_x10 - 50) / 10)`  (base at M6.0, 2x at M7.0, 3x at M8.0)
- `gap = min(cooldown_s, min |origin_s - o|)` over every counted origin `o` that can still be within `cooldown_s` of a valid future event, i.e. `o >= now - max_age_s - cooldown_s` (not a fixed count: events may be counted out of origin order)
- `raw = S * share_ppm * gap / (10^6 * cooldown_s)`
- `m7`, `m30` = coins minted in day buckets `floor(block_time / 86400)` over the current day and the previous 6 / 29
- `week_left = max(0, S * week_cap_ppm / 10^6 - m7)`, `month_left = max(0, S * month_cap_ppm / 10^6 - m30)`
- `mint = min(raw, week_left, month_left)`; `clipped = mint < raw`. S is the total supply just before this mint (there is no burn). The caps are shares of the supply at mint time, so their absolute allowance grows with supply: they bound dilution over a window, not total issuance, and they compound with supply across windows.
- Split: each relief account gets `mint / 5`; the remainder (< 5 base units) goes to the first account.

## Starter coins
`tap()`: once per account, moves `tap_amount` from the pool (coins the launcher sent to the contract's own account) to the caller. It mints nothing.

## Giving
`give(amount)`: any holder except a relief account moves `amount > 0` of their own coins to the relief list, split like a mint (`amount / 5` each, remainder to the first account). It mints nothing: S, the day buckets, the caps and the cooldown are untouched, so every later mint is exactly what it would have been. The contract adds `amount` to the giver's running total `given[account]`; that total is a record only and gives no say in anything.

## Calm-day dividend
Days are `floor(block_time / 86400)`. A day is calm if no quake was counted in it. The clock starts at the first transaction (`settled_to` = that day; nothing is paid for earlier days).
- Every transaction first settles each finished day `x` from `settled_to` up to yesterday (at most 400 per call). For a calm day:
  `eligible = S - pot - (relief balances)`; `d = S * calm_ppm / 10^6`; if `eligible > 0` and `d > 0`: `acc += d * 10^18 / eligible`, `S += d`, `pot += d`. Nothing but the days themselves is used, so settling late gives exactly the result of settling on time.
- The dividend is outside the weekly and monthly caps and the day buckets: `m7`, `m30` and the caps count quake mints only, so relief's allowance is never spent on holders. Its own limit is one dividend per day (`calm_ppm` of supply a day).
- An account's share is `balance * (acc - paid[account]) / 10^18`; it is credited (and `paid[account] = acc`, `pot -=` the credit) before any change to that balance and when the account calls `claim_dividend`. Relief accounts earn nothing. Rounding dust stays in `pot`.
- `calm_ppm = 0` disables it.

## Invariants (checked in every test)
1. `S = S0 + sum(quake mints) + sum(dividends)`, and the sum of all token balances + `pot` = S.
2. No quake mint exceeds the weekly or monthly allowance at that moment; at most one dividend of `calm_ppm` of supply is created per day.
3. An event id mints at most once, and only after `threshold` different publishers attested the same record.
4. Parameters, publishers and relief accounts never change after init.
5. Replaying the event log reproduces supply, mints, caps and every event exactly.
6. Giving never changes S or any mint; `given` only grows, and no relief account is ever a giver.

## Golden vectors (S0 = 1,000,000 TREM, spec-default 0.5% base share for these numbers)
GV-1: each event is confirmed by 3 bots at its own origin time. E1 M6.0 -> 5,000 (supply 1,005,000; 1,000 each). E2 M7.0, 48h later -> 10,050 (1,015,050; 2,010 each). E3 M6.0, 12h after E2 -> raw 2,537.625, weekly allowance 15,225.75 - 15,050 = 175.75 minted, clipped (35.15 each; relief account total 3,045.15; a 1% holder's share falls 1.4997%).
GV-2: a visitor claims a quake. After two publisher attestations nothing has minted; a non-publisher's attestation is refused; the third attestation mints 5,000 (1,000 each); a fourth is refused ("already counted").
GV-3: two bots attest M6.0 and one attests M6.1 for the same id: nothing mints; the third bot cannot attest twice; a fourth bot attesting M6.0 completes three matching attestations and it mints 5,000 as M6.0. A made-up claim stays pending with no mint. A magnitude below 6.0 is refused.
GV-4: the launcher gives 12.000003 TREM: 2.400003 to the first relief account and 2.4 to each of the others (supply unchanged, given 12.000003). A second gift of 1 TREM adds 0.2 each (given 13.000003). An account with no coins, a relief account, and a gift of 0 are refused. A M6.0 quake afterwards still mints 5,000 (1,000 each): the first relief account then holds 1,002.600003 and the others 1,002.6.
GV-5 (`calm_ppm` 100): the launcher sends 100,000 TREM to bob on day 0, which starts the clock. On day 2, days 0 and 1 are settled as calm: 100 TREM, then 100.01 TREM (supply 1,000,200.01); bob is credited 20.001 and the launcher 180.009, leaving nothing unclaimed. A second claim and a relief account's claim are refused. A M6.0 quake on day 2 mints 5,001.00005 (1,000.20001 each). On day 3 nothing is paid (day 2 had a quake). On day 4, day 3 pays 100.520101 TREM over the 1,000,200.01 TREM not held by relief accounts; bob is credited 10.05201 and holds 100,030.05301.
