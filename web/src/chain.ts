import { RPCS } from "./config";
import { DEP } from "./deployment";

export interface Params {
  s0: string; min_mag_x10: number; min_alert?: number; base_ppm: number; max_event_ppm: number; cooldown_s: number; week_cap_ppm: number; month_cap_ppm: number;
  min_age_s: number; max_age_s: number; max_open: number; max_claims: number; claim_wait_s: number; threshold: number; match_ppm?: number; match_day_ppm?: number; match_month_ppm?: number; match_account_max?: string; tap_amount: string;
  publisher_accounts: string[]; relief_accounts: string[];
}
export interface State {
  supply: string; initial_supply: string; minted_7d: string; minted_30d: string; week_left: string; month_left: string; pending_events: number;
  tap_pool: string; given_total?: string; givers?: number; reserve?: string; funded_total?: string; matched_total?: string; matched_7d?: string; match_day_left?: string; match_month_left?: string; log_len: number; now_s: number; // the optional fields: contracts deployed with give() and the donation match
}
export interface Version { mag_x10: number; origin_s: number; alert?: number; attesters: string[] }
export interface Ev {
  event_id: string; status: "pending" | "counted"; claimer: string | null; created_at: number; mag_x10: number; origin_s: number; alert?: number; attestations: number; needed: number;
  versions: Version[]; claim_open_until: number | null; minted: string; clipped: boolean;
}

async function rpc<T>(method: string, params: unknown): Promise<T> {
  let last: unknown = new Error("no RPC");
  for (const url of RPCS) {
    try {
      const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
      if (!r.ok) throw new Error(`${url} answered ${r.status}`);
      const j = await r.json();
      if (j.error || j.result?.error) throw new Error(JSON.stringify(j.error ?? j.result.error));
      return j.result as T;
    } catch (e) { last = e; }
  }
  throw last;
}

export async function view<T>(method: string, args: object = {}): Promise<T> {
  const res = await rpc<{ result: number[] }>("query", {
    request_type: "call_function", finality: "final", account_id: DEP.contract, method_name: method,
    args_base64: btoa(JSON.stringify(args)),
  });
  return JSON.parse(new TextDecoder().decode(new Uint8Array(res.result))) as T;
}

export async function accessKeyCount(): Promise<number> {
  const r = await rpc<{ keys: unknown[] }>("query", { request_type: "view_access_key_list", finality: "final", account_id: DEP.contract });
  return r.keys.length;
}

export async function listEvents(): Promise<Ev[]> {
  const out: Ev[] = [];
  for (;;) {
    const page = await view<Ev[]>("list_events", { from: out.length, limit: 100 });
    out.push(...page);
    if (page.length < 100) return out;
  }
}

export interface Giver { account_id: string; given: string }
/** Everyone who has given, largest first. Returns null on a contract deployed before give() existed. */
export async function listGivers(): Promise<Giver[] | null> {
  const out: Giver[] = [];
  try {
    for (;;) {
      const page = await view<Giver[]>("list_givers", { from: out.length, limit: 100 });
      out.push(...page);
      if (page.length < 100) break;
    }
  } catch { return null; }
  return out.sort((a, b) => (BigInt(b.given) > BigInt(a.given) ? 1 : BigInt(b.given) < BigInt(a.given) ? -1 : 0));
}

/** For each giver: in how many "quake rounds" they gave, counted from the public log: a round is a gift made after at least one new quake had
 *  counted since that account's previous gift (so giving ten times between two quakes is one round). Computed in the browser; a label, not a power. */
export async function giverRounds(): Promise<Map<string, number>> {
  const lines: string[] = [];
  for (let guard = 0; guard < 200; guard++) { // at most 20,000 log lines
    const page = await view<string[]>("get_log", { from: lines.length, limit: 100 });
    lines.push(...page); if (page.length < 100) break;
  }
  const rounds = new Map<string, number>(), seen = new Map<string, number>(); let quakes = 0;
  for (const l of lines) {
    let e: { event: string; data: { account?: string } };
    try { e = JSON.parse(l); } catch { continue; }
    if (e.event === "event_counted") quakes++;
    else if (e.event === "gave" && e.data.account) { const a = e.data.account; if (quakes > (seen.get(a) ?? 0)) rounds.set(a, (rounds.get(a) ?? 0) + 1); seen.set(a, quakes); }
  }
  return rounds;
}

export async function registered(account: string): Promise<boolean> { return (await view<unknown>("storage_balance_of", { account_id: account })) !== null; }

/** An open claim nobody has confirmed after its time is up is shown as "not confirmed". */
export const unconfirmed = (e: Ev, now: number): boolean => e.status === "pending" && !!e.claim_open_until && now >= e.claim_open_until && e.attestations === 0;
