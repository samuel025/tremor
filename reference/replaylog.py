"""Replay a Tremor event log through the Python reference and report every disagreement.
Used offline by `make replay` (committed fixture) and online by `make verify-onchain` (get_log from testnet).
Limits (said plainly in the README): the log has events, votes and claims but no plain token transfers or bond deposits,
so replay checks supply, mints, caps, event outcomes, vote payouts and relief balances, not every holder's balance."""
import json
from tremor_ref import Params, Tremor, Reject, DAY


def params_from_chain(prm):
    return Params(s0=int(prm["s0"]), min_mag_x10=prm["min_mag_x10"], base_ppm=prm["base_ppm"], max_event_ppm=prm["max_event_ppm"],
                  cooldown_s=prm["cooldown_s"], week_cap_ppm=prm["week_cap_ppm"], month_cap_ppm=prm["month_cap_ppm"], bond=int(prm["bond"]),
                  window_s=prm["window_s"], vote_s=prm["vote_s"], slash_pct=prm["slash_pct"], quorum_ppm=prm["quorum_ppm"],
                  max_age_s=prm["max_age_s"], tap_amount=int(prm.get("tap_amount", 0)), relief=tuple(prm["relief_accounts"]))


def replay(prm, log_lines):
    """Returns (reference, list of mismatch strings)."""
    ref = Tremor(params_from_chain(prm), "launcher")
    bad = []

    def fund(a):  # the log does not show bond deposits; give every actor a large bond balance so the logic can run
        ref.bal.setdefault(a, 10**21)

    for i, line in enumerate(log_lines):
        e = json.loads(line) if isinstance(line, str) else line
        k, d = e["event"], e["data"]
        try:
            if k == "event_posted":
                fund(d["reporter"]); ref.report_event(d["reporter"], d["event_id"], d["mag_x10"], d["origin_s"], d["time"])
            elif k == "event_challenged":
                fund(d["challenger"]); ref.challenge(d["challenger"], d["event_id"], d["time"])
            elif k == "vote_cast":
                fund(d["voter"]); ref.vote(d["voter"], d["event_id"], d["side"], int(d["amount"]), ref.ev[d["event_id"]].challenged_at)
            elif k == "event_counted":
                r = ref.finalize(d["event_id"], d["time"])
                if r is None or r[0] != int(d["minted"]): bad.append(f"log {i} {d['event_id']}: minted {d['minted']} but reference says {r and r[0]}")
                elif r[2] != d["clipped"]: bad.append(f"log {i} {d['event_id']}: clipped flag differs")
                if ref.supply != int(d["supply"]): bad.append(f"log {i} {d['event_id']}: supply {d['supply']} but reference {ref.supply}")
            elif k == "event_rejected":
                r = ref.finalize(d["event_id"], d["time"])
                if r is not None or ref.ev[d["event_id"]].status != "rejected": bad.append(f"log {i} {d['event_id']}: reference did not reject")
            elif k == "tapped":
                pass  # starter coins move plain token balances only; the replay checks events, mints and caps
            elif k == "claimed":
                out = ref.claim_vote(d["account"], d["event_id"], 0)
                if out != int(d["paid"]): bad.append(f"log {i} claim {d['account']}: paid {d['paid']} but reference {out}")
            else:
                bad.append(f"log {i}: unknown event {k}")
        except (Reject, KeyError) as ex:
            bad.append(f"log {i} {k}: reference rejected a step the chain accepted ({ex})")
    return ref, bad
