"""Replay a Tremor event log through the Python reference and report every disagreement.
Used offline by `make replay` (committed fixture) and online by `make verify-onchain` (get_log from testnet).
Limits (said plainly in the README): the log has claims, attestations and mints but no plain token transfers, so replay checks supply,
mints, caps, which events counted, who attested what, what each account gave, what the reserve matched, and relief balances, not every holder's balance."""
from tremor_ref import Params, Tremor, Reject, DAY


def params_from_chain(prm):
    return Params(s0=int(prm["s0"]), min_mag_x10=prm["min_mag_x10"], min_alert=prm.get("min_alert", 1), base_ppm=prm["base_ppm"], max_event_ppm=prm["max_event_ppm"], cooldown_s=prm["cooldown_s"],
                  week_cap_ppm=prm["week_cap_ppm"], month_cap_ppm=prm["month_cap_ppm"], min_age_s=prm["min_age_s"], max_age_s=prm["max_age_s"], max_open=prm["max_open"],
                  max_claims=prm["max_claims"], claim_wait_s=prm["claim_wait_s"], threshold=prm["threshold"], match_ppm=prm.get("match_ppm", 0), match_day_ppm=prm.get("match_day_ppm", 0), match_month_ppm=prm.get("match_month_ppm", 0), match_account_max=int(prm.get("match_account_max", 0)), tap_amount=int(prm.get("tap_amount", 0)),
                  publishers=tuple(prm["publisher_accounts"]), relief=tuple(prm["relief_accounts"]))


def replay(prm, log_lines, now=None):
    """Returns (reference, list of mismatch strings). Gifts and reserve funding are replayed exactly (how much was matched, on which
    day, against which budgets); how an account came by its coins is not, because the log has no plain transfers."""
    import json
    ref = Tremor(params_from_chain(prm), "launcher"); bad = []; last = None
    for i, line in enumerate(log_lines):
        e = json.loads(line) if isinstance(line, str) else line
        k, d = e["event"], e["data"]
        try:
            if k == "claim_submitted":
                ref.submit_claim(d["claimer"], d["event_id"], d["mag_x10"], d["origin_s"], d["time"], d.get("alert", 2))
            elif k == "attested":
                last = ref.attest(d["publisher"], d["event_id"], d["mag_x10"], d["origin_s"], d["time"], d.get("alert", 2))
                n = len(ref.ev[d["event_id"]].versions[(d["mag_x10"], d["origin_s"], d.get("alert", 2))])
                if n != d["attestations"]: bad.append(f"log {i} {d['event_id']}: {d['attestations']} attestations on chain but {n} in the reference")
            elif k == "event_counted":
                if last is None or last[0] != int(d["minted"]): bad.append(f"log {i} {d['event_id']}: minted {d['minted']} but reference says {last and last[0]}")
                elif last[2] != d["clipped"]: bad.append(f"log {i} {d['event_id']}: clipped flag differs")
                if ref.supply != int(d["supply"]): bad.append(f"log {i} {d['event_id']}: supply {d['supply']} but reference {ref.supply}")
                last = None
            elif k == "funded":
                ref.tok[d["account"]] = ref.tok.get(d["account"], 0) + int(d["amount"])  # how the funder got the coins is not replayed (no plain transfers in the log)
                ref.tok["launcher"] -= int(d["amount"])
                ref.fund_match(d["account"], int(d["amount"]), d["time"])
                if ref.reserve != int(d["reserve"]): bad.append(f"log {i}: reserve {d['reserve']} but reference {ref.reserve}")
            elif k == "gave":
                ref.tok[d["account"]] = ref.tok.get(d["account"], 0) + int(d["amount"])
                ref.tok["launcher"] -= int(d["amount"])
                m = ref.give(d["account"], int(d["amount"]), d["time"])
                if ref.given[d["account"]] != int(d["total"]): bad.append(f"log {i} {d['account']}: total given {d['total']} but reference {ref.given[d['account']]}")
                if m != int(d["matched"]) or ref.reserve != int(d["reserve"]): bad.append(f"log {i} {d['account']}: matched {d['matched']} (reserve {d['reserve']}) but reference {m} (reserve {ref.reserve})")
            elif k == "tapped":
                pass  # starter coins move plain token balances only
            else:
                bad.append(f"log {i}: unknown event {k}")
        except (Reject, KeyError) as ex:
            bad.append(f"log {i} {k}: reference rejected a step the chain accepted ({ex})")
    return ref, bad
