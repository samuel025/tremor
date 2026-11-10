import { RPCS } from "./config";
import { DEP } from "./deployment";

export interface Params {
  s0: string; min_mag_x10: number; base_ppm: number; max_event_ppm: number; cooldown_s: number; week_cap_ppm: number; month_cap_ppm: number;
  min_age_s: number; max_age_s: number; max_open: number; max_claims: number; claim_wait_s: number; threshold: number; calm_ppm?: number; tap_amount: string;
  publisher_accounts: string[]; relief_accounts: string[];
}
export interface State {
  supply: string; initial_supply: string; minted_7d: string; minted_30d: string; week_left: string; month_left: string; pending_events: number;
  tap_pool: string; given_total?: string; givers?: number; dividends_total?: string; dividend_pot?: string; calm_days?: number; log_len: number; now_s: number; // the optional fields: contracts deployed with give() and the calm-day dividend
}
export interface Version { mag_x10: number; origin_s: number; attesters: string[] }
export interface Ev {
  event_id: string; status: "pending" | "counted"; claimer: string | null; created_at: number; mag_x10: number; origin_s: number; attestations: number; needed: number;
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

export async function registered(account: string): Promise<boolean> { return (await view<unknown>("storage_balance_of", { account_id: account })) !== null; }

/** An open claim nobody has confirmed after its time is up is shown as "not confirmed". */
export const unconfirmed = (e: Ev, now: number): boolean => e.status === "pending" && !!e.claim_open_until && now >= e.claim_open_until && e.attestations === 0;
