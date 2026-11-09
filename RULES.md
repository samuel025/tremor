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

## Invariants (checked in every test)
1. `S = S0 + sum(mints)`, and the sum of all token balances = S.
2. No mint exceeds the weekly or monthly allowance at that moment.
3. An event id mints at most once, and only after `threshold` different publishers attested the same record.
4. Parameters, publishers and relief accounts never change after init.
5. Replaying the event log reproduces supply, mints, caps and every event exactly.

## Golden vectors (S0 = 1,000,000 TREM, spec-default 0.5% base share for these numbers)
GV-1: each event is confirmed by 3 bots at its own origin time. E1 M6.0 -> 5,000 (supply 1,005,000; 1,000 each). E2 M7.0, 48h later -> 10,050 (1,015,050; 2,010 each). E3 M6.0, 12h after E2 -> raw 2,537.625, weekly allowance 15,225.75 - 15,050 = 175.75 minted, clipped (35.15 each; relief account total 3,045.15; a 1% holder's share falls 1.4997%).
GV-2: a visitor claims a quake. After two publisher attestations nothing has minted; a non-publisher's attestation is refused; the third attestation mints 5,000 (1,000 each); a fourth is refused ("already counted").
GV-3: two bots attest M6.0 and one attests M6.1 for the same id: nothing mints; the third bot cannot attest twice; a fourth bot attesting M6.0 completes three matching attestations and it mints 5,000 as M6.0. A made-up claim stays pending with no mint. A magnitude below 6.0 is refused.
